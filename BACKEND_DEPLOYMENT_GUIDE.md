# PaddyGuard backend operator deployment guide

This change is local and uncommitted. No production migration, administrator provisioning, Atlas configuration, commit, push or deployment was performed. Operator actions below are manual. Keep the existing Gateway domain `https://gateway-production-3c64.up.railway.app` and frontend origin `https://research-2026-eta.vercel.app`. Use the existing User Management and Gateway Railway services; do not add services or a MongoDB container. Voice, Redis, Modal ASR and teammate services are unchanged.

## Inspection and implementation record

- Gateway entry point: `gateway/main.py`; routers: `gateway/router/{user,voice,image,pest,chat}.py`. User Management uses `USER_MGMT_URL`; all communication is HTTP via httpx.
- Identity entry point: `user_management/main.py`; auth routes: `/register`, `/login`, `/refresh`; old profile routes `/me` retained.
- PostgreSQL: `user_management/models/user.py`, SQLAlchemy `users` table. POSTGRES_URL takes precedence over DATABASE_URL. SQLite is only explicit local development mode. Existing startup `create_all` creates missing tables; it does not migrate existing tables.
- Existing password hashes use passlib bcrypt; existing JWT signing uses python-jose HS256 with `sub`, `type`, `exp`. Access-token role checks now load the active PostgreSQL identity. Existing hashes/IDs/tokens are not migrated into MongoDB.
- No prior User Management role field or migration tool exists in this checkout. Explicit additive SQL is introduced rather than an automatic migration framework. Other services have separate roles/accounts, which were not modified.
- No prior MongoDB configuration/driver in User Management. Teammate and Voice services have independent MongoDB usage; User Management can use the existing Atlas cluster with a dedicated database. Do not reuse another service's collections/schema.
- Dockerfiles retain their existing service roots and port entry points. Existing tests in gateway/user_management are retained and extended. Existing Railway guide is RAILWAY_DEPLOYMENT.md; inspect actual Railway service names instead of assuming folder names.
- Plan implemented: additive identity fields, secure CLI bootstrap, reusable RBAC, optional MongoDB, profiles/avatars, moderated feedback, admin views, activity ingestion/history, transparent Gateway forwarding, backward-compatible Pest upload, regression tests and frontend contract.

## Before migration: backup and inspect

Schedule the update in a controlled release window and record current deployment versions. Disable any automatic deployment trigger for this release while preparing the migration. Confirm the database is the existing PostgreSQL identity database. Check its users columns, account count and duplicate emails/roles without displaying password hashes. If a role column already exists, retain its values; do not demote Pest/staff/admin identities. Investigate any pre-existing nullable role/language columns before applying this migration: `ADD COLUMN IF NOT EXISTS` intentionally does not overwrite or repair existing columns.

Use a PostgreSQL client compatible with the server. Connect from an operator machine using the existing public database connection or an existing service shell over Railway's private network. Put the connection URI in a private shell variable `PADDYGUARD_PG_URL`; do not paste credentials into documentation or logs.

```bash
umask 077
pg_dump --dbname="$PADDYGUARD_PG_URL" --format=custom --file=paddyguard-before-profile.dump
pg_restore --list paddyguard-before-profile.dump
```

Store the backup encrypted outside the repository and verify a restore against an isolated test database. If using `railway run`, remember it injects env vars on your local machine; Railway private hostnames may not resolve there. Use a public operator connection or a shell in the existing deployed service for private URLs. No new Railway service is needed.

## Explicit PostgreSQL migration

Migration file: `user_management/migrations/001_profile_roles.sql`.

```bash
psql "$PADDYGUARD_PG_URL" -v ON_ERROR_STOP=1 -f user_management/migrations/001_profile_roles.sql
```

Apply first to a staging copy. The SQL runs inside a transaction and adds only:

| Column | Type / default |
|---|---|
| role | VARCHAR NOT NULL DEFAULT 'FARMER' |
| phone | nullable VARCHAR |
| district | nullable VARCHAR |
| preferred_language | VARCHAR NOT NULL DEFAULT 'si' |

