# ShortlistIQ

AI-assisted resume screening: deterministic scoring, evidence-grounded explanations, recruiter override wins.

1. Copy env: `cp .env.example .env` (add `GEMINI_API_KEY` or keep `LLM_PROVIDER=none`)
2. Start all: `docker compose up --build`
3. Open UI: `http://localhost:3000`, API: `http://localhost:8000/health`
4. Demo: New job → paste JD → upload `sample_data/resumes/` → ranking → detail → override with reason → Export CSV
5. Eval: `python eval/run_eval.py` (precision/recall/F1 + name-swap + timing)
6. Backend tests: `pytest backend/tests/`
7. No-LLM fallback: `LLM_PROVIDER=none` runs rule-based extractor end-to-end
8. Frontend design swap: drop uploaded design into `frontend/`, then `npm run lint`, `npx tsc --noEmit`, `npm run build`

## Environment variables

Copy `.env.example` → `.env` and fill in as needed. Everything except the database URL ships with a working default; `LLM_PROVIDER=none` runs the whole pipeline (parse → mask → extract → score) with **no API keys**.

| Variable | Who reads it | Default | Notes |
|---|---|---|---|
| `DATABASE_URL` | backend | `sqlite:///./shortlistiq.db` | Postgres URL in compose (`postgresql+psycopg://...`) |
| `LLM_PROVIDER` | backend | `none` | `gemini` / `anthropic` / `groq` / `none`; key from the matching var below |
| `GEMINI_API_KEY` / `ANTHROPIC_API_KEY` / `GROQ_API_KEY` | backend | — | Required only for the chosen provider |
| `GEMINI_MODEL` | backend | `gemini-2.0-flash` | Model override |
| `EMBEDDING_MODEL` | backend | `BAAI/bge-small-en-v1.5` | Downloaded on first run (~130 MB) |
| `NEXT_PUBLIC_API_URL` | frontend (build-time) | `http://localhost:8000` | Must be browser-reachable |
| `ALLOWED_ORIGINS` | backend | `http://localhost:3000,http://127.0.0.1:3000` | CORS allow-list; add your production origin |
| `RATE_MAX` | backend | `120` | Requests/IP per 60 s (health exempt) |

Secrets live only in `.env` (git-ignored) or your deployment platform's secret store — never in the repo and never in the frontend bundle.

## Recruiter authentication & PII retention

Every data route requires a signed-in recruiter. The stack is unchanged — stdlib PBKDF2 password hashing and HMAC-signed session tokens, no new dependencies or services.

- **First run:** open `http://localhost:3000/login` → *Register* → you're in. Sign-ins are recorded in `audit_log`.
- **Session:** 12 h default (`TOKEN_TTL_SECONDS`), Bearer token in `localStorage`
- **Recruiter identity on overrides:** the override `user` field is now the signed-in email, not a client-supplied string
- **raw_text retention:** original unmasked resume text is cleared after `PURGE_RAW_TEXT_AFTER_DAYS` days (default 30); masked text and scores stay. `0` disables.
- **Delete per data-subject request:** `DELETE /candidates/{id}` (UI button on the candidate detail panel) removes the candidate, their overrides, and keeps a non-PII audit entry.
- **Multi-worker note:** with `AUTH_SECRET` unset, tokens are boot-generated per process; set a shared value in `.env` when running more than one worker.
