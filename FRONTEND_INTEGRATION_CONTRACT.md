# PaddyGuard backend integration contract

Implementation status: local backend code, not deployed by this task. The production service will expose these changes only after the operator follows BACKEND_DEPLOYMENT_GUIDE.md. All examples below are illustrative, not production records.

Production Gateway base URL: **https://gateway-production-3c64.up.railway.app**

Production frontend origin: **https://research-2026-eta.vercel.app**

Do not call User Management directly. Paths below are relative to the Gateway base URL. Existing AI routes remain available; no frontend source was changed.

## Authentication and roles

Use `Authorization: Bearer <access_token>` for every protected call. Access tokens and refresh tokens are distinct. Never send the refresh token as the bearer access token. An inactive/deleted account is rejected by User Management. Role checks load PostgreSQL identity on each protected request; frontend role claims cannot grant access.

System Admin uses the ordinary login endpoint. Fetch `/api/v1/users/me` after login to determine the authoritative `role`. Roles currently introduced here are `FARMER` (existing accounts when the role column is added) and `SYSTEM_ADMIN`. Existing roles are retained if the column already exists. Pest and Leaf staff identities/tokens remain separate; they are not System Admin credentials. Do not infer role from an email or frontend stored credentials. There is no public admin registration/bootstrap endpoint.

| Method | Path | Authentication / role | Request | Success response |
|---|---|---|---|---|
| POST | /api/v1/auth/register | Public; always creates FARMER | RegisterRequest | 201 TokenResponse |
| POST | /api/v1/auth/login | Public; farmer or admin credentials | LoginRequest | 200 TokenResponse |
| POST | /api/v1/auth/refresh | Public endpoint, valid refresh token required | RefreshRequest | 200 TokenResponse |
| GET | /api/v1/users/me | Active access-token identity | None | 200 ProfileResponse |
| PATCH | /api/v1/users/me | Active access-token identity | ProfileUpdateRequest | 200 ProfileResponse |
| GET, PATCH | /api/v1/auth/me | Same; retained compatibility alias | Same as users/me | 200 ProfileResponse |
| POST | /api/v1/users/me/avatar | Active access-token identity | Multipart avatar | 200 AvatarResponse |
| GET | /api/v1/users/me/avatar | Active access-token identity | None | 200 binary JPEG; 404 if absent |
| DELETE | /api/v1/users/me/avatar | Active access-token identity | None | 204 empty; idempotent |
| POST | /api/v1/feedback | FARMER | FeedbackRequest | 201 FeedbackResponse |
| GET | /api/v1/feedback/mine | Active access-token identity | Pagination | 200 FeedbackPage |
| GET | /api/v1/testimonials | Public | Pagination | 200 TestimonialPage |
| GET | /api/v1/activity/me | Active access-token identity; own events only | Activity filters | 200 ActivityPage |
| GET | /api/v1/admin/overview | SYSTEM_ADMIN | None | 200 OverviewResponse |
| GET | /api/v1/admin/farmers | SYSTEM_ADMIN | Pagination, search | 200 FarmerPage |
| GET | /api/v1/admin/farmers/{user_id} | SYSTEM_ADMIN | None | 200 ProfileResponse; 404 missing/non-farmer |
| GET | /api/v1/admin/feedback | SYSTEM_ADMIN | Pagination, feedback filters | 200 FeedbackPage |
| PATCH | /api/v1/admin/feedback/{feedback_id} | SYSTEM_ADMIN | ModerationRequest | 200 FeedbackResponse |
| DELETE | /api/v1/admin/feedback/{feedback_id} | SYSTEM_ADMIN | Query confirm={feedback_id} | 204 empty; 404 missing |
| GET | /api/v1/admin/activity | SYSTEM_ADMIN | Pagination, activity filters, user_id | 200 ActivityPage |

### JSON schemas

Exact machine-readable types, constraints, query parameters and response models for the new APIs are in **GATEWAY_OPENAPI.json**, generated from both actual FastAPI apps. Regenerate with `python scripts/export_openapi.py` in an environment with both requirements sets installed. It enriches the Gateway's transparent proxy operations using User Management schemas and omits internal ingestion. The live `/openapi.json` and `/docs` are also available at the Gateway, but raw proxy operations in the live schema have generic bodies/responses; use the checked-in enriched schema for frontend code generation.

Schema notation: `?` means optional, `| null` means nullable. Dates are ISO 8601; activity queries must include a timezone. IDs are opaque strings. Profile emails are read-only in this API; no email/password change workflow is introduced.

