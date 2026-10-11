# Rollback

How to undo a bad deploy cleanly — no data loss, minimal downtime.

## Quick reference

| Change type | Rollback action | Data impact |
|---|---|---|
| Frontend (Next.js) image | Re-deploy previous image tag / `git revert` + rebuild | None (no FE state) |
| Backend (FastAPI) image | Re-deploy previous image tag | None |
| Backend schema change | See below — **never roll back a migration blindly** | May lose writes |
| `docker compose` env change | `cp` previous `.env.bak` → `docker compose up -d` | None |
| Database volume (`pgdata`) | Restore from backup (see below) | Depends on backup age |

## Backend / frontend image rollback

1. Keep the last-good image before every deploy:
   ```bash
   docker tag shortlistiq-backend:latest shortlistiq-backend:prev
   docker tag shortlistiq-frontend:latest shortlistiq-frontend:prev
   ```
2. Roll back by retagging and restarting:
   ```bash
   docker compose down
   docker tag shortlistiq-backend:prev shortlistiq-backend:latest
   docker tag shortlistiq-frontend:prev shortlistiq-frontend:latest
   docker compose up -d
   ```
   Or from git: `git revert <merge-commit> && docker compose up --build -d`.

No release in this repo should require coordinated same-moment back/frontend
rollbacks — the API contract is additive.

## Database notes

- Postgres data lives in the named volume `pgdata` — image rollbacks do not
  touch it. Snap it before risky ops:
  ```bash
  docker compose exec db pg_dump -U shortlistiq shortlistiq > backup_$(date +%F).sql
  ```
- Schema changes so far are additive (`CREATE TABLE` via SQLAlchemy
  `Base.metadata.create_all`, which never alters existing tables). Rolling back
  to a pre-`overrides`/`audit_log` release with those tables present is safe —
  old code just ignores them.
- If `create_all` introduced a table you don't want after rollback, drop it
  explicitly (`DROP TABLE audit_log`) rather than deleting the volume.

## Config / env rollback

`.env` changes are the most common deploys to fail fast:

```bash
cp .env .env.bak.$(date +%s)   # before editing
cp .env.bak.<ts> .env && docker compose up -d backend frontend
```

Secrets (`GEMINI_API_KEY`, etc.) changed in a platform secret store should be
double-keyed before rotation: keep the old value under `*_OLD` until the new
one is confirmed working.

## Frontend-only safe rollback

The frontend talks to the backend purely over `fetch` with the compile-time
`NEXT_PUBLIC_API_URL`; any prior frontend image works against any backend that
serves the documented routes (GET /jobs, POST /jobs, GET/POST /jobs/{id}/...,
GET/POST /candidates/{id}/...).

## Pre-deploy verification checklist

Run before every push/deploy — if any step fails, stop:

```bash
# backend
pytest backend/tests/ -q
# frontend
cd frontend && npm run lint && npx tsc --noEmit && npm run build
# full stack smoke
docker compose up --build -d
curl -fsS http://localhost:8000/health
curl -fsS http://localhost:3000 | head -5
# scoring eval (should not regress)
python eval/run_eval.py
```
