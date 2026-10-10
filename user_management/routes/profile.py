"""Private PostgreSQL profiles and bounded, metadata-free MongoDB avatars."""
import io
import warnings
from datetime import datetime
from typing import Literal
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session
from PIL import Image, UnidentifiedImageError
from starlette.concurrency import run_in_threadpool
from models.user import User, get_db
from services.security import get_current_user
from services.mongo import database, record

router = APIRouter()
MAX_UPLOAD = 2 * 1024 * 1024


class ProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    email: str
    full_name: str | None
    phone: str | None
    district: str | None
    preferred_language: Literal['si', 'en']
    role: str
    created_at: datetime
    is_active: bool
    avatar_url: str = '/api/v1/users/me/avatar'


class ProfileUpdateRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    full_name: str | None = Field(default=None, min_length=1, max_length=120)
    phone: str | None = Field(default=None, pattern=r'^\+?[0-9 ()-]{7,24}$')
    district: str | None = Field(default=None, min_length=1, max_length=80)
    preferred_language: Literal['si', 'en'] = 'si'

    @field_validator('full_name', 'district')
    @classmethod
    def clean_text(cls, value):
        if value is not None:
            value = value.strip()
            if not value or any(ord(c) < 32 for c in value):
                raise ValueError('Invalid text')
        return value


@router.get('/me', response_model=ProfileResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.patch('/me', response_model=ProfileResponse)
def update_me(payload: ProfileUpdateRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(current_user, key, value)
    db.commit()
    db.refresh(current_user)
    record(current_user.id, 'PROFILE_UPDATED', 'PROFILE')
    return current_user


def compress_image(content):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(content)) as image:
                if image.format not in {'JPEG', 'PNG', 'WEBP'} or image.width * image.height > 16_000_000:
                    raise ValueError()
                image.load()
                image.thumbnail((512, 512))
                # Fresh RGB image strips EXIF and ancillary metadata.
                clean = Image.new('RGB', image.size, 'white')
                if image.mode in ('RGBA', 'LA'):
                    rgba = image.convert('RGBA')
                    clean.paste(rgba, mask=rgba.getchannel('A'))
                else:
                    clean.paste(image.convert('RGB'))
                output = io.BytesIO()
                clean.save(output, format='JPEG', quality=80, optimize=True)
                if output.tell() > 200 * 1024:
                    output = io.BytesIO()
                    clean.save(output, format='JPEG', quality=55, optimize=True)
                if output.tell() > 200 * 1024:
                    raise ValueError()
                return output.getvalue()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise HTTPException(422, 'Invalid or oversized image')


class AvatarResponse(BaseModel):
    avatar_url: str


@router.post('/me/avatar', response_model=AvatarResponse)
async def upload_avatar(avatar: UploadFile = File(...), user: User = Depends(get_current_user)):
    if avatar.content_type not in {'image/jpeg', 'image/png', 'image/webp'}:
        raise HTTPException(415, 'Unsupported image type')
    content = await avatar.read(MAX_UPLOAD + 1)
    if len(content) > MAX_UPLOAD:
        raise HTTPException(413, 'Avatar limit is 2 MiB')
    compressed = await run_in_threadpool(compress_image, content)
    def save():
        database().profile_images.update_one({'user_id': user.id}, {'$set': {'data': compressed, 'content_type': 'image/jpeg'}}, upsert=True)
        record(user.id, 'AVATAR_UPDATED', 'PROFILE')
    await run_in_threadpool(save)
    return {'avatar_url': '/api/v1/users/me/avatar'}


@router.get('/me/avatar')
def avatar(user: User = Depends(get_current_user)):
    image = database().profile_images.find_one({'user_id': user.id})
    if not image:
        raise HTTPException(404, 'Avatar not found')
    return Response(bytes(image['data']), media_type='image/jpeg', headers={'Cache-Control': 'private, no-store', 'X-Content-Type-Options': 'nosniff'})


@router.delete('/me/avatar', status_code=204)
def delete_avatar(user: User = Depends(get_current_user)):
    database().profile_images.delete_one({'user_id': user.id})
    record(user.id, 'AVATAR_DELETED', 'PROFILE')
    return Response(status_code=204)
