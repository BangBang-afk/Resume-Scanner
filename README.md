# ShortlistIQ

AI-assisted resume screening: deterministic scoring, evidence-grounded explanations, recruiter override wins.

1. Run everything with one command: `python run.py` — boots the API (`:8000`) and the UI (`:3000`), seeds the demo job + 12 resumes on first run, opens your browser. Ctrl+C stops both. (Needs Python + Node installed; first run builds the frontend.)
2. Or via Docker: copy env (`cp .env.example .env`), then `docker compose up --build`
3. Sign in at `/login` (register once) — demo seed uses `demo@vetted.local` / `vetted-demo-2026`
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

## Host the backend (pairs with Vercel frontend)

Vercel cannot host this API (SQLite disk + background scoring exceed serverless limits). Two hosts, pick one:

**Option A — Fly.io (recommended, `fly.toml` included):** free shared VMs + 1 GB persistent volume, so demo data survives restarts.

1. Install flyctl → `fly auth signup` → `cd shortlistiq` → `fly launch` (reuse config, pick region near you)
2. `fly volumes create shortlistiq_data --size 1`
3. `fly secrets set ALLOWED_ORIGINS="http://localhost:3000,http://127.0.0.1:3000,https://<your-app>.vercel.app"`
4. `fly deploy`, copy `https://shortlistiq-api.fly.dev` (or your app name)
5. Vercel env `NEXT_PUBLIC_API_URL=https://<name>.fly.dev` → redeploy frontend

**Option B — Render (`render.yaml` included):**

1. Render Dashboard → New → Blueprint → select repo (`render.yaml` found automatically)
2. Deploy `shortlistiq-api`, copy its `https://...onrender.com` URL
3. Render env: append `https://<your-app>.vercel.app` to `ALLOWED_ORIGINS`, redeploy
4. Vercel project → Settings → Environment Variables: `NEXT_PUBLIC_API_URL=https://...onrender.com` → redeploy frontend
5. Open Vercel URL from anywhere, register once, full app live

Free tier sleeps when idle (first load ~50s). Demo data resets on restart — re-upload resumes via UI.
