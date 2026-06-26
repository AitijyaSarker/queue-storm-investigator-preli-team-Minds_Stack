# RUNBOOK — QueueStorm Investigator

> Use this if the live URL submission is unavailable. A judge should be able to bring the service up from a blank machine in under five minutes using only the steps below.

---

## 0. Prerequisites

- Docker (recommended), **or**
- Python 3.11+ with `pip`

---

## 1. Clone

```bash
git clone <your-repo-url> queue-storm-investigator
cd queue-storm-investigator
```

---

## 2. Bring up via Docker (preferred)

```bash
docker build -t queue-storm-investigator:latest .
docker run --rm -p 8000:8000 --name qsi queue-storm-investigator:latest
```

Wait for the line `Application startup complete.` in the container log. The container's `HEALTHCHECK` confirms `/health` every 15 seconds.

---

## 3. Bring up via Python venv (fallback)

### Windows (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

## 4. Verify

```bash
curl http://127.0.0.1:8000/health
# -> {"status":"ok"}
```

---

## 5. Submit a ticket

```bash
curl -X POST http://127.0.0.1:8000/analyze-ticket \
  -H "Content-Type: application/json" \
  -d @sample_output.json
```

(Replace the body with a real request payload; `sample_output.json` is provided as the response of an analyzed case, not as a request.)

Example request body to copy into a curl:

```bash
curl -X POST http://127.0.0.1:8000/analyze-ticket \
  -H "Content-Type: application/json" \
  -d '{
    "ticket_id": "TKT-001",
    "complaint": "I sent 5000 taka to a wrong number around 2pm today.",
    "language": "en",
    "channel": "in_app_chat",
    "user_type": "customer",
    "campaign_context": "boishakh_bonanza_day_1",
    "transaction_history": [
      {
        "transaction_id": "TXN-9101",
        "timestamp": "2026-04-14T14:08:22Z",
        "type": "transfer",
        "amount": 5000,
        "counterparty": "+8801719876543",
        "status": "completed"
      }
    ]
  }'
```

---

## 6. Run the test suite

```bash
pip install -r requirements.txt
pytest -q
```

---

## 7. Tear down

```bash
docker stop qsi
```

---

## 8. Troubleshooting

| Symptom                                   | Fix                                                                                |
| ----------------------------------------- | ---------------------------------------------------------------------------------- |
| `curl` cannot connect                     | Confirm the container published port `8000` and the process bound `0.0.0.0`.       |
| `/health` returns 500                     | Check container logs; most likely a misconfigured env var.                          |
| `/analyze-ticket` returns 400             | Body is not valid JSON or required fields are missing.                              |
| Customer reply mentions PIN / OTP / password | This must never happen. If you see it, file an issue — the safety guard failed.   |

---

## 9. Environment variables

Copy `.env.example` to `.env` and edit. **Do not commit `.env`.**

```
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=INFO
USE_LLM=false
OPENAI_API_KEY=
MODEL_NAME=
```

---

## 10. Submission form mapping

| Field                       | Value to submit                                  |
| --------------------------- | ------------------------------------------------ |
| Live URL                    | `https://<your-host>/` (Render / Railway / Fly / Poridhi) |
| Docker pull command         | `docker pull <username>/queue-storm-investigator:latest` |
| GitHub repository           | public URL or shared with `bipulhf`               |
| README.md                   | included in repo root                             |
| `.env.example`              | included in repo root                             |
| `sample_output.json`        | included in repo root                             |
