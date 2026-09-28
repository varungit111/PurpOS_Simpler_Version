# PurpOS Prototype

PurpOS is an AI-assisted self-service prototype for SMEs working through the SOI journey:

```text
Identify -> Define -> Align -> Measure & Learn
```

This repository currently contains the project source documents in `Purpos_docs/` plus a new frontend and backend foundation. The source documents must stay in place because they are the methodology and architecture reference material for later implementation.

## Project Structure

```text
frontend/   Next.js, React, TypeScript, Tailwind CSS, Zod
backend/    FastAPI, Pydantic v2
Purpos_docs/ Project reference documents and UX material
```

## Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Canonical frontend URL:

```text
http://localhost:3000
```

Use this hostname and port consistently during local development so browser
storage remains associated with one origin. The dev command binds explicitly
to `localhost:3000`. If port 3000 is already occupied, Next.js reports
`EADDRINUSE` and does not fall back to another port.

## Backend Setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

This command automatically loads local backend configuration from
`backend/.env`. Variables already set in the process environment take
precedence over values in that file.

Expected URL:

```text
http://localhost:8000
```

### Backend AI Configuration

Gemini remains the primary PurpOS AI provider. The backend constructs one
shared provider-neutral AI client, so Identify, Hot Seat, AI Detective, Signal
Hunt, Define, Stress Test, and Alignment code keep calling the same
`AIClient` interface.

OpenRouter is optional and only used as a fallback after eligible Gemini
provider failures such as rate limits, quota exhaustion, timeout, temporary
network/provider failures, Gemini 503, or selected retryable 5xx responses.
It is not used for application validation bugs, malformed internal requests,
auth/configuration errors, or structured-output validation failures.

Configure server-side keys in `backend/.env` only:

```text
GEMINI_API_KEY=
OPENROUTER_API_KEY=
OPENROUTER_MODEL=
OPENROUTER_FALLBACK_MODELS=
```

To disable provider fallback entirely:

```text
PURPOS_AI_FALLBACK_ENABLED=false
```

Development defaults are cost-conservative:

```text
PURPOS_AI_FREE_ONLY=true
OPENROUTER_FREE_MODELS=
```

When `PURPOS_AI_FREE_ONLY=true`, every configured OpenRouter model, including
fallback models, must appear in `OPENROUTER_FREE_MODELS`. PurpOS will not
silently choose OpenRouter Auto Router, arbitrary Claude/GPT/Gemini models, or
anything not explicitly allowlisted. Free availability and rate limits can
change at the provider, so treat the allowlist as a deliberate development
guard, not a guarantee from model naming. Do not enable paid models unless you
intentionally set `PURPOS_AI_FREE_ONLY=false` for that environment.

## Health Check

With the backend running:

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{"status":"ok","service":"purpos-api"}
```

## Current Scope

Implemented in this foundation:

- Next.js App Router frontend
- TypeScript strict mode
- Tailwind CSS
- Zod installed and used for environment validation
- FastAPI backend
- Pydantic v2 health response schema
- Backend `/health` endpoint
- Environment example files

Not implemented yet:

- AI provider integration
- Conversation engine
- Orchestrator behaviour
- Identify, Define, Align, or Measure logic
- RAG/document processing
- Database persistence
- Scoring
- Authentication
