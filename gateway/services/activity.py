"""Best-effort server-confirmed events; never records request bodies or results."""
import logging
import os
from uuid import UUID, uuid4
import httpx
from router.user import USER_MGMT_URL

log = logging.getLogger(__name__)


def confidence(value):
    return type(value) in (int, float) and 0 <= value <= 1


def confirmed(data, event):
    if not isinstance(data, dict) or data.get('error') or data.get('detail'):
        return False
    if event.startswith('VOICE'):
        valid = isinstance(data.get('disease'), str) and bool(data['disease']) and confidence(data.get('confidence'))
        quality = data.get('audio_quality')
        if isinstance(quality, dict) and quality.get('passed') is False:
            return False
        if event == 'VOICE_FOLLOWUP_COMPLETED':
            return valid and data.get('followup_complete') is True
        return valid
    if event.startswith('LEAF'):
        prediction = data.get('prediction')
        return (isinstance(prediction, dict) and prediction.get('status') in {'KNOWN', 'UNCERTAIN', 'OOD'}
                and isinstance(prediction.get('prediction'), str) and bool(prediction['prediction'])
                and confidence(prediction.get('confidence')))
    if event.startswith('PEST'):
        return (isinstance(data.get('prediction'), str) and data.get('status') in {'known', 'maybe', 'unknown'}
                and confidence(data.get('confidence'))
                and isinstance(data.get('quality'), dict) and data['quality'].get('passed') is True)
    if event == 'TREATMENT_INTERACTION':
        return isinstance(data.get('reply'), str) and bool(data['reply']) and isinstance(data.get('session_id'), str)
    return False


async def observe(request, response, event):
    if not 200 <= response.status_code < 300:
        return
    try:
        data = response.json()
    except ValueError:
        return
    if not confirmed(data, event):
        return
    auth = request.headers.get('authorization')
    if not auth:
        return  # Preserve guest routes; never invent a farmer identity.
    key = os.getenv('INTERNAL_ACTIVITY_KEY')
    if not key:
        log.warning('Activity capture disabled: INTERNAL_ACTIVITY_KEY not configured')
        return
    try:
        request_id = str(UUID(request.headers.get('x-request-id', '')))
    except ValueError:
        request_id = str(uuid4())
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            result = await client.post(f'{USER_MGMT_URL}/internal/activity',
                headers={'Authorization': auth, 'X-Internal-Activity-Key': key},
                json={'event_type': event, 'module': event.split('_')[0], 'request_id': request_id})
        if result.status_code != 202:
            log.warning('Activity ingestion rejected (status=%s)', result.status_code)
    except httpx.RequestError:
        log.warning('Activity ingestion unavailable')
