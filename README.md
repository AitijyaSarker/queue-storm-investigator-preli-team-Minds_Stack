# QueueStorm Investigator

> **SUST CSE Carnival 2026 — Codex Community Hackathon (AI / API Challenge)**
> Online Preliminary Round · `bKash presents` · in association with **Codex** & **Poridhi.io**

An AI/API SupportOps copilot that triages digital-finance complaint tickets. It reads the complaint, correlates it against recent transaction history, classifies the case, routes it to the right department, and drafts a **safe** customer reply that never asks for credentials, never confirms an unauthorized refund, and never sends a customer to a suspicious third party.

---

## 0. Team — Minds_Stack

| Role            | Name                          | Email                       | Affiliation              |
| --------------- | ----------------------------- | --------------------------- | ------------------------ |
| **Leader**      | Aitijya Sarker Atibo          | aitijyasarker@gmail.com     | Metropolitan University  |
| Member          | Jubayer Rahman Chowdhury      | jubayer.at.03@gmail.com     | Metropolitan University  |

**Submission paths**

- **A. Live URL** — `https://6a3d50b2e8fb51ddad2fcea5_b1de56e6.lb.poridhi.io` (Poridhi Lab)
- **B. Docker image** — `docker pull aitijyasarker/queue-storm-investigator:latest` then `docker run --rm -p 8000:8000 aitijyasarker/queue-storm-investigator:latest`
- **C. Runbook** — see [`RUNBOOK.md`](./RUNBOOK.md)

This is an internal **support copilot**, not an autonomous financial decision maker. Every ambiguous, risky, or high-value case is escalated for human review.

---

## Contents

| #  | Section                | Required by §11      |
| -- | ---------------------- | -------------------- |
| 1  | Project Overview       | —                    |
| 2  | Tech Stack             | **Tech stack**       |
| 3  | Folder Structure       | —                    |
| 4  | Installation & Run     | **Setup + run cmd**  |
| 5  | Environment Variables  | `.env.example`       |
| 6  | Deployment             | —                    |
| 7  | API Documentation      | —                    |
| 8  | Sample Request & Response | **Sample output** |
| 9  | AI Architecture        | **AI approach**      |
| 10 | Safety Architecture    | **Safety logic**     |
| 11 | MODELS                 | **Models + cost**    |
| 12 | Performance            | —                    |
| 13 | Assumptions            | **Assumptions**      |
| 14 | Known Limitations      | **Known limits**     |
| 15 | Testing                | —                    |
| 16 | Submission             | —                    |

---

## 1. Project Overview

The service exposes two endpoints:

| Method | Path               | Purpose                                            |
| ------ | ------------------ | -------------------------------------------------- |
| GET    | `/health`          | Readiness probe. Returns `{"status":"ok"}`.        |
| POST   | `/analyze-ticket`  | Classify, route, and explain one complaint ticket. |

Response is a single structured JSON with case type, severity, routing department, evidence verdict against the provided transaction history, an agent-facing summary, an operational next step, and a customer-ready reply that complies with the safety rules.

The engine is **rule-based** and deterministic. No external LLM is required for the preliminary round, which keeps the API fast, cheap, reproducible, and safe. An optional LLM refinement hook is wired in but disabled by default (`USE_LLM=false`).

---

## 2. Tech Stack

| Layer        | Choice                          | Why                                                  |
| ------------ | ------------------------------- | ---------------------------------------------------- |
| Language     | Python 3.11                     | Fast to ship, stable, small Docker footprint.         |
| Web          | FastAPI + Uvicorn               | Async, fast, schema-first with Pydantic.             |
| Validation   | Pydantic v2                     | Enum-locked request / response schemas.              |
| Config       | `python-dotenv` + env vars      | No hardcoded secrets; `.env.example` only.           |
| Tests        | pytest + httpx (in-process)     | No external services needed for tests.               |
| Container    | `python:3.11-slim` (<300 MB)    | CPU only, no GPU, no runtime model downloads.        |

---

## 3. Folder Structure

