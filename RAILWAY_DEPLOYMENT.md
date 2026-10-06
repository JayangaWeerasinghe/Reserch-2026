# PaddyGuard AI: GitHub and Railway deployment

## Architecture and scope

Your Railway project contains `gateway`, `voice_nlp`, `user_management`, and
Railway managed PostgreSQL. Deploy each service independently from this GitHub
monorepo using its Dockerfile and Root Directory below. Compose is local only;
do not deploy its PostgreSQL container to Railway. The frontend deploys separately
(e.g. Vercel). Leaf disease, pest detection, and treatment chatbot run in teammates'
separate Railway projects and must supply public HTTPS endpoints.

| Service | Root Directory | Healthcheck | Public domain |
| --- | --- | --- | --- |
| gateway | `/gateway` | `/health` | Yes |
| voice-nlp | `/voice_nlp` | `/health` | Unnecessary when only gateway calls it |
| user-management | `/user_management` | `/health` | Keep private |

Use the names `voice-nlp`, `user-management`, and `Postgres` below only if those
are your actual Railway service names. Railway service names and folder names
need not match. Do not override the Docker start command with a hardcoded port.
All Docker entry points listen on `0.0.0.0` and `${PORT:-<local default>}`.

## Exact Railway variables (placeholders only)

Choose explicit Railway `PORT` values for the private services so the referenced
ports are unambiguous. `PORT` overrides legacy `SERVICE_PORT`/`GATEWAY_PORT`.

Gateway:

```dotenv
PORT=8000
VOICE_NLP_URL=http://${{voice-nlp.RAILWAY_PRIVATE_DOMAIN}}:${{voice-nlp.PORT}}
USER_MGMT_URL=http://${{user-management.RAILWAY_PRIVATE_DOMAIN}}:${{user-management.PORT}}
LEAF_DISEASE_URL=https://<teammate-leaf-public-domain>
PEST_DETECTION_URL=https://<teammate-pest-public-domain>
TREATMENT_CHATBOT_URL=https://<teammate-treatment-public-domain>
ALLOWED_ORIGINS=https://<your-frontend>.vercel.app
JWT_SECRET=<strong-random-secret-shared-with-user-management>
```

Voice NLP:

```dotenv
PORT=8001
MODEL_PATH=models/paddyguard_best_classifier.pkl
TFIDF_PATH=models/paddyguard_tfidf.pkl
ASR_MODEL_ID=Lingalingeswaran/whisper-small-sinhala
ASR_BACKEND=hosted
HOSTED_ASR_URL=<compatible-provider-endpoint>
HOSTED_ASR_API_KEY=<secret-if-required-or-empty>
HOSTED_ASR_TIMEOUT_SECONDS=60
HOSTED_ASR_TEXT_FIELD=text
REDIS_URL=<your-external-redis-connection-url>
MONGO_URL=
ALLOWED_ORIGINS=https://<your-frontend>.vercel.app
RAILWAY_HEALTHCHECK_TIMEOUT_SEC=600
```

User management:

```dotenv
PORT=8005
POSTGRES_URL=${{Postgres.DATABASE_URL}}
USE_SQLITE=false
JWT_SECRET=<same-strong-random-secret-as-gateway>
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
ALLOWED_ORIGINS=https://<your-frontend>.vercel.app
```

Railway provides `DATABASE_URL` on the managed PostgreSQL service. Reference it
in user-management variables rather than committing an actual connection string.
Python resolves `POSTGRES_URL`, then `DATABASE_URL`; if neither is set, only
explicit `USE_SQLITE=true` enables local SQLite. Otherwise configuration fails.
Legacy `postgres://` URLs normalize to `postgresql://` for psycopg2. Connections
use `pool_pre_ping`, a five-second connection timeout, and initialization retries
five times with two-second waits. `create_all()` creates missing tables without
dropping existing data; it does not migrate existing schemas.

