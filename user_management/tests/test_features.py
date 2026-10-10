import io
import pytest
from PIL import Image
from pymongo.errors import ServerSelectionTimeoutError
from services import mongo
from models.user import User


def image_bytes():
    buffer = io.BytesIO()
    Image.new('RGB', (900, 600), 'green').save(buffer, 'PNG')
    return buffer.getvalue()


def feedback(client, headers, **changes):
    return client.post('/feedback', headers=headers, json={'rating': 5, 'category': 'GENERAL', 'message': 'Useful advice', 'consent_public': True, **changes})


def test_existing_auth(backend, farmer):
    client, sessions, _ = backend
    assert client.post('/login', json={'email': 'farmer@example.com', 'password': 'bad'}).status_code == 401
    tokens = client.post('/login', json={'email': 'farmer@example.com', 'password': 'FarmerPass123!'}).json()
    assert client.post('/refresh', json={'refresh_token': tokens['refresh_token']}).status_code == 200
    assert client.get('/me', headers={'Authorization': 'Bearer '+tokens['refresh_token']}).status_code == 401
    assert client.post('/register', json={'email': 'farmer@example.com', 'password': 'FarmerPass123!'}).status_code == 409
    with sessions() as db:
        db.query(User).first().is_active = False
        db.commit()
    assert client.get('/me', headers=farmer).status_code == 401
    assert client.post('/refresh', json={'refresh_token': tokens['refresh_token']}).status_code == 401


@pytest.mark.parametrize('path', ['/admin/overview', '/admin/farmers', '/admin/farmers/id', '/admin/feedback', '/admin/activity'])
def test_admin_authorization(backend, farmer, path):
    client, _, _ = backend
    assert client.get(path).status_code == 401
    assert client.get(path, headers=farmer).status_code == 403


def test_profile_validation(backend, farmer):
    client, _, _ = backend
    assert client.patch('/me', headers=farmer, json={'role': 'SYSTEM_ADMIN'}).status_code == 422
    assert client.patch('/me', headers=farmer, json={'preferred_language': 'xx'}).status_code == 422
    assert client.patch('/me', headers=farmer, json={'full_name': '   '}).status_code == 422
    result = client.patch('/me', headers=farmer, json={'full_name': 'New Name', 'phone': '+94771234567', 'district': 'Galle', 'preferred_language': 'en'})
    assert result.status_code == 200
    assert result.json()['role'] == 'FARMER'
    assert 'hashed_password' not in result.json()
    assert client.get('/me').status_code == 401


def test_avatar_lifecycle(backend, farmer):
    client, _, storage = backend
    assert client.get('/me/avatar', headers=farmer).status_code == 404
    for _ in range(2):
        assert client.post('/me/avatar', headers=farmer, files={'avatar': ('test.png', image_bytes(), 'image/png')}).status_code == 200
    assert storage.profile_images.count_documents({}) == 1
    response = client.get('/me/avatar', headers=farmer)
    assert response.headers['content-type'] == 'image/jpeg'
    image = Image.open(io.BytesIO(response.content))
    assert max(image.size) <= 512 and len(response.content) < 200 * 1024
    assert client.get('/me/avatar').status_code == 401
    assert client.post('/me/avatar', headers=farmer, files={'avatar': ('bad.png', b'bad', 'image/png')}).status_code == 422
    assert client.post('/me/avatar', headers=farmer, files={'avatar': ('big.png', b'x'*(2*1024*1024+1), 'image/png')}).status_code == 413
    assert client.post('/me/avatar', headers=farmer, files={'avatar': ('bad.gif', b'bad', 'image/gif')}).status_code == 415
    assert client.delete('/me/avatar', headers=farmer).status_code == 204
    assert client.get('/me/avatar', headers=farmer).status_code == 404


