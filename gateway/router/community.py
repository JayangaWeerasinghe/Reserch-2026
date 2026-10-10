"""Transparent forwarding of User Management API; no public internal ingestion route."""
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import Response
import httpx
from router.user import USER_MGMT_URL

router = APIRouter()


async def forward(request: Request, path: str):
    headers = {key: request.headers[key] for key in ('authorization', 'content-type', 'accept') if key in request.headers}
    # Enforce avatar size before buffering a raw multipart body.
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 2 * 1024 * 1024 + 65536:
            raise HTTPException(413, 'Request exceeds upload limit')
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(request.method, f'{USER_MGMT_URL}{path}',
                params=request.query_params.multi_items(), headers=headers, content=bytes(body))
        safe_headers = {key: value for key, value in response.headers.items()
                        if key.lower() in {'content-type', 'cache-control', 'x-content-type-options', 'www-authenticate'}}
        return Response(response.content, status_code=response.status_code, headers=safe_headers)
    except httpx.TimeoutException:
        raise HTTPException(504, 'User management service timed out')
    except httpx.RequestError:
        raise HTTPException(503, 'User management service unavailable')


@router.get('/users/me')
@router.patch('/users/me')
async def profile(request: Request):
    return await forward(request, '/me')


@router.get('/users/me/avatar')
@router.post('/users/me/avatar')
@router.delete('/users/me/avatar')
async def avatar(request: Request):
    return await forward(request, '/me/avatar')


@router.post('/feedback')
@router.get('/feedback/mine')
@router.get('/testimonials')
@router.get('/activity/me')
@router.get('/admin/overview')
@router.get('/admin/farmers')
@router.get('/admin/feedback')
@router.get('/admin/activity')
async def community(request: Request):
    return await forward(request, request.url.path.removeprefix('/api/v1'))


@router.get('/admin/farmers/{user_id}')
async def farmer(request: Request, user_id: str):
    return await forward(request, '/admin/farmers/' + user_id)


@router.patch('/admin/feedback/{feedback_id}')
@router.delete('/admin/feedback/{feedback_id}')
async def moderation(request: Request, feedback_id: str):
    return await forward(request, '/admin/feedback/' + feedback_id)