It neither deletes/recreates users nor touches IDs, password hashes, email, account creation dates or existing roles. On an existing PostgreSQL table, the application cannot add columns by `create_all`; the operator must apply this SQL before deploying new User Management code. Verify account count and IDs are unchanged and new fields have the expected defaults. SQL uses IF NOT EXISTS for repeat execution; validate existing column definitions separately. Table schema locks are possible; use the planned release window.

## MongoDB Atlas

Use the existing Atlas cluster if available. Create a least-privileged database user scoped to the dedicated PaddyGuard database; it needs read/write and index creation on the three collections. Store the TLS Atlas SRV URI only in private User Management variables. Configure Atlas network access for the Railway deployment's actual egress arrangement. Prefer restricted egress allowlisting/private networking where available. Do not publish database credentials or print the URI.

Set MONGO_URL to the Atlas URI and MONGO_DB_NAME to a separate database such as `paddyguard`. Do not move PostgreSQL identities into Atlas. Test connectivity from the existing User Management service. No local MongoDB Railway deployment is required.

One pymongo client is created per process and closed at shutdown: pool maximum 20, server selection/connect timeout 2s, socket timeout 3s and pool queue timeout 2s. Index-recovery lock waits are bounded at 2s. Missing/bad MongoDB config is logged without credentials and does not prevent PostgreSQL authentication. Network/index availability errors return sanitized 503 for required MongoDB operations; audit/event writes only emit safe warnings. Monitor the User Management activity-write warnings and Gateway ingestion rejection/unavailability warnings. A 202 internal ingestion acknowledgement is best-effort acceptance, not a durable event receipt.

Indexes are idempotently created on startup, and retried on MongoDB operations after startup failure. Writes requiring indexes fail when index setup cannot complete; deduplication is not knowingly bypassed. Check index definitions in Atlas before enabling the feature. Pre-existing duplicates or conflicting indexes must be investigated manually; do not delete existing records automatically to make an index build pass.

| Collection | Index |
|---|---|
| feedback | default unique _id string UUID |
| feedback | user_id ascending, created_at descending |
| feedback | status, consent_public, rating ascending, created_at descending |
| activity_events | default unique _id string UUID |
| activity_events | user_id ascending, timestamp descending |
| activity_events | timestamp descending |
| activity_events | UNIQUE user_id, event_type, request_id ascending |
| profile_images | UNIQUE user_id ascending |

Feedback contains IDs referencing PostgreSQL users, text, rating, consent, moderation and timestamps. Profile images contain only one compressed JPEG and MIME per user. Activity contains enum event/module/status, timestamp, request ID and safe action metadata. It contains no passwords, JWTs, raw diagnosis media or conversations.

### Explicit retention policy

Default `ACTIVITY_RETENTION_DAYS=0`: no automated expiration. Changing this variable alone does not silently delete historical events. Choose a retention period, back up existing activity records and review the records older than that period before enabling it.

In an existing User Management service shell with its installed dependencies and private variables:

```bash
python configure_retention.py --confirm-expire-existing-events
```

This requires ACTIVITY_RETENTION_DAYS >= 1. It creates the named TTL index `activity_retention` on timestamp ascending or modifies that index's expiry. **Enabling TTL can expire existing old events immediately; backup/review is required.** It affects only activity_events. MongoDB expiration runs asynchronously; do not depend on precise-second deletion. To change retention, update the private variable and rerun the explicit command. Setting 0 does not remove a previously configured TTL index: an operator must explicitly drop `activity_retention` through Atlas or a privileged database shell to stop expiry. This task did not run the command or create a TTL index.

## Railway variables by service

Use actual existing Railway service names for variable references. Keep secrets in private Railway settings, not frontend envs or Git.