Reference variables above use Railway UI syntax, never Python interpolation.
Private networking is scoped to the same Railway project/environment. Keep HTTP
for these internal addresses and include the actual listening port. Generate a
public gateway domain and target port 8000. Teammate endpoints must be complete
public HTTPS base URLs, without the gateway `/api/v1` prefixes. Existing gateway
routes and forwarding paths are unchanged; trailing slashes are normalized.
See [Railway private domain/port references](https://docs.railway.com/networking/domains/working-with-domains).

## CORS, authentication and external services

Set `ALLOWED_ORIGINS` to comma-separated exact frontend origins (no trailing
slash), including a custom domain or local origin only when needed. Gateway
credentials are disabled for wildcard origins. Use explicit production origins.
Set the same strong JWT secret in gateway and user management; development
fallbacks and `change-me` examples are unsuitable for production.

Voice follow-up sessions require reachable Redis. Supply the existing external
Redis provider through `REDIS_URL`; an empty value is a template, not a working
configuration. Redis failures preserve existing non-fatal session behavior but
follow-ups cannot reliably work without session persistence. No cloud Redis
resource was created. The gateway rate-limiter module exists but is not wired
into `main.py` or the routers; set `REDIS_URL=<external-redis-url>` there if you
later enable that limiter. This deployment change does not enable middleware or
change authentication/rate-limit behavior.

`MONGO_URL` is optional. Unset/empty disables Voice Mongo logging. When configured,
connection/server-selection/socket timeouts are two seconds and logging remains
non-fatal. Diagnosis endpoints currently do not call this logger, so Mongo is not
required for API operation. Do not add a Railway Mongo service for optional logs.
Translation and gTTS require outbound network access; their existing fallbacks
and behavior remain intact. `TTS_ENGINE` exists in the local template but is not
read by the current gTTS implementation.

## CPU image, models and startup resources

Voice uses `python:3.11-slim`, ffmpeg, libsndfile1, and curl. PyTorch and torchaudio
are pinned to 2.5.1+cpu from the official CPU wheel index, with matching exact
requirements preventing a second CUDA install. Other runtime/research packages
are retained; the previously missing Motor dependency is declared.
See [official PyTorch CPU installation](https://docs.pytorch.org/get-started/previous-versions/).

Both trained classifier artifacts are present and intentionally allowed in Git:
`voice_nlp/models/paddyguard_best_classifier.pkl` and
`voice_nlp/models/paddyguard_tfidf.pkl`. They are small enough for ordinary Git;
no Git LFS configuration is needed. Docker includes them. See
[artifact instructions](voice_nlp/models/README.md). Their runtime compatibility
still requires actual model-loading tests; fake artifacts must never be generated.

For low-memory Railway, use `ASR_BACKEND=hosted`: local Whisper is never
imported, downloaded or loaded. Startup loads the classifier and validates the
hosted adapter; `/health` performs no external requests. Set a compatible hosted
endpoint and optional Bearer key in Railway Variables before redeployment.
See [Voice ASR modes and endpoint contract](voice_nlp/README.md).

`ASR_BACKEND=local` preserves the Sinhala Whisper research model but now loads
it lazily on first local transcription. Local first-use downloads and model
allocation can still cause latency or OOM in a 1 GB container. Hosted mode avoids
that allocation; scientific libraries, audio buffers and concurrent requests
still require measured memory validation. No hosted/local accuracy equivalence
is claimed. The existing Docker healthcheck grace period and Railway timeout
can remain configured; hosted startup does not wait for Whisper.

## Local development and Git safety

Keep every actual `.env` local. Copy the three service `.env.example` files and
supply local values. The existing user-management `.env` mistakenly contains
Voice variables; correct it locally from the new user-management example.
Use `USE_SQLITE=true` explicitly when running user management directly without
PostgreSQL. Example JWT secrets must be replaced for any exposed deployment.

Compose retains existing local service dependencies and volumes, removes Voice's
NVIDIA reservation, and sets user management to its local Postgres container.
Root shell/`.env` variables `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`,
and `JWT_SECRET` override harmless local defaults. Use URL-safe local database
credentials (percent-encode reserved URL characters if constructing a URL).
All existing service `.env` files are still needed by Compose. Redis remains an
external/local service configured through Voice `.env`. Compose GPU reservations
for Voice were removed to match the CPU image.

Root ignores cover all `.env*` except `.env.example`, SQLite databases, private
keys, Python/Node caches, downloaded model caches, datasets, generated leaf data,
and unrelated large model formats. Existing data and credentials were preserved.
Git status and tracked paths should be reviewed before committing. Actual `.env`
and database files are ignored and untracked in the current checkout. Inspect
staged filenames and diffs without pasting credentials; historical secret leakage
requires a separate history audit if the repository was previously published.


## Validation commands on a provisioned machine

```bash
python3 -m venv .venv
.venv/bin/pip install -r gateway/requirements.txt -r user_management/requirements.txt
(cd gateway && ../.venv/bin/python -m pytest tests)
(cd user_management && USE_SQLITE=true ../.venv/bin/python -m pytest tests)
# Voice has a different httpx pin; use a separate environment.
python3 -m venv voice_nlp/.venv
voice_nlp/.venv/bin/pip install -r voice_nlp/requirements.txt
(cd voice_nlp && .venv/bin/python -m pytest tests)
python3 -m compileall -q gateway voice_nlp user_management
docker build -t paddyguard-gateway ./gateway
docker build -t paddyguard-user-management ./user_management
docker build -t paddyguard-voice-nlp ./voice_nlp
```

This machine lacks Docker, pytest, pip, application dependencies and ensurepip;
unit-test attempts cannot collect tests, and image builds cannot run. Syntax and
standard-library configuration checks can run here. Network/download failures
must be distinguished from application failures. Validate `/health` against all
three running containers, PostgreSQL startup and authentication, and real Sinhala
audio/follow-up inference before accepting production deployment.
