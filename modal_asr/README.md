# Modal ASR proof-of-concept for Sinhala Whisper Small

This isolated service is intentionally separate from the Railway voice-nlp deployment.
It proves that the Sinhala-specialized model can run in a dedicated Modal container
without changing the current Railway/Groq production configuration.

## Model

- `Lingalingeswaran/whisper-small-sinhala`

## Deployment

From the repository root:

```bash
~/.local/bin/modal deploy modal_asr/app.py
```

Before deploying the HTTP endpoint, create a Modal Secret named
`paddyguard-modal-asr-auth` containing the key `PADDYGUARD_ASR_API_KEY`.
Create it in the Modal dashboard under **Secrets**; enter the secret value there
and never commit it or paste it into chat. The deployed ASGI function exposes
`POST /listen`. Modal's deploy output provides the HTTPS function URL; append
`/listen` to that URL for the endpoint.

The endpoint requires `Authorization: Bearer <shared-secret>` and accepts
multipart form data with `file`, plus optional `model`, `language`, and
`response_format` fields. `model` is ignored; the server always uses the Sinhala
checkpoint configured below. `language` may be `si`, and `response_format` may
be `json`. Uploads are limited to 25 MiB and support OGG, WAV, MP3, M4A, and
WebM.

Example response:

```json
{
  "text": "<Sinhala transcript>",
  "model": "Lingalingeswaran/whisper-small-sinhala",
  "language": "si",
  "inference_seconds": 9.354
}
```

Safe request template (replace the placeholders locally):

```bash
curl -X POST "<modal-function-https-url>/listen" \
  -H "Authorization: Bearer <MODAL_ASR_API_KEY>" \
  -F "file=@/path/to/sample.ogg" \
  -F "model=Lingalingeswaran/whisper-small-sinhala" \
  -F "language=si" \
  -F "response_format=json"
```

The HTTP function and GPU transcription function both scale to zero. The GPU
function remains limited to one container and the persistent model cache remains
mounted at `/model-cache`.

## Local smoke test

Use a local Sinhala audio file, for example:

```bash
~/.local/bin/modal run modal_asr/app.py --audio-path /path/to/sample.ogg
```

## HTTP endpoint

The deployed endpoint accepts multipart form data with a field named `file`.

Example:

```bash
curl -X POST "<deployed-url>" \
  -F "file=@/path/to/sample.ogg"
```

Expected JSON:

```json
{
  "text": "<Sinhala transcript>",
  "model": "Lingalingeswaran/whisper-small-sinhala",
  "language": "si",
  "inference_seconds": 3.42
}
```

## Notes

- The model is loaded once per warm container.
- A persisted volume is used for the Hugging Face cache.
- Railway voice_nlp remains unchanged at this stage.
- No credentials are committed to the repository.