| Service | Variables |
|---|---|
| User Management | existing PORT (typically 8005), POSTGRES_URL or DATABASE_URL (existing PostgreSQL reference), USE_SQLITE=false, JWT_SECRET (existing strong signing secret), ACCESS_TOKEN_EXPIRE_MINUTES=30, REFRESH_TOKEN_EXPIRE_DAYS=7, ALLOWED_ORIGINS=https://research-2026-eta.vercel.app |
| User Management new | MONGO_URL, MONGO_DB_NAME=paddyguard, INTERNAL_ACTIVITY_KEY (random private shared secret), ACTIVITY_RETENTION_DAYS=0 unless explicitly enabled |
| Gateway | existing PORT, USER_MGMT_URL (existing private service domain plus its actual listening port), VOICE_NLP_URL, LEAF_DISEASE_URL, PEST_DETECTION_URL, TREATMENT_CHATBOT_URL, JWT_SECRET (existing convention), ALLOWED_ORIGINS=https://research-2026-eta.vercel.app |
| Gateway new | INTERNAL_ACTIVITY_KEY (same private secret as User Management) |
| Manual bootstrap only | ADMIN_BOOTSTRAP_EMAIL, ADMIN_BOOTSTRAP_PASSWORD, plus User Management DB variables |

Keep existing JWT_SECRET unchanged during this feature release to preserve issued tokens; never use `dev_secret`/`change-me` in production. Gateway's old JWT middleware exists but is not registered globally; new APIs rely on User Management's active-identity authorization. Do not enable global middleware for this release: Leaf staff tokens and guest AI routes have existing independent behavior. INTERNAL_ACTIVITY_KEY is only for Gateway ingestion and never used for ordinary login. Do not forward it to teammate inference services.

USER_MGMT_URL should use the existing Railway private domain/port. Avoid giving User Management a public domain; remove any unnecessary public ingress only after verifying existing callers. There is no Gateway forwarding route for `/internal/activity`; the endpoint additionally requires the internal key and a valid access token. Request payload cannot contain a user ID. The internal key is a trusted-service credential: anyone with it and a user's token can submit one of the permitted events; protect and rotate it as a service secret.

## Deploy User Management, then Gateway

After reviewed staging tests, backup and explicit production migration, manually deploy the existing User Management service with root `/user_management` and its unchanged Dockerfile. Dependencies add pymongo, Pillow and python-multipart. Existing startup does not provision an admin or enable retention. Check `/health`, existing farmer login/refresh, profile reads and startup index warnings. `/health` is liveness, not proof that Atlas is reachable; verify a protected MongoDB operation as well.

Then manually deploy the existing Gateway service with root `/gateway` and its unchanged Dockerfile. Keep the existing domain, service URLs and CORS origins. The default Gateway CORS includes the specified Vercel origin; if ALLOWED_ORIGINS is already set it takes precedence, so explicitly include that origin. Preserve existing Voice/Modal/Redis configuration. No inference service deployment is required.

Gateway profile/community forwarding preserves HTTP methods, query parameters, authorization, binary data and content types, without forwarding internal redirect URLs. Bodies are bounded at 2 MiB plus 64 KiB multipart overhead. Existing AI route timeout/multipart/session behaviors remain intact. Activity capture can add up to its bounded 2s ingestion timeout to a successful authenticated AI response.

## One-time System Admin bootstrap

Only run after the migration with a specifically authorized administrator email. Choose a unique existing-account-free email and a password with 12+ characters, upper/lowercase, digit and symbol, at most 72 UTF-8 bytes. The command uses existing passlib bcrypt and creates one PostgreSQL SYSTEM_ADMIN. Existing active SYSTEM_ADMIN is a no-op and its password remains unchanged; an existing non-admin/inactive account is rejected without promotion. The unique email constraint prevents duplicate insertions. There is no startup bootstrap and no HTTP bootstrap endpoint.

Place temporary ADMIN_BOOTSTRAP_EMAIL / ADMIN_BOOTSTRAP_PASSWORD in private variables of the existing User Management service, then use its existing Railway service shell/SSH capability to run from `/app`:

```bash
python bootstrap_admin.py
```

