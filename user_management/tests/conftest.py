import os
os.environ.setdefault('USE_SQLITE', 'true')
os.environ.setdefault('JWT_SECRET', 'test-secret-only')
import pytest
import mongomock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from models.user import Base, get_db
from main import app
from services import mongo


@pytest.fixture
def backend(monkeypatch):
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    def db():
        with sessions() as session:
            yield session
    app.dependency_overrides[get_db] = db
    storage = mongomock.MongoClient(tz_aware=True).paddyguard
    storage.profile_images.create_index('user_id', unique=True)
    storage.activity_events.create_index([('user_id', 1), ('event_type', 1), ('request_id', 1)], unique=True)
    monkeypatch.setattr(mongo, '_database', storage)
    # No application startup or external DB connections: test dependencies are isolated.
    yield TestClient(app), sessions, storage
    app.dependency_overrides.clear()
    engine.dispose()


@pytest.fixture
def farmer(backend):
    client, _, _ = backend
    response = client.post('/register', json={'email': 'farmer@example.com', 'password': 'FarmerPass123!', 'full_name': 'Farmer One'})
    assert response.status_code == 201
    return {'Authorization': 'Bearer ' + response.json()['access_token']}


@pytest.fixture
def admin(backend):
    from models.user import User
    from routes.auth import pwd_context
    from services.jwt_service import create_access_token
    _, sessions, _ = backend
    with sessions() as db:
        user = User(email='admin@example.com', hashed_password=pwd_context.hash('AdminPass123!'), role='SYSTEM_ADMIN')
        db.add(user)
        db.commit()
        identity = user.id
    return {'Authorization': 'Bearer ' + create_access_token(identity)}