```text
RegisterRequest = {email: email-string, password: string (>=8 chars, <=72 UTF-8 bytes), full_name?: string|null (1..120 chars)}
LoginRequest = {email: email-string, password: string}
RefreshRequest = {refresh_token: string}
TokenResponse = {access_token: string, refresh_token: string, token_type: "bearer"}
ProfileUpdateRequest = {
  full_name?: string|null (trimmed, 1..120 chars, no control characters),
  phone?: string|null (7..24 digits/spaces/parentheses/hyphens, optional initial +),
  district?: string|null (trimmed, 1..80 chars, no control characters),
  preferred_language?: "si"|"en"
}
ProfileResponse = {
  id: string, email: string, full_name: string|null, phone: string|null,
  district: string|null, preferred_language: "si"|"en", role: string,
  created_at: datetime, is_active: boolean,
  avatar_url: "/api/v1/users/me/avatar"
}
AvatarResponse = {avatar_url: "/api/v1/users/me/avatar"}
FeedbackRequest = {rating: integer (1..5), category: Category,
  message: string (trimmed, 1..2000 chars), consent_public?: boolean (default false)}
FeedbackResponse = {id: string, user_id: string, rating: integer, category: Category,
  message: string, consent_public: boolean, status: ModerationStatus,
  created_at: datetime, updated_at: datetime, moderated_by: string|null}
ModerationRequest = {status: ModerationStatus}
TestimonialResponse = {id: string, rating: integer, category: Category,
  message: string, created_at: datetime, display_label: "Anonymous farmer"}
ActivityResponse = {id: string, user_id: string, event_type: EventType,
  module: Module, status: "SUCCESS", timestamp: datetime, request_id: string, metadata: object}
Page<T> = {items: T[], total: integer, offset: integer, limit: integer}
FeedbackPage = Page<FeedbackResponse>
TestimonialPage = Page<TestimonialResponse>
ActivityPage = Page<ActivityResponse>
FarmerPage = Page<ProfileResponse>
OverviewResponse = {farmers: integer, active_farmers: integer, feedback: integer,
  pending_feedback: integer, testimonials: integer, activity_events: integer}
Category = "VOICE"|"LEAF"|"PEST"|"TREATMENT"|"GENERAL"
ModerationStatus = "PENDING"|"APPROVED"|"REJECTED"|"UNPUBLISHED"
```

Profile updates, feedback submissions, moderation and registration reject unknown fields. Do not supply user ID, role, password hash or status through profile/feedback forms. Profile PATCH updates only supplied fields; nullable fields accept null to clear them. Role is returned for navigation but checked again on the server for authorization.

`avatar_url` is an authenticated self-avatar reference, not a promise that an image exists. For admin farmer-detail responses it does not reference that farmer's image. Admin viewing of another user's avatar is NOT IMPLEMENTED. Avatar existence can be determined with GET (404 means no avatar). Do not embed JWTs in image URLs. Fetch with the bearer header, convert the response to a Blob URL and revoke the Blob URL when finished.

### Avatar uploads

Use multipart field **avatar**, MIME `image/jpeg`, `image/png`, or `image/webp`. Actual bytes are decoded and validated. Maximum input is **2 MiB**. Invalid files/decompression bombs return 422; unsupported MIME returns 415; oversized uploads return 413. Images are resized to fit 512×512, converted to metadata-free JPEG, and bounded below 200 KiB. A replacement overwrites the one image for that user. Retrieval is `image/jpeg` with `Cache-Control: private, no-store`; delete returns an empty 204. Normal profile JSON and JWTs contain no image bytes. MongoDB is required for image operations.

### Pagination and filters

All list endpoints: `offset=0` by default (0..100000), `limit=20` by default (1..100), response `{items,total,offset,limit}`. Feedback/testimonials sort newest created first; activity sorts newest timestamp first. IDs break equal-timestamp ties. Farmer list sorts newest account creation first.

- `/admin/farmers`: `search` up to 120 characters, case-insensitive literal substring of full name/email.
- `/admin/feedback`: optional `status`, `category`, `rating` (1..5), `user_id`.
- `/activity/me`: optional `event_type`, `module`, `since`, `until`; timezone-aware ISO 8601 dates, inclusive range. No user selection; identity comes from the token.
- `/admin/activity`: same filters plus `user_id`.

### Moderation

Every feedback starts PENDING. No automatic publication. Valid transitions:

| Current | Allowed next |
|---|---|
| PENDING | APPROVED, REJECTED |
| APPROVED | UNPUBLISHED, REJECTED |
| REJECTED | PENDING |
| UNPUBLISHED | APPROVED, REJECTED |