Alternatively, with the exact same code/dependencies locally, use the existing selected Railway project/service environment and an operator-accessible PostgreSQL URL; `railway run python bootstrap_admin.py` must be run from `user_management` and only when injected database hostname is reachable. Prefer an existing service shell for private networking. Do not put a plaintext password on the command line or invoke bootstrap through the app start command.

Verify ordinary Gateway login and `/api/v1/users/me` returns SYSTEM_ADMIN, then verify a protected admin read. Remove ADMIN_BOOTSTRAP_PASSWORD immediately and remove ADMIN_BOOTSTRAP_EMAIL when no longer needed. These variables do not participate in login. This task did not provision any admin.

## Local validation and API smoke checks

Install dev dependencies in a temporary virtual environment (no production credentials):

```bash
python -m pip install -r user_management/requirements-dev.txt -r gateway/requirements.txt
(cd user_management && python -m pytest -q)
(cd gateway && python -m pytest -q)
python scripts/export_openapi.py
```

The two suites should be run in separate processes because the current service conventions use shared top-level names such as `main`, `models`, `routes` and `services`. Tests override SQLAlchemy with in-memory SQLite and MongoDB with mongomock; HTTP inference/proxy calls are mocked. No production connection/bootstrap is needed for them.

Manually smoke-test through the unchanged public Gateway after deployment, using designated test accounts and test feedback:

1. Existing farmer registration/login/refresh; GET users/me; confirm no password/hash fields. Farmer GET admin/overview must be 403; no-token profile/admin calls must be 401.
2. PATCH profile language/district, reload it, reject role/user-ID updates. Check a second farmer cannot read the first farmer's history/avatar.
3. Upload, replace, retrieve and delete avatar; verify authenticated JPEG, no public cached response, 404 when deleted, bad-file and >2MiB rejection.
4. Submit positive consented feedback and negative feedback; public testimonials must initially be empty for both. Admin approve consented positive feedback; check public fields and anonymity. Reject negative feedback and ensure it remains visible privately. Unpublish positive feedback and check public disappearance. Delete only the test item with explicit confirm=ID.
5. Admin farmer search/detail, feedback filters and dashboard counts must match real storage. Activity date/pagination filters must work.
6. Simulate MongoDB outage in staging: feedback/avatar/history fail clearly with 503; password login, profile text and diagnosis still work, logging failures appear in safe warnings.
7. Voice diagnose with an actual valid Sinhala audio file, confirm returned session/question is unchanged. Complete follow-up with the same session and existing answer schema; only final follow-up logs a completed event. Leave Modal/Redis settings unchanged.
8. Leaf classify with image and existing location/context fields; compare case/history endpoints and responses with the prior deployment. Leaf staff login/experts use their existing tokens; System Admin does not replace them.
9. Pest detect once using image, once using file, with a farmer bearer token and request UUID; results should match direct service. Both fields at once must return 422. Confirm direct Pest calls create no Gateway activity. Check failed quality inputs are not logged as completed successes.
10. Treatment message with existing session_id, then topics and session clear; compare response/session behavior. Only successful message output emits an interaction event.
11. Retry an AI call with the same X-Request-ID UUID; only one activity event for the same user/type/ID. This is event deduplication, not inference deduplication. Anonymous requests do not create a farmer event.
12. Verify browser preflight from the deployed Vercel origin, Authorization propagation and no internal Railway URLs in new proxy errors. Do not log bearer tokens during checks.

For illustrative curl commands, use private shell variables and designated staging accounts:

```bash
curl --fail-with-body https://gateway-production-3c64.up.railway.app/health
curl --fail-with-body -H "Authorization: Bearer $PADDYGUARD_ACCESS_TOKEN" https://gateway-production-3c64.up.railway.app/api/v1/users/me
curl --fail-with-body -H "Authorization: Bearer $PADDYGUARD_ACCESS_TOKEN" -F 'avatar=@example.png;type=image/png' https://gateway-production-3c64.up.railway.app/api/v1/users/me/avatar
curl --fail-with-body -H "Authorization: Bearer $PADDYGUARD_ACCESS_TOKEN" -F 'file=@pest.jpg;type=image/jpeg' https://gateway-production-3c64.up.railway.app/api/v1/pest/detect
```

