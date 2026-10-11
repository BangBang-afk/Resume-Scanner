import os
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware

from .auth import issue_token, router as auth_router
from .db import Base, engine, get_db
from .models import AuditLog, Candidate, Job, User
from .routers import candidates, jobs

__all__ = ["_RATE", "app"]  # _RATE is poked by tests

Base.metadata.create_all(bind=engine)

app = FastAPI(title="ShortlistIQ", docs_url="/docs", redoc_url=None)

ALLOWED_ORIGINS = [o.strip() for o in os.getenv(
    "ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",") if o.strip()]
app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS, allow_methods=["GET", "POST", "DELETE"],
                   allow_headers=["Content-Type", "Authorization"], max_age=600)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        resp = await call_next(request)
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        resp.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return resp


app.add_middleware(SecurityHeadersMiddleware)

# In-memory rate limit: RATE_MAX requests / 60s per client IP (health exempt).
# The per-IP map is pruned each request so spoofed-IP floods cannot grow memory.
_RATE: dict[str, list[float]] = {}
RATE_MAX = int(os.getenv("RATE_MAX", "120"))
RATE_WINDOW = 60.0
_MAX_TRACKED_IPS = 10_000


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Opt-out switch (tests only): RATE_LIMIT_DISABLED=1 skips counting
        # entirely except /health. test_security toggles it around its own
        # limiter assertions; everything else runs with limiter off so
        # cross-test in-process state cannot bleed 429s into unrelated tests.
        if os.getenv("RATE_LIMIT_DISABLED") == "1" and request.url.path != "/health":
            return await call_next(request)
        if request.url.path != "/health":
            now = time.time()
            ip = request.client.host if request.client else "unknown"
            hits = [t for t in _RATE.get(ip, []) if now - t < RATE_WINDOW]
            if len(hits) >= RATE_MAX:
                return JSONResponse({"detail": "rate limit exceeded, slow down"}, status_code=429)
            hits.append(now)
            _RATE[ip] = hits
            if len(_RATE) > _MAX_TRACKED_IPS:
                cutoff = now - RATE_WINDOW
                for key in [k for k, v in _RATE.items()
                            if not v or v[-1] < cutoff][: len(_RATE) - _MAX_TRACKED_IPS]:
                    _RATE.pop(key, None)
        return await call_next(request)


app.add_middleware(RateLimitMiddleware)

app.include_router(auth_router)
app.include_router(jobs.router)
app.include_router(candidates.router)


@app.get("/health")
def health():
    return {"ok": True}


def _test_session_header(db_session=None):
    """Test helper: Bearer header for a deterministic demo user.

    Creates the row on first call so tests can hit gated routes without
    round-tripping /auth/register. Not wired into the app for production use.
    """
    import secrets

    from sqlalchemy.orm import Session as _S

    from .auth import hash_password

    db = db_session or next(get_db())
    try:
        email = "test-recruiter@shortlistiq.local"
        user = db.query(User).filter(User.email == email).first()
        if not user:
            salt = secrets.token_hex(16)
            user = User(id="testuser00001", email=email,
                        password_hash=hash_password("test-password", salt.encode()), salt=salt)
            db.add(user)
            db.commit()
        return {"Authorization": "Bearer " + issue_token(user.id)}
    finally:
        if db_session is None:
            db.close()