def test_feedback_moderation(backend, farmer, admin):
    client, _, storage = backend
    response = feedback(client, farmer)
    assert response.status_code == 201 and response.json()['status'] == 'PENDING'
    identity = response.json()['id']
    assert client.get('/testimonials').json()['total'] == 0
    assert client.patch('/admin/feedback/'+identity, headers=farmer, json={'status': 'APPROVED'}).status_code == 403
    assert client.patch('/admin/feedback/'+identity, headers=admin, json={'status': 'APPROVED'}).status_code == 200
    public = client.get('/testimonials').json()['items'][0]
    assert set(public) == {'id', 'rating', 'category', 'message', 'created_at', 'display_label'}
    assert client.patch('/admin/feedback/'+identity, headers=admin, json={'status': 'APPROVED'}).status_code == 409
    assert client.patch('/admin/feedback/'+identity, headers=admin, json={'status': 'UNPUBLISHED'}).status_code == 200
    assert client.get('/testimonials').json()['total'] == 0
    assert client.delete('/admin/feedback/'+identity, headers=admin, params={'confirm': 'wrong'}).status_code == 422
    assert client.delete('/admin/feedback/'+identity, headers=admin, params={'confirm': identity}).status_code == 204
    assert storage.activity_events.count_documents({'event_type': 'FEEDBACK_DELETED'}) == 1


@pytest.mark.parametrize('changes', [{'rating': 1}, {'consent_public': False}])
def test_negative_or_no_consent_stays_private(backend, farmer, admin, changes):
    client, _, storage = backend
    identity = feedback(client, farmer, **changes).json()['id']
    assert client.patch('/admin/feedback/'+identity, headers=admin, json={'status': 'APPROVED'}).status_code == 409
    assert client.get('/admin/feedback', headers=admin).json()['total'] == 1
    assert client.get('/testimonials').json()['total'] == 0
    assert storage.feedback.count_documents({}) == 1
    assert client.patch('/admin/feedback/'+identity, headers=admin, json={'status': 'REJECTED'}).status_code == 200
    assert client.get('/admin/feedback', headers=admin, params={'status': 'REJECTED'}).json()['total'] == 1
    assert storage.feedback.count_documents({}) == 1


def test_feedback_validation(backend, farmer):
    client, _, _ = backend
    for change in ({'rating': 0}, {'rating': True}, {'message': ' '}, {'status': 'APPROVED'}, {'user_id': 'other'}, {'category': 'BAD'}):
        assert feedback(client, farmer, **change).status_code == 422


def test_activity_isolation_and_internal_auth(backend, farmer, admin, monkeypatch):
    client, _, storage = backend
    monkeypatch.setenv('INTERNAL_ACTIVITY_KEY', 'private-key')
    payload = {'event_type': 'PEST_DIAGNOSIS_COMPLETED', 'module': 'PEST', 'request_id': 'request-1'}
    assert client.post('/internal/activity', headers=farmer, json=payload).status_code == 403
    headers = farmer | {'X-Internal-Activity-Key': 'private-key'}
    for _ in range(2):
        assert client.post('/internal/activity', headers=headers, json=payload).status_code == 202
    assert storage.activity_events.count_documents({'event_type': 'PEST_DIAGNOSIS_COMPLETED'}) == 1
    assert client.post('/internal/activity', headers=headers, json=payload | {'user_id': 'someone-else'}).status_code == 422
    mongo.record('other-farmer', 'LOGIN', 'AUTH')
    history = client.get('/activity/me', headers=farmer).json()
    assert all(item['user_id'] != 'other-farmer' for item in history['items'])
    assert client.get('/activity/me', headers=farmer, params={'limit': 101}).status_code == 422
    assert client.get('/activity/me', headers=farmer, params={'since': '2026-01-01'}).status_code == 422
    assert client.get('/admin/activity', headers=admin).json()['total'] > history['total']


def test_mongo_unavailable_auth_survives(backend, farmer, admin, monkeypatch, caplog):
    client, _, _ = backend
    monkeypatch.setattr(mongo, '_database', None)
    assert client.post('/login', json={'email': 'farmer@example.com', 'password': 'FarmerPass123!'}).status_code == 200
    assert client.patch('/me', headers=farmer, json={'district': 'Matara'}).status_code == 200
    assert feedback(client, farmer).status_code == 503
    assert client.get('/admin/overview', headers=admin).status_code == 503
    assert client.get('/me/avatar', headers=farmer).status_code == 503
    assert 'could not be stored' in caplog.text


def test_mongo_connection_error_is_sanitized(backend, farmer, monkeypatch):
    client, _, storage = backend
    def fail(*a, **kw):
        raise ServerSelectionTimeoutError('private-uri-and-password')
    monkeypatch.setattr(storage.feedback, 'insert_one', fail)
    response = feedback(client, farmer)
    assert response.status_code == 503 and 'private-uri' not in response.text