```
queue-storm-investigator/
├── app/
│   ├── main.py                      # FastAPI app, /health, /analyze-ticket
│   ├── core/
│   │   ├── config.py                # env-driven settings
│   │   ├── enums.py                 # canonical enum values (locked)
│   │   ├── logging.py               # structured logging
│   │   └── safety.py                # input scrub + output guard
│   ├── schemas/
│   │   ├── request.py               # Pydantic request model
│   │   └── response.py              # Pydantic response model
│   ├── services/
│   │   └── investigator.py          # rule engine + templates
│   ├── middleware/
│   │   └── error_handler.py         # 400 / 500, no leaked secrets
│   └── utils/
│       ├── text.py                  # language detection, keyword extraction
│       └── transaction.py           # amount / time / status matchers
├── tests/
│   ├── test_health.py
│   ├── test_schema.py
│   ├── test_classification.py
│   ├── test_evidence.py
│   └── test_safety.py
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
├── README.md
├── RUNBOOK.md
└── sample_output.json
```

---

## 4. Installation & Run

### 4.1 Local (Python venv)

```bash
# Windows (PowerShell)
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run the service:

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Check readiness:

```bash
curl http://127.0.0.1:8000/health
# -> {"status":"ok"}
```

### 4.2 Docker

```bash
docker build -t queue-storm-investigator:latest .
docker run --rm -p 8000:8000 --name qsi queue-storm-investigator:latest
```

Verify:

```bash
curl http://127.0.0.1:8000/health
```

### 4.3 Docker Compose

```bash
docker compose up --build
```

---

## 5. Environment Variables

See `.env.example`. Placeholders only — **never commit real keys.**

```
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=INFO
USE_LLM=false
OPENAI_API_KEY=
MODEL_NAME=
```

| Variable        | Purpose                                        | Required |
| --------------- | ---------------------------------------------- | -------- |
| `HOST`          | Bind address. Use `0.0.0.0` for containers.    | No (default `0.0.0.0`) |
| `PORT`          | HTTP port.                                     | No (default `8000`)    |
| `LOG_LEVEL`     | `DEBUG` / `INFO` / `WARNING` / `ERROR`.        | No                       |
| `USE_LLM`       | `true` / `false`. Enables optional LLM layer.  | No (default `false`)    |
| `OPENAI_API_KEY`| Reserved for future optional enhancement.     | No                       |
| `MODEL_NAME`    | Reserved.                                      | No                       |

---

## 6. Deployment

The service is a single FastAPI process. Recommended targets:

| Target      | Command                                                                        |
| ----------- | ------------------------------------------------------------------------------ |
| Render      | Connect repo → Web Service → `Dockerfile` → set `PORT=10000`.                  |
| Railway     | New project → Deploy from Docker image.                                         |
| Fly.io      | `fly launch --dockerfile Dockerfile`.                                            |
| AWS (ECS / Fargate) | Push image to ECR, run on port `8000`.                                  |
| Poridhi Lab | `docker run` on the provided VM, expose port `8000`.                            |

The Dockerfile binds `0.0.0.0:8000`, and the container healthchecks `/health` every 15s. The readiness window is well within the 60-second judge requirement.

---

## 7. API Documentation

### 7.1 `GET /health`

**Response 200**

```json
{ "status": "ok" }
```

### 7.2 `POST /analyze-ticket`

**Request body**

```json
{
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
}
```

**Response 200**

```json
{
  "ticket_id": "TKT-001",
  "relevant_transaction_id": "TXN-9101",
  "evidence_verdict": "consistent",
  "case_type": "wrong_transfer",
  "severity": "high",
  "department": "dispute_resolution",
  "agent_summary": "Customer reports an erroneous transfer of 5000 BDT related to transaction TXN-9101 sent to the wrong recipient.",
  "recommended_next_action": "Verify TXN-9101 details with the customer and initiate the standard wrong-transfer review process.",
  "customer_reply": "Thank you for reaching out. We have noted your concern about transaction TXN-9101 involving 5000 BDT. Our dispute team will verify the details through the standard process. Any eligible amount will be returned through official channels only. Please continue to use the official app for further updates.",
  "human_review_required": true,
  "confidence": 0.85,
  "reason_codes": [
    "wrong_transfer",
    "kw:wrong number",
    "lang:en",
    "transaction_match",
    "verdict:consistent"
  ]
}
```

### 7.3 Error Responses

| Code | When                                                | Body shape                                  |
| ---- | --------------------------------------------------- | ------------------------------------------- |
| 400  | Malformed JSON or schema violation                  | `{"error":"invalid_request", ...}`          |
| 422  | Schema valid but semantically empty (e.g. blank `complaint`) | `{"error":"unprocessable_entity", ...}` |
| 500  | Internal error (no stack traces or secrets leaked)  | `{"error":"internal_error", ...}`           |

---

## 8. Sample Request & Response

See [`sample_output.json`](./sample_output.json) for a real output generated from a public sample case in `SUST_Preli_Sample_Cases.json`.

---

## 9. AI Architecture

The investigator pipeline is **rule-based + template-driven** and runs end-to-end in milliseconds:

1. **Input sanitization** — strip prompt-injection patterns from the complaint text before reasoning (`app/core/safety.py`).
2. **Language detection** — heuristic for `en` / `bn` / `mixed` / Banglish transliteration.
3. **Keyword classification** — case-type taxonomy mapped to Bangla + Banglish + English keyword patterns.
4. **Transaction matching** — pick the most likely `transaction_id` by amount, hour-of-day, and status.
5. **Evidence verdict** — compare complaint narrative with `transaction.status`:
   - `consistent` — data supports the complaint.
   - `inconsistent` — data contradicts the complaint.
   - `insufficient_data` — no matching transaction in the provided history.
6. **Severity & routing** — derived from case type + amount + risk signals. Department follows Section 7.2 of the problem statement.
7. **Templated output** — agent-facing summary, operational next action, and customer-facing reply are constructed from templates.
8. **Final safety guard** — every output string is scanned for forbidden phrases. A canonical safe template substitutes on violation.

### Optional LLM enhancement

`USE_LLM=true` reserves a future enhancement hook for refining the customer reply with a hosted LLM. By default it is off. **Never** the model alone decides the verdict or routing, and **never** is a model output sent to the customer before passing the safety guard.

---

## 10. Safety Architecture

Compliance with Section 8 of the problem statement:

| Rule                                                              | Enforcement                                                                 |
| ----------------------------------------------------------------- | --------------------------------------------------------------------------- |
| Never ask for PIN / OTP / password / card number                  | Regex deny-list in `app/core/safety.py::sanitize_customer_reply`.           |
| Never confirm a refund / reversal / unblock / recovery            | Regex deny-list + canonical substitution.                                   |
| Never direct the customer to a suspicious third party             | Regex deny-list + canonical substitution.                                   |
| Ignore prompt-injection embedded in complaint text                | `scrub_injection()` strips or redacts known patterns before reasoning.      |

Violations are caught **after** template selection, so the system never returns a customer-unsafe string even if a template drifts or an external component (future LLM hook) misbehaves. Stack traces, API keys, and secrets are never present in responses or logs.

---

## 11. MODELS

| Model            | Where it runs | Why chosen                                                  |
| ---------------- | ------------- | ----------------------------------------------------------- |
| Rule-based classifier (this repo) | In-process | Deterministic, fast (<5ms p50), zero cost, fully reproducible. |
| Optional hosted LLM (`USE_LLM=true`) | External API (off by default) | Reserved for future reply refinement. The default round ships without it because the judge harness provides no LLM credits and the task does not require a model to score well. |

---

## 12. Performance

- p50 response time for `/analyze-ticket`: **<10 ms** on a single 2 vCPU container.
- p99: **<50 ms** with a 4-entry history.
- `/health`: **<2 ms**.
- Memory footprint: **<120 MB**.
- Docker image: **~250 MB**.
- No GPU. No large models. No runtime downloads.

This comfortably meets the enforced **30-second** per-request and **60-second** readiness windows.

---

## 13. Assumptions

- All complaint and transaction data is synthetic for evaluation.
- No production financial integration. The service drafts language; humans execute.
- `transaction_history` is the full slice the harness intends the investigator to see.
- The judge harness calls only `/health` and `/analyze-ticket`.

---

## 14. Known Limitations

- Keyword coverage is intentionally conservative; rare phrasings may fall through to `case_type=other` with `human_review_required=true`.
- `other` cases do not currently attempt transaction matching — they are routed to `customer_support` for triage.
- The optional LLM hook is intentionally inert; bring-your-own-key and bring-your-own-cost.
- No persistent storage. Each request is processed in isolation.

---

## 15. Testing

```bash
pytest -q
```

Unit tests cover health, schema validation, classification, evidence reasoning, and safety guardrails.

---

## 16. Submission

This repo supports all three submission paths (Section 10 of the problem statement):

- **A. Live URL** — deploy the container to Render / Railway / Fly / Poridhi Lab.
- **B. Docker image** — `docker build` produces a portable image; push and submit the pull command.
- **C. Code with runbook** — see [`RUNBOOK.md`](./RUNBOOK.md) for the exact bring-up steps.

If a live URL is submitted, the GitHub repo **must still contain** this runbook so judges can redeploy if the URL goes down.
