# Voice NLP: research ASR and low-memory deployment

## Research mode

`ASR_BACKEND=local` (default) uses the original
`Lingalingeswaran/whisper-small-sinhala` model, configurable through
`ASR_MODEL_ID`. Torch/Transformers imports and processor/model downloads occur
only at first local transcription, not application import or lifespan startup.
Initialization is protected by a lock and the successfully loaded pair is reused.
CPU is supported; CUDA remains supported where compatible local Torch is installed.
The deployment image installs CPU Torch. Local model startup and inference need
sufficient memory; a low-memory container can still OOM on its first local request.
For research warmup, `pipeline.asr.preload_asr()` is retained as an explicit helper.

## Railway low-memory mode

Set `ASR_BACKEND=hosted`. The hosted deployment adapter validates its configuration
at startup without an external request. It never imports Torch/Transformers,
instantiates Whisper, downloads its weights, or allocates local Whisper tensors.
The existing SVM and TF-IDF artifacts still load during startup. `/health` retains
its existing response and performs no ASR, Redis, Mongo, translation, or TTS work.

Hosted ASR is a deployment adaptation, not a replacement for the local research
model. WER/CER and downstream accuracy equivalence are not established. Evaluate
and record hosted performance separately from local Whisper research results.

The repository does not verify provider-level model support. Groq may or may not
accept `Lingalingeswaran/whisper-small-sinhala` as a hosted model name; the code
keeps the value configurable but does not assume support. For the exact
Sinhala-specialized model, the safest and most reliable approach is to use the local
lazy-load backend for research and to route production to a hosted provider only
after the provider explicitly confirms model compatibility.

### Hosted endpoint contract

The configured endpoint must accept `POST` multipart audio under the field
`file`. The hosted adapter sends the audio with the original filename and a safe
MIME type, and it closes the file handle promptly after the request. The existing
`/diagnose` temporary file is removed in its `finally` block. No retained audio
copy is created.

For Groq/OpenAI-compatible transcription, the adapter sends the following form
fields alongside the uploaded audio:

```text
file=<audio>
model=whisper-large-v3
language=si
response_format=json
```

`HOSTED_ASR_MODEL`, `HOSTED_ASR_LANGUAGE`, and `HOSTED_ASR_RESPONSE_FORMAT`
remain configurable through environment variables, while `HOSTED_ASR_TEXT_FIELD`
keeps the generic top-level response parsing. The endpoint must return a 2xx JSON
object with a top-level string field such as:

```json
{"text": "Sinhala transcription"}
```

`HOSTED_ASR_API_KEY` is optional and is sent as `Authorization: Bearer <key>`
when configured. Empty values omit that header. Keep credentials in Railway
Variables and use HTTPS for external production endpoints. Configuration errors
are mode-aware: hosted URL must be valid HTTP(S), timeout positive and finite,
text field nonempty, model nonempty, and local mode does not require hosted
settings.

Timeouts yield HTTP 504, network failures 503, and unsuccessful/malformed hosted
responses 502, with safe `detail` messages that omit provider diagnostics and
response bodies. Empty transcription preserves the existing HTTP 400 behavior.
`HOSTED_ASR_TIMEOUT_SECONDS` is the HTTPX per-operation inactivity timeout, not
an overall wall-clock deadline. No retry or fallback to local Whisper occurs.
See [HTTPX timeouts](https://www.python-httpx.org/advanced/timeouts/).

The public gateway still sends multipart `audio` to `/diagnose`; the internal
hosted adapter sends `file` to the configured external endpoint. `/followup`,
response fields, labels, OOD/confidence thresholds, severity, session trajectory,
and TTS behavior are unchanged. Gateway changes required: No.

## Exact Railway configuration

Root Directory: `/voice_nlp`. Keep the Dockerfile command (one Uvicorn process),
healthcheck path `/health`, and its existing CPU-compatible image/audio packages.

```dotenv
PORT=8001
ASR_BACKEND=hosted
HOSTED_ASR_URL=<compatible-provider-endpoint>
HOSTED_ASR_API_KEY=<secret-if-required-or-empty>
HOSTED_ASR_TIMEOUT_SECONDS=60
HOSTED_ASR_TEXT_FIELD=text
MODEL_PATH=models/paddyguard_best_classifier.pkl
TFIDF_PATH=models/paddyguard_tfidf.pkl
REDIS_URL=<existing-external-redis-url>
MONGO_URL=
ALLOWED_ORIGINS=https://<frontend-domain>
```

`ASR_MODEL_ID` is unused in hosted mode; keep its default for local research.
Do not copy `.env` into Git or paste credentials into chat. Set these variables
on the Voice Railway service before redeploying the reviewed commit. A real
compatible hosted endpoint is required; this repository does not invent one.
Keep gateway's existing Voice URL and actual internal listening port aligned.
Docker listens on `0.0.0.0:${PORT:-8001}`. Python direct execution preserves
`PORT -> SERVICE_PORT -> 8001`. No reload or additional workers are enabled.
Check deployment logs for `[asr] backend=hosted`, successful classifier loading,
and healthy `/health`, then test one diagnosis through the gateway.

## Classifier compatibility and remaining memory risks

The two existing artifacts contain `_sklearn_version` markers for **1.6.1**.
Requirements now pin `scikit-learn==1.6.1` instead of 1.5.2; no retraining, pickle
modification or warning suppression was performed. Full load tests require the
installed scientific runtime. See [scikit-learn persistence guidance](https://scikit-learn.org/stable/model_persistence.html).

Translation imports its existing `translators` client only when translating.
TTS uses gTTS; neither creates a local transformer or Torch model at startup.
The audio quality gate still uses librosa/NumPy, and classification uses
scikit-learn/SciPy. Those dependencies and decoded audio/request buffers consume
memory even in hosted mode. Full Torch/Transformers packages remain installed
in the image for local support but are not imported by hosted ASR. Peak memory
under 1 GB has not been measured or guaranteed. Large/concurrent uploads and
scientific-library initialization may still exceed the limit.

Redis remains required for persistent follow-ups, with existing failure behavior.
Mongo stays optional and does not become a startup requirement. Hosted ASR,
translation and gTTS need network access; external availability, latency and any
provider charges remain deployment concerns. No paid endpoint is called in tests.

## Offline validation

From `voice_nlp/`:

```bash
python3 -m unittest discover -s tests -p test_asr_backends.py -v
python3 -m pytest tests/test_asr_backends.py tests/test_hosted_startup.py
python3 -m pytest tests
python3 -m compileall -q .
```

The standard-library adapter suite runs without installed runtime packages.
Full startup/health, model-loading and endpoint compatibility tests require
service dependencies. They mock external inference, TTS and endpoint session
needs, block Torch/Transformers imports in hosted startup, and make no hosted
ASR requests. The existing `test_followup_ood` now supplies an offline session fixture and
mocks Redis deletion/TTS, so it exercises the intended OOD branch without
network access. The API still returns 404 for a missing session.

On this editing machine: 15 adapter tests passed and syntax checks passed. Full
pytest and actual application import were blocked by missing pytest/FastAPI and
other dependencies; model deserialization could not run. Docker is unavailable.
Use the installed Railway image or a provisioned local environment for full
runtime validation and `pip check` before accepting deployment.