def test_bootstrap(backend, monkeypatch):
    import bootstrap_admin
    _, sessions, _ = backend
    monkeypatch.setattr(bootstrap_admin, 'SessionLocal', sessions)
    with pytest.raises(ValueError):
        bootstrap_admin.bootstrap('admin@example.com', 'weak')
    with pytest.raises(ValueError):
        bootstrap_admin.bootstrap('not-an-email', 'AdminPassword123!')
    assert bootstrap_admin.bootstrap('admin@example.com', 'AdminPassword123!') == 'Administrator provisioned'
    assert 'already' in bootstrap_admin.bootstrap('admin@example.com', 'OtherPassword123!')
    with sessions() as db:
        user = db.query(User).one()
        assert user.role == 'SYSTEM_ADMIN'
        assert bootstrap_admin.pwd_context.verify('AdminPassword123!', user.hashed_password)
        user.role = 'FARMER'
        db.commit()
    with pytest.raises(ValueError, match='refusing'):
        bootstrap_admin.bootstrap('admin@example.com', 'OtherPassword123!')


def test_dashboard_and_farmer_search(backend, farmer, admin):
    client, _, _ = backend
    assert client.get('/admin/overview', headers=admin).json()['farmers'] == 1
    result = client.get('/admin/farmers', headers=admin, params={'search': 'Farmer'}).json()
    assert result['total'] == 1
    assert client.get('/admin/farmers/'+result['items'][0]['id'], headers=admin).status_code == 200
    assert client.get('/admin/farmers/not-found', headers=admin).status_code == 404


def test_admin_login_role_and_revocation(backend, admin):
    client, sessions, _ = backend
    tokens = client.post('/login', json={'email': 'admin@example.com', 'password': 'AdminPass123!'})
    assert tokens.status_code == 200
    headers = {'Authorization': 'Bearer '+tokens.json()['access_token']}
    assert client.get('/me', headers=headers).json()['role'] == 'SYSTEM_ADMIN'
    assert client.get('/admin/overview', headers=headers).status_code == 200
    with sessions() as db:
        db.query(User).filter(User.email == 'admin@example.com').one().role = 'FARMER'
        db.commit()
    assert client.get('/admin/overview', headers=headers).status_code == 403


def test_frontend_role_claim_cannot_elevate(backend, farmer):
    from jose import jwt
    from services.jwt_service import JWT_SECRET
    client, _, _ = backend
    token = farmer['Authorization'].split(' ')[1]
    claims = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
    claims['role'] = 'SYSTEM_ADMIN'
    forged_role = jwt.encode(claims, JWT_SECRET, algorithm='HS256')
    assert client.get('/admin/overview', headers={'Authorization': 'Bearer '+forged_role}).status_code == 403
    assert client.post('/register', json={'email': 'bad@example.com', 'password': 'Password123!', 'role': 'SYSTEM_ADMIN'}).status_code == 422


def test_avatar_decompression_bomb(backend, farmer, monkeypatch):
    client, _, _ = backend
    monkeypatch.setattr(Image, 'MAX_IMAGE_PIXELS', 1000)
    assert client.post('/me/avatar', headers=farmer, files={'avatar': ('bomb.png', image_bytes(), 'image/png')}).status_code == 422


def test_bad_mongo_configuration_does_not_stop_identity(backend, farmer, monkeypatch):
    client, _, _ = backend
    monkeypatch.setenv('MONGO_URL', 'mongodb://[')
    mongo.initialize()
    assert client.get('/me', headers=farmer).status_code == 200


def test_pool_cleanup_and_no_automatic_retention(monkeypatch):
    import mongomock
    storage_client = mongomock.MongoClient()
    calls = []
    def factory(url, **kwargs):
        calls.append(kwargs)
        return storage_client
    monkeypatch.setenv('MONGO_URL', 'mongodb://localhost')
    monkeypatch.setenv('ACTIVITY_RETENTION_DAYS', '1')
    monkeypatch.setattr(mongo, 'MongoClient', factory)
    monkeypatch.setattr(mongo, 'client', None)
    monkeypatch.setattr(mongo, '_database', None)
    mongo.initialize()
    assert calls[0]['maxPoolSize'] == 20
    assert calls[0]['serverSelectionTimeoutMS'] == 2000
    assert calls[0]['waitQueueTimeoutMS'] == 2000
    indexes = mongo.database().activity_events.index_information()
    assert not any('expireAfterSeconds' in index for index in indexes.values())
    mongo.close()
    assert mongo.client is None and mongo._database is None
