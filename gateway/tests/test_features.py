import json
import httpx
import pytest
from fastapi.testclient import TestClient
from main import app
from services.activity import confirmed


@pytest.fixture
def proxy(monkeypatch):
    calls = []
    class Client:
        def __init__(self, **kwargs):
            calls.append(('timeout', kwargs))
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def request(self, method, url, **kwargs):
            calls.append((method, url, kwargs))
            return httpx.Response(200, content=b'binary-avatar', headers={'Content-Type': 'image/jpeg', 'Cache-Control': 'private, no-store'})
        async def post(self, url, **kwargs):
            calls.append(('POST', url, kwargs))
            if '/internal/activity' in url:
                return httpx.Response(202, json={'accepted': True})
            if '/followup' in url:
                return httpx.Response(200, json={'disease': 'Brown Spot', 'confidence': .8, 'session_id': None, 'followup_complete': True})
            if '/diagnose' in url:
                return httpx.Response(200, json={'disease': 'Brown Spot', 'confidence': .8, 'session_id': 'session-one', 'followup_question': 'Question'})
            if '/detect' in url:
                return httpx.Response(200, json={'prediction': 'Rice bug', 'confidence': .9, 'status': 'known', 'quality': {'passed': True}})
            return httpx.Response(200, json={'session_id': 'session-one', 'reply': 'Advice'})
    monkeypatch.setattr(httpx, 'AsyncClient', Client)
    return TestClient(app), calls


@pytest.mark.parametrize('path', ['/api/v1/users/me/avatar', '/api/v1/feedback/mine', '/api/v1/admin/activity'])
def test_raw_proxy_preserves_auth_query_content(proxy, path):
    client, calls = proxy
    response = client.get(path, headers={'Authorization': 'Bearer token'}, params={'limit': 2, 'module': 'PEST'})
    assert response.status_code == 200 and response.content == b'binary-avatar'
    assert response.headers['content-type'] == 'image/jpeg'
    call = calls[-1]
    assert call[2]['headers']['authorization'] == 'Bearer token'
    assert ('limit', '2') in call[2]['params']
    assert '/internal/' not in call[1]


def test_avatar_multipart_and_delete(proxy):
    client, calls = proxy
    client.post('/api/v1/users/me/avatar', files={'avatar': ('photo.png', b'contents', 'image/png')})
    call = calls[-1]
    assert 'multipart/form-data' in call[2]['headers']['content-type']
    assert b'name="avatar"' in call[2]['content']
    assert client.post('/api/v1/internal/activity', json={}).status_code == 404
    client.delete('/api/v1/admin/feedback/id', params={'confirm': 'id'})
    assert calls[-1][0] == 'DELETE' and ('confirm', 'id') in calls[-1][2]['params']


@pytest.mark.parametrize('field', ['image', 'file'])
def test_pest_compatible_fields(proxy, field):
    client, calls = proxy
    assert client.post('/api/v1/pest/detect', files={field: ('pest.png', b'image', 'image/png')}).status_code == 200
    call = calls[-1]
    assert set(call[2]['files']) == {'file'}
    assert call[2]['files']['file'][1] == b'image'
    assert any(c[0] == 'timeout' and c[1]['timeout'] == 60 for c in calls)


def test_pest_ambiguous_fields(proxy):
    client, _ = proxy
    assert client.post('/api/v1/pest/detect', files={'image': ('a.png', b'a'), 'file': ('b.png', b'b')}).status_code == 422


def test_voice_session_and_event(proxy, monkeypatch):
    client, calls = proxy
    monkeypatch.setenv('INTERNAL_ACTIVITY_KEY', 'private-service-key')
    headers = {'Authorization': 'Bearer token', 'X-Request-ID': '92f7b4bd-9c0b-4e6b-b042-8d4fbd244002'}
    result = client.post('/api/v1/voice/diagnose', headers=headers, files={'audio': ('voice.wav', b'audio', 'audio/wav')})
    assert result.json()['session_id'] == 'session-one'
    upstream = next(c for c in calls if c[0] == 'POST' and c[1].endswith('/diagnose'))
    assert upstream[2]['files']['audio'][1] == b'audio'
    assert any(c[0] == 'timeout' and c[1]['timeout'] == 600 for c in calls)
    event = calls[-1][2]
    assert event['json']['event_type'] == 'VOICE_DIAGNOSIS_COMPLETED'
    assert set(event['json']) == {'event_type', 'module', 'request_id'}
    payload = {'session_id': 'session-one', 'answer': 'yes'}
    response = client.post('/api/v1/voice/followup', headers=headers, json=payload)
    assert response.json()['followup_complete'] is True
    upstream = next(c for c in calls if c[0] == 'POST' and c[1].endswith('/followup'))
    assert upstream[2]['json'] == payload
    assert calls[-1][2]['json']['event_type'] == 'VOICE_FOLLOWUP_COMPLETED'