## Rollback

Redeploy the previously recorded Gateway and User Management versions. Keep the additive PostgreSQL columns and MongoDB data so rollback does not destroy farmer data; the old application ignores extra columns. Do not drop users, roles, collections or restore a full backup over live writes as a routine code rollback. If migration transaction fails, stop deployment and investigate; ON_ERROR_STOP and the transaction prevent partial SQL additions in that invocation.

Disable the new Gateway integration by reverting its version if needed. Keep the service secret private; rotating it requires updating both services. If an opt-in TTL policy caused unwanted expiry, explicitly remove the TTL index and recover only affected events from the reviewed backup; expired data cannot be restored merely by redeploying. Restoring PostgreSQL requires a separate reviewed incident procedure and a maintenance window.

## Frontend handoff and remaining limits

Copy **FRONTEND_INTEGRATION_CONTRACT.md** and **GATEWAY_OPENAPI.json** to the separate frontend repository through its normal reviewed process. Communicate the actual backend deployment completion before frontend starts using these routes. Do not copy backend private env files. The frontend must use Gateway Pest uploads to gain trusted farmer activity, fetch current role via users/me, and fetch authenticated avatars as blobs.

Live PostgreSQL/Atlas migration, Atlas TTL behavior, production bootstrap, production CORS/private networking and real inference were not exercised here. Local tests cover affected services with isolated storage and mocked HTTP. Named testimonials, cross-account admin avatar retrieval, email/password edits and complete activity for direct teammate calls are not implemented. Activity/audit logging is best-effort rather than transactional with PostgreSQL/feedback writes. Offset pagination can shift during concurrent inserts. Existing separate Leaf/Pest staff identity systems are intentionally preserved.

## Executed validation (local, 2026-10-09)

- User Management regression suite: **26 passed** (includes original tests).
- Gateway regression suite: **36 passed** (includes original tests).
- Python compileall over gateway, user_management and scripts: passed.
- `git diff --check`: passed.
- Generated GATEWAY_OPENAPI.json: 56 paths, 24 schemas; checked avatar multipart schema, admin bearer security and exclusion of internal ingestion.

Test-client calls initially stalled in the sandbox event loop, including the untouched health route; the passing suites ran outside the sandbox with approved permission, still using in-memory/mock databases and downstream HTTP. Reported warnings are dependency/FastAPI lifecycle deprecations. Real Atlas, PostgreSQL migration and teammate inference suites are outside the exercised validation; no production smoke checks were executed.

## Files changed

| Change | File |
|---|---|
| Modified | `gateway/.env.example` |
| Modified | `gateway/main.py` |
| Modified | `gateway/router/chat.py` |
| Modified | `gateway/router/image.py` |
| Modified | `gateway/router/pest.py` |
| Modified | `gateway/router/voice.py` |
| Modified | `user_management/.env.example` |
| Modified | `user_management/main.py` |
| Modified | `user_management/models/user.py` |
| Modified | `user_management/requirements.txt` |
| Modified | `user_management/routes/auth.py` |
| Modified | `user_management/routes/profile.py` |
| Added | `BACKEND_DEPLOYMENT_GUIDE.md` |
| Added | `FRONTEND_INTEGRATION_CONTRACT.md` |
| Added | `GATEWAY_OPENAPI.json` |
| Added | `gateway/router/community.py` |
| Added | `gateway/services/activity.py` |
| Added | `gateway/tests/test_features.py` |
| Added | `scripts/export_openapi.py` |
| Added | `user_management/bootstrap_admin.py` |
| Added | `user_management/configure_retention.py` |
| Added | `user_management/migrations/001_profile_roles.sql` |
| Added | `user_management/requirements-dev.txt` |
| Added | `user_management/routes/community.py` |
| Added | `user_management/services/mongo.py` |
| Added | `user_management/services/security.py` |
| Added | `user_management/tests/conftest.py` |
| Added | `user_management/tests/test_features.py` |