APPROVED requires rating 4–5 and `consent_public=true`. Invalid transitions or concurrent modifications return 409. Negative feedback remains stored for private review, including after rejection. Public testimonials expose only the listed public fields, always with an anonymous label. Named testimonials are NOT IMPLEMENTED; there is no separate name-consent field. Admin must review message contents before publication because free text can contain identifying information supplied by the farmer.

Deletion requires `?confirm=<exact feedback ID>` and SYSTEM_ADMIN. The confirmation is required backend semantics; the frontend should present a confirmation dialog before sending it. Metadata records feedback ID, moderator ID, previous/new statuses where applicable, without feedback message contents. Audit writes are best-effort.

### Activity event names

| Event type | Module | Recorded when |
|---|---|---|
| LOGIN | AUTH | Password login succeeds |
| PROFILE_UPDATED | PROFILE | PostgreSQL profile update commits |
| AVATAR_UPDATED / AVATAR_DELETED | PROFILE | MongoDB avatar operation succeeds |
| FEEDBACK_SUBMITTED | FEEDBACK | MongoDB feedback insert succeeds |
| VOICE_DIAGNOSIS_COMPLETED | VOICE | Gateway receives valid diagnosis output (may start a follow-up session) |
| VOICE_FOLLOWUP_COMPLETED | VOICE | Valid final follow-up output has followup_complete=true |
| LEAF_DIAGNOSIS_COMPLETED | LEAF | Gateway receives valid prediction status |
| PEST_DIAGNOSIS_COMPLETED | PEST | Gateway receives prediction and passed quality check |
| TREATMENT_INTERACTION | TREATMENT | Gateway receives a nonempty reply/session ID |
| FEEDBACK_MODERATED / FEEDBACK_DELETED | ADMIN | Admin mutation succeeds |

All stored events currently have status **SUCCESS**, meaning the operation completed; it does not imply a confident diagnosis. OOD/uncertain outputs may be completed operations. Invalid audio, HTTP errors, malformed downstream responses and incomplete Voice follow-up steps do not produce completed events. FAIL/PENDING event statuses are NOT IMPLEMENTED.

Send a fresh UUID in `X-Request-ID` for an AI operation; reuse that UUID when retrying the same operation. Gateway generates one when absent/invalid. MongoDB deduplicates `(user_id,event_type,request_id)`. This deduplicates activity records, not the AI service's execution. Public clients cannot submit activity records. Guest AI requests remain supported but produce no farmer event. Activity logging is best-effort; diagnosis succeeds even if logging is unavailable. Do not use activity records as diagnosis results: existing Leaf cases/history and Voice session behavior remain separate and unchanged.

### Existing AI proxy contracts and Pest adapter

| Method / Gateway path | Downstream | Request / behavior |
|---|---|---|
| POST /api/v1/voice/diagnose | Voice /diagnose | Multipart audio; 600s timeout; response/session unchanged |
| POST /api/v1/voice/followup | Voice /followup | Existing JSON session_id and answer contract; 30s timeout |
| POST /api/v1/image/classify | Leaf /api/analyze | Multipart image; mapped to file; other form fields preserved; 120s timeout |
| POST /api/v1/pest/detect | Pest /detect | Multipart **image OR file**, exactly one; forwarded as file; 60s timeout |
| POST /api/v1/chat/message | Treatment /chat | Existing JSON message, session_id; 60s timeout |
| GET /api/v1/chat/topics | Treatment /chat/topics | Existing response unchanged |
| DELETE /api/v1/chat/session/{session_id} | Treatment /chat/session/{session_id} | Existing response unchanged |

Existing Leaf cases, user history, staff authentication and expert/admin proxy routes are retained. Leaf uses its own staff/user token system; this task does not reconcile Leaf accounts with PostgreSQL farmers. Primary bearer tokens are forwarded for Leaf's existing behavior and separately verified by User Management for activity ingestion. Direct Pest frontend calls bypass Gateway and cannot generate trustworthy PostgreSQL farmer activity. To enable Pest activity, switch its detection call to the Gateway URL above and send the farmer's access token plus optional request UUID. Neither Pest inference nor its staff admin system was changed. Direct calls to any teammate service remain outside this activity capture.

### Errors

Typical error: `{"detail":"System Admin role required"}`. Validation errors use FastAPI's `{"detail":[{"type":"...","loc":["body","rating"],"msg":"...","input":0,...}]}` format. Handle either string or array `detail`. Retained AI proxy endpoints may return their service's original error shape (for example Leaf `error/message`); do not assume all teammate errors share the new API format.

