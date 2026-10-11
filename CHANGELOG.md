# Changelog

All notable changes to ShortlistIQ are documented here. Format based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning is
pre-1.0 (0.x.y) — breaking changes bump the minor.

## [0.3.0] — 2026-10-11

### Added
- **Recruiter authentication.** Register/login with PBKDF2-hashed passwords
  (stdlib, no new deps) and HMAC-signed Bearer session tokens. All jobs and
  candidates routes now require sign-in; overrides record the signed-in email.
  Frontend gained `/login`, a session gate, sign-out, and authenticated CSV
  download. Stack unchanged.
- **PII lifecycle.** `DELETE /candidates/{id}` for data-subject erasure (cascades
  overrides, keeps non-PII audit trace); retention job zeroes `raw_text` after
  `PURGE_RAW_TEXT_AFTER_DAYS` (default 30) days.
- **CI** (GitHub Actions): backend pytest, eval budget (F1 ≥ 0.75, name-swap
  delta ≤ 1.0), frontend lint + typecheck + build on every push/PR.
- **Container hardening.** Backend image runs as non-root `appuser`; compose
  gained db/backend healthchecks with ordered `depends_on` conditions.

### Config
- New optional env vars: `AUTH_SECRET`, `TOKEN_TTL_SECONDS`,
  `PURGE_RAW_TEXT_AFTER_DAYS` (documented in `.env.example`).

## [0.2.0] — 2026-10-11

### Removed
- Unauthenticated `/dev/name-swap-test` debug endpoint (bias-check tooling lives
  in `eval/run_eval.py` + `backend/tests/test_name_swap.py`, which is where it
  belonged). This endpoint was reachable without auth and re-ran the full
  scoring pipeline on arbitrary candidate IDs.

### Security
- Rate-limiter per-IP map is pruned each request; previously a flood of
  spoofed/unique client IPs grew `_RATE` unboundedly (memory DoS).
- Resume upload is now all-or-nothing: every file is validated before any
  candidate row is committed. Previously a bad file mid-batch left earlier
  (already-committed) candidates queued while the request returned 400.
- CORS allowed methods narrowed from `GET, POST, PUT` to the two actually used
  (`GET, POST`).
- "Resume removed" audit record (`resumes_uploaded`) for every batch.
- Uploads cannot smuggle oversized/unbounded bodies (already enforced; documented in README).

### Fixed
- Duplicate parse call in the background pipeline (pdf/docx were parsed twice).
- Frontend list pages (Candidates, Roles, Shortlists) swallowed every fetch
  error; they now show an error banner with a Retry action instead of a
  misleading empty list.
- Backend duplicate/interview endpoints silently swallowed exceptions; they
  now log with `logger.exception` before falling back.

### Accessibility
- Skip-to-content link, visible focus ring on all interactive elements,
  `prefers-reduced-motion` respected.
- Ranking rows expose `aria-label` + keyboard activation (Enter/Space, was already
  present); filter buttons get `aria-pressed`; bars get `role="meter"` with
  value attributes; status/messages use `role="alert"`; min-years slider gets a
  programmatic label; decorative bullet marked `aria-hidden`.
- Contrast: muted-text and yellow-ink tokens darkened/brightened to ≥ 4.5:1
  against their card/panel backgrounds in both themes.

### Removed (repo hygiene)
- Scratch files removed from the repo: `backend/_seed.py`, `_serve.py`,
  `_demo.db`, `_demo_job.txt`, `_run_backend.log`, `_run_backend.err.log`,
  `frontend/tsconfig.tsbuildinfo`. Added root and frontend `.dockerignore`,
  hardened the backend one.

## [0.1.0] — initial release

- Deterministic scoring (must/preferred/experience/projects/education weights),
  evidence-grounded explanations, recruiter override with reason receipt,
  blind mode, duplicate detection, CSV export, name-swap bias check, rate
  limiting, security headers, docker compose with pgvector.
