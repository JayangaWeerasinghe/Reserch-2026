"""Feedback, public testimonials, administration, and private activity history."""
import os
import secrets
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import or_
from sqlalchemy.orm import Session
from models.user import User, get_db
from routes.profile import ProfileResponse
from services.security import get_current_user, require_system_admin
from services.mongo import database, record

router = APIRouter()
Category = Literal['VOICE', 'LEAF', 'PEST', 'TREATMENT', 'GENERAL']
Status = Literal['PENDING', 'APPROVED', 'REJECTED', 'UNPUBLISHED']
Event = Literal['LOGIN', 'PROFILE_UPDATED', 'AVATAR_UPDATED', 'AVATAR_DELETED', 'FEEDBACK_SUBMITTED',
                'VOICE_DIAGNOSIS_COMPLETED', 'VOICE_FOLLOWUP_COMPLETED', 'LEAF_DIAGNOSIS_COMPLETED',
                'PEST_DIAGNOSIS_COMPLETED', 'TREATMENT_INTERACTION', 'FEEDBACK_MODERATED', 'FEEDBACK_DELETED']
Module = Literal['AUTH', 'PROFILE', 'FEEDBACK', 'VOICE', 'LEAF', 'PEST', 'TREATMENT', 'ADMIN']


class FeedbackRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    rating: int = Field(ge=1, le=5, strict=True)
    category: Category
    message: str = Field(min_length=1, max_length=2000)
    consent_public: bool = Field(default=False, strict=True)

    @field_validator('message')
    @classmethod
    def trim_message(cls, value):
        value = value.strip()
        if not value:
            raise ValueError('Message cannot be blank')
        return value


class ModerationRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    status: Status


class ActivityRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    event_type: Literal['VOICE_DIAGNOSIS_COMPLETED', 'VOICE_FOLLOWUP_COMPLETED', 'LEAF_DIAGNOSIS_COMPLETED', 'PEST_DIAGNOSIS_COMPLETED', 'TREATMENT_INTERACTION']
    module: Literal['VOICE', 'LEAF', 'PEST', 'TREATMENT']
    request_id: str = Field(min_length=1, max_length=128)


class FeedbackResponse(BaseModel):
    id: str
    user_id: str
    rating: int
    category: Category
    message: str
    consent_public: bool
    status: Status
    created_at: datetime
    updated_at: datetime
    moderated_by: str | None = None


class TestimonialResponse(BaseModel):
    id: str
    rating: int
    category: Category
    message: str
    created_at: datetime
    display_label: str


class ActivityResponse(BaseModel):
    id: str
    user_id: str
    event_type: Event
    module: Module
    status: Literal['SUCCESS']
    timestamp: datetime
    request_id: str
    metadata: dict


class Pagination(BaseModel):
    total: int
    offset: int
    limit: int


class FeedbackPage(Pagination):
    items: list[FeedbackResponse]


class TestimonialPage(Pagination):
    items: list[TestimonialResponse]


class ActivityPage(Pagination):
    items: list[ActivityResponse]


class FarmerPage(Pagination):
    items: list[ProfileResponse]


class OverviewResponse(BaseModel):
    farmers: int
    active_farmers: int
    feedback: int
    pending_feedback: int
    testimonials: int
    activity_events: int


def public_record(doc):
    return {('id' if k == '_id' else k): v for k, v in doc.items()}


def page(collection, query, offset, limit, order='created_at'):
    return {'items': [public_record(d) for d in collection.find(query).sort([(order, -1), ('_id', -1)]).skip(offset).limit(limit)],
            'total': collection.count_documents(query), 'offset': offset, 'limit': limit}


@router.post('/feedback', response_model=FeedbackResponse, status_code=201)
def submit_feedback(payload: FeedbackRequest, user: User = Depends(get_current_user)):
    if user.role != 'FARMER':
        raise HTTPException(403, 'Farmer role required')
    now = datetime.now(timezone.utc)
    doc = {'_id': str(uuid4()), 'user_id': user.id, **payload.model_dump(), 'status': 'PENDING', 'created_at': now, 'updated_at': now}
    database().feedback.insert_one(doc)
    record(user.id, 'FEEDBACK_SUBMITTED', 'FEEDBACK', metadata={'feedback_id': doc['_id']})
    return public_record(doc)


@router.get('/feedback/mine', response_model=FeedbackPage)
def my_feedback(offset: int = Query(0, ge=0, le=100000), limit: int = Query(20, ge=1, le=100), user: User = Depends(get_current_user)):
    return page(database().feedback, {'user_id': user.id}, offset, limit)


@router.get('/testimonials', response_model=TestimonialPage)
def testimonials(offset: int = Query(0, ge=0, le=100000), limit: int = Query(20, ge=1, le=100)):
    result = page(database().feedback, {'status': 'APPROVED', 'consent_public': True, 'rating': {'$gte': 4}}, offset, limit)
    result['items'] = [{k: item[k] for k in ('id', 'rating', 'category', 'message', 'created_at')} | {'display_label': 'Anonymous farmer'} for item in result['items']]
    return result