401 missing/invalid/expired/wrong-type token or inactive identity; 403 wrong role/internal credential; 404 absent resource; 409 duplicate email/invalid moderation/conflict; 413 request/upload too large; 415 unsupported avatar MIME; 422 validation; 503 storage/service unavailable; 504 downstream timeout. Feedback writes return 503 when MongoDB cannot persist, never a fabricated success. Dashboard returns 503 if MongoDB counts cannot be obtained, rather than showing zero fabricated counts. PostgreSQL login/profile text still work during MongoDB outages.

### Example requests and responses (illustrative)

```http
POST /api/v1/auth/login
Content-Type: application/json

{"email":"admin@example.com","password":"example-only-secret"}
```

```json
{"access_token":"<access JWT>","refresh_token":"<refresh JWT>","token_type":"bearer"}
```

```http
PATCH /api/v1/users/me
Authorization: Bearer <access JWT>
Content-Type: application/json

{"district":"Galle","preferred_language":"en"}
```

```json
{"id":"b5af24c2-c4d7-44c9-9816-20642ac07896","email":"farmer@example.com","full_name":"Example Farmer","phone":null,"district":"Galle","preferred_language":"en","role":"FARMER","created_at":"2026-10-09T10:00:00Z","is_active":true,"avatar_url":"/api/v1/users/me/avatar"}
```

```http
POST /api/v1/feedback
Authorization: Bearer <access JWT>
Content-Type: application/json

{"rating":5,"category":"VOICE","message":"The Sinhala instructions were helpful.","consent_public":true}
```

```json
{"id":"6099c8a1-cfc2-4a1f-b39b-267dfc0a562b","user_id":"b5af24c2-c4d7-44c9-9816-20642ac07896","rating":5,"category":"VOICE","message":"The Sinhala instructions were helpful.","consent_public":true,"status":"PENDING","created_at":"2026-10-09T10:02:00Z","updated_at":"2026-10-09T10:02:00Z","moderated_by":null}
```

```http
PATCH /api/v1/admin/feedback/6099c8a1-cfc2-4a1f-b39b-267dfc0a562b
Authorization: Bearer <System Admin access JWT>
Content-Type: application/json

{"status":"APPROVED"}
```

```json
{"items":[{"id":"6099c8a1-cfc2-4a1f-b39b-267dfc0a562b","rating":5,"category":"VOICE","message":"The Sinhala instructions were helpful.","created_at":"2026-10-09T10:02:00Z","display_label":"Anonymous farmer"}],"total":1,"offset":0,"limit":20}
```

```json
{"items":[{"id":"42f96682-f399-44a2-9ac8-3d3948c9daa3","user_id":"b5af24c2-c4d7-44c9-9816-20642ac07896","event_type":"VOICE_DIAGNOSIS_COMPLETED","module":"VOICE","status":"SUCCESS","timestamp":"2026-10-09T10:01:00Z","request_id":"92f7b4bd-9c0b-4e6b-b042-8d4fbd244002","metadata":{}}],"total":1,"offset":0,"limit":20}
```

Browser avatar upload example:

```javascript
const form = new FormData();
form.append("avatar", selectedFile);
await fetch(`${gatewayBase}/api/v1/users/me/avatar`, {
  method: "POST", headers: {Authorization: `Bearer ${accessToken}`}, body: form
}); // Let the browser supply the multipart boundary.
```

## Environment and validation limits

Only the public Gateway base URL belongs in frontend configuration. Never expose MONGO_URL, POSTGRES_URL, JWT_SECRET, INTERNAL_ACTIVITY_KEY, or bootstrap variables through frontend env variables. Backend variables by service and operator procedures are in BACKEND_DEPLOYMENT_GUIDE.md.

User Management: POSTGRES_URL or DATABASE_URL, JWT_SECRET, MONGO_URL, MONGO_DB_NAME, INTERNAL_ACTIVITY_KEY; optional ACTIVITY_RETENTION_DAYS, ALLOWED_ORIGINS, token lifetimes. Gateway: existing service URL variables, INTERNAL_ACTIVITY_KEY, ALLOWED_ORIGINS. Bootstrap requires temporary ADMIN_BOOTSTRAP_EMAIL and ADMIN_BOOTSTRAP_PASSWORD only for the manual command.

Local tests use SQLite/mongomock and mocked HTTP services. Live PostgreSQL migration, Atlas connectivity/TTL, Railway private-network access, production bootstrap, deployed CORS and inference smoke tests have NOT been performed. Production provisioning/deployment is intentionally pending. No new Railway service is needed. No automatic migration, bootstrap, TTL expiration, commit, push or deployment occurs.
