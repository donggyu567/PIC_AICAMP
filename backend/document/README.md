# PIC Masked STT Correction API

Android sends one already-masked utterance as an `application/json` POST body.
The server validates it, obtains or creates an LLM correction, builds the recent
conversation context, and stores both immutable results.

## Run

```powershell
python -m pip install -r requirements.txt
$env:OPENAI_API_KEY = "server-only-project-key"
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Optional settings:

```text
PIC_DATA_ROOT
PIC_CONTEXT_HISTORY_SIZE
OPENAI_MODEL
OPENAI_TIMEOUT_SECONDS
OPENAI_MAX_RETRIES
OPENAI_MAX_OUTPUT_TOKENS
```

## Endpoints

- `POST /api/v1/utterances`
- `GET /api/v1/conversations/{conversation_id}/context`
- `GET /health`
- `GET /docs`

The POST body must contain exactly:

```json
{
  "schema_version": "1.0",
  "conversation_id": "20260828_1430",
  "utterance_id": 1,
  "masked_text": "안녕하세요",
  "has_masked_data": false,
  "masked_types": []
}
```

`raw_text` is rejected. Until the Android NER implementation is added,
`masked_text` still contains the original recognized text and must be treated
as sensitive data.

## Storage

```text
backend/data/
├─ corrections/
│  └─ conversation-<sha256>/
│     └─ tuned_result0001.json
└─ contexts/
   └─ conversation-<sha256>/
      └─ context_result0001.json
```

For development, use one Uvicorn worker. Context is reconstructed from stored
snapshots, and per-conversation locks serialize requests inside that process.