def test_leaf_adapter_preserves_fields(proxy):
    client, calls = proxy
    client.post('/api/v1/image/classify', files={'image': ('leaf.png', b'leaf', 'image/png')}, data={'city': 'Galle'})
    forwarded = calls[-1]
    assert forwarded[1].endswith('/api/analyze')
    assert forwarded[2]['files']['file'][1] == b'leaf'
    assert forwarded[2]['files']['city'] == (None, 'Galle')


def test_treatment_passthrough(proxy):
    client, calls = proxy
    payload = {'message': 'Help', 'session_id': 'session-one'}
    assert client.post('/api/v1/chat/message', json=payload).json()['reply'] == 'Advice'
    assert calls[-1][2]['json'] == payload


@pytest.mark.parametrize('event,data,expected', [
    ('VOICE_DIAGNOSIS_COMPLETED', {'status': 'Audio quality check failed'}, False),
    ('VOICE_FOLLOWUP_COMPLETED', {'disease': 'Brown Spot', 'confidence': .5, 'followup_complete': False}, False),
    ('VOICE_FOLLOWUP_COMPLETED', {'disease': 'Brown Spot', 'confidence': .8, 'followup_complete': True}, True),
    ('LEAF_DIAGNOSIS_COMPLETED', {'prediction': {'status': 'KNOWN', 'prediction': 'Brown Spot', 'confidence': .9}}, True),
    ('LEAF_DIAGNOSIS_COMPLETED', {'error': 'duplicate_upload'}, False),
    ('PEST_DIAGNOSIS_COMPLETED', {'prediction': 'unknown', 'confidence': .1, 'status': 'unknown', 'quality': {'passed': False}}, False),
    ('TREATMENT_INTERACTION', {'detail': 'failed'}, False),
])
def test_only_confirmed_success(event, data, expected):
    assert confirmed(data, event) is expected


def test_event_network_failure_does_not_break_diagnosis(proxy, monkeypatch):
    client, _ = proxy
    monkeypatch.setenv('INTERNAL_ACTIVITY_KEY', 'key')
    original = httpx.AsyncClient.post
    async def post(self, url, **kwargs):
        if url.endswith('/internal/activity'):
            raise httpx.ConnectError('unreachable')
        return await original(self, url, **kwargs)
    monkeypatch.setattr(httpx.AsyncClient, 'post', post)
    assert client.post('/api/v1/voice/diagnose', headers={'Authorization': 'Bearer token'}, files={'audio': ('a.wav', b'a')}).status_code == 200


@pytest.mark.parametrize('status', [201, 204, 401, 403, 409, 422, 503])
def test_new_proxy_preserves_downstream_status(proxy, monkeypatch, status):
    client, _ = proxy
    async def response(self, *args, **kwargs):
        return httpx.Response(status, content=b'' if status == 204 else b'{"detail":"test"}', headers={'Content-Type': 'application/json'})
    monkeypatch.setattr(httpx.AsyncClient, 'request', response)
    result = client.get('/api/v1/feedback/mine')
    assert result.status_code == status
    if status == 204:
        assert result.content == b''


@pytest.mark.parametrize('status', [400, 500])
def test_downstream_failure_does_not_emit_activity(proxy, monkeypatch, status):
    client, calls = proxy
    monkeypatch.setenv('INTERNAL_ACTIVITY_KEY', 'key')
    async def response(self, *args, **kwargs):
        calls.append(('POST', args[0], kwargs))
        return httpx.Response(status, json={'detail': 'failed'})
    monkeypatch.setattr(httpx.AsyncClient, 'post', response)
    result = client.post('/api/v1/voice/diagnose', headers={'Authorization': 'Bearer token'}, files={'audio': ('a.wav', b'a')})
    assert result.status_code == status
    assert not any(call[0] == 'POST' and '/internal/activity' in call[1] for call in calls)