@router.patch('/admin/feedback/{feedback_id}', response_model=FeedbackResponse)
def moderate(feedback_id: str, payload: ModerationRequest, admin: User = Depends(require_system_admin)):
    collection = database().feedback
    current = collection.find_one({'_id': feedback_id})
    if not current:
        raise HTTPException(404, 'Feedback not found')
    allowed = {'PENDING': {'APPROVED', 'REJECTED'}, 'APPROVED': {'UNPUBLISHED', 'REJECTED'},
               'REJECTED': {'PENDING'}, 'UNPUBLISHED': {'APPROVED', 'REJECTED'}}
    if payload.status not in allowed.get(current['status'], set()):
        raise HTTPException(409, 'Invalid moderation transition')
    if payload.status == 'APPROVED' and (current['rating'] < 4 or not current['consent_public']):
        raise HTTPException(409, 'Approval requires rating 4–5 and publication consent')
    update = {'status': payload.status, 'updated_at': datetime.now(timezone.utc), 'moderated_by': admin.id}
    result = collection.update_one({'_id': feedback_id, 'status': current['status']}, {'$set': update})
    if result.matched_count != 1:
        raise HTTPException(409, 'Feedback changed; reload before moderating')
    record(admin.id, 'FEEDBACK_MODERATED', 'ADMIN', metadata={'feedback_id': feedback_id, 'previous_status': current['status'], 'status': payload.status})
    return public_record(current | update)


@router.delete('/admin/feedback/{feedback_id}', status_code=204)
def delete_feedback(feedback_id: str, confirm: str = Query(...), admin: User = Depends(require_system_admin)):
    if confirm != feedback_id:
        raise HTTPException(422, 'confirm must equal feedback ID')
    if not database().feedback.delete_one({'_id': feedback_id}).deleted_count:
        raise HTTPException(404, 'Feedback not found')
    record(admin.id, 'FEEDBACK_DELETED', 'ADMIN', metadata={'feedback_id': feedback_id})
    return Response(status_code=204)


@router.get('/admin/feedback', response_model=FeedbackPage)
def admin_feedback(status: Status | None = None, category: Category | None = None, user_id: str | None = None,
                   rating: int | None = Query(None, ge=1, le=5), offset: int = Query(0, ge=0, le=100000),
                   limit: int = Query(20, ge=1, le=100), admin: User = Depends(require_system_admin)):
    query = {k: v for k, v in {'status': status, 'category': category, 'user_id': user_id, 'rating': rating}.items() if v is not None}
    return page(database().feedback, query, offset, limit)


@router.get('/admin/overview', response_model=OverviewResponse)
def overview(admin: User = Depends(require_system_admin), db: Session = Depends(get_db)):
    mongo = database()
    return {'farmers': db.query(User).filter(User.role == 'FARMER').count(),
            'active_farmers': db.query(User).filter(User.role == 'FARMER', User.is_active.is_(True)).count(),
            'feedback': mongo.feedback.count_documents({}), 'pending_feedback': mongo.feedback.count_documents({'status': 'PENDING'}),
            'testimonials': mongo.feedback.count_documents({'status': 'APPROVED', 'consent_public': True, 'rating': {'$gte': 4}}),
            'activity_events': mongo.activity_events.count_documents({})}


@router.get('/admin/farmers', response_model=FarmerPage)
def farmers(search: str | None = Query(None, max_length=120), offset: int = Query(0, ge=0, le=100000),
            limit: int = Query(20, ge=1, le=100), admin: User = Depends(require_system_admin), db: Session = Depends(get_db)):
    query = db.query(User).filter(User.role == 'FARMER')
    if search:
        term = '%' + search.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
        query = query.filter(or_(User.email.ilike(term, escape='\\'), User.full_name.ilike(term, escape='\\')))
    return {'items': [ProfileResponse.model_validate(u) for u in query.order_by(User.created_at.desc(), User.id).offset(offset).limit(limit)],
            'total': query.count(), 'offset': offset, 'limit': limit}


@router.get('/admin/farmers/{user_id}', response_model=ProfileResponse)
def farmer(user_id: str, admin: User = Depends(require_system_admin), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id, User.role == 'FARMER').first()
    if not user:
        raise HTTPException(404, 'Farmer not found')
    return user


def activity_query(event_type, module, since, until, user_id=None):
    query = {} if user_id is None else {'user_id': user_id}
    if event_type:
        query['event_type'] = event_type
    if module:
        query['module'] = module
    if since or until:
        for date in (since, until):
            if date and date.tzinfo is None:
                raise HTTPException(422, 'Dates require a timezone')
        if since and until and since > until:
            raise HTTPException(422, 'since must precede until')
        query['timestamp'] = {}
        if since:
            query['timestamp']['$gte'] = since
        if until:
            query['timestamp']['$lte'] = until
    return query


@router.get('/activity/me', response_model=ActivityPage)
def history(event_type: Event | None = None, module: Module | None = None, since: datetime | None = None,
            until: datetime | None = None, offset: int = Query(0, ge=0, le=100000), limit: int = Query(20, ge=1, le=100),
            user: User = Depends(get_current_user)):
    return page(database().activity_events, activity_query(event_type, module, since, until, user.id), offset, limit, 'timestamp')


@router.get('/admin/activity', response_model=ActivityPage)
def admin_activity(event_type: Event | None = None, module: Module | None = None, since: datetime | None = None,
                   until: datetime | None = None, user_id: str | None = None, offset: int = Query(0, ge=0, le=100000),
                   limit: int = Query(20, ge=1, le=100), admin: User = Depends(require_system_admin)):
    return page(database().activity_events, activity_query(event_type, module, since, until, user_id), offset, limit, 'timestamp')


@router.post('/internal/activity', status_code=202)
def ingest(payload: ActivityRequest, x_internal_activity_key: str = Header(default=''), user: User = Depends(get_current_user)):
    expected = os.getenv('INTERNAL_ACTIVITY_KEY', '')
    if not expected or not secrets.compare_digest(x_internal_activity_key, expected):
        raise HTTPException(403, 'Internal service authentication required')
    module = payload.event_type.split('_')[0]
    if module != payload.module:
        raise HTTPException(422, 'Event/module mismatch')
    record(user.id, payload.event_type, payload.module, payload.request_id)
    return {'accepted': True}
