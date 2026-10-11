"""Recruiter authentication.

Stdlib-only on purpose (no new dependencies for the project stack):
- passwords: PBKDF2-HMAC-SHA256 with per-user salt
- tokens: HMAC-signed expiry payloads (itsdangerous-style), no DB round-trip
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from .db import get_db

import sqlalchemy as sa
from sqlalchemy.orm import Session  # noqa: F401  (re-exported for tests)

from .models import User

PBKDF_ITERS = int(os.getenv("PBKDF_ITERS", "120000"))
TOKEN_TTL_SECONDS = int(os.getenv("TOKEN_TTL_SECONDS", str(12 * 3600)))
_SECRET = None

router = APIRouter(prefix="/auth", tags=["auth"])


class UserIn(BaseModel):
    email: str = Field(min_length=3, max_length=120)
    password: str = Field(min_length=8, max_length=128)


class TokenIn(BaseModel):
    email: str = Field(min_length=3, max_length=120)
    password: str = Field(min_length=1, max_length=128)


def user_table_ready(engine) -> bool:
    return sa.inspect(engine).has_table("users")


def _secret() -> bytes:
    """Secret for password-token signing. Priority: env > boot-generated.

    Boot-generated means tokens reset on restart (acceptable for a single-node
    demo), and the value never lands in code or the repo.
    """
    global _SECRET
    if _SECRET is None:
        raw = os.getenv("AUTH_SECRET", "")
        _SECRET = raw.encode() if raw else secrets.token_bytes(32)
    return _SECRET


def hash_password(password: str, salt: bytes) -> str:
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF_ITERS)
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def verify_password(password: str, stored: str, salt: str) -> bool:
    return hmac.compare_digest(hash_password(password, salt.encode()), stored)


def _sign(payload: bytes) -> bytes:
    return hmac.new(_secret(), payload, hashlib.sha256).digest()


def issue_token(user_id: str, ttl: int = TOKEN_TTL_SECONDS) -> str:
    exp = int(time.time()) + ttl
    payload = base64.urlsafe_b64encode(
        json.dumps({"u": user_id, "e": exp}).encode()).decode().rstrip("=")
    body = payload.encode()
    sig = _sign(body)
    return base64.urlsafe_b64encode(body + b"." + sig).decode().rstrip("=")


def parse_token(token: str) -> str:
    """Return user id or raise ValueError. Signature check is constant-time."""
    if not token:
        raise ValueError("empty token")
    padded = token + "=" * (-len(token) % 4)
    raw = base64.urlsafe_b64decode(padded.encode())
    body, sig = raw.rsplit(b".", 1)
    if not hmac.compare_digest(_sign(body), sig):
        raise ValueError("bad signature")
    payload = json.loads(base64.urlsafe_b64decode(body + b"=" * (-len(body) % 4)).decode())
    if payload["e"] < time.time():
        raise ValueError("expired")
    return str(payload["u"])


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    """FastAPI dependency; attach to a route to require a signed-in recruiter."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "sign in first (Bearer token required)")
    token = authorization.split(" ", 1)[1].strip()
    try:
        user_id = parse_token(token)
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(401, "invalid or expired session token") from exc
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(401, "unknown user")
    return user


@router.post("/register", status_code=201)
def register(payload: UserIn, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(409, "email already registered")
    salt = secrets.token_hex(16)
    user = User(id=secrets.token_urlsafe(8), email=email,
                password_hash=hash_password(payload.password, salt.encode()),
                salt=salt)
    db.add(user)
    db.commit()
    return {"id": user.id, "email": user.email,
            "token": issue_token(user.id)}


@router.post("/login")
def login(payload: TokenIn, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    # Same error for both cases: no user enumeration.
    if not user or not verify_password(payload.password, user.password_hash, user.salt):
        raise HTTPException(401, "wrong email or password")
    return {"id": user.id, "email": user.email, "token": issue_token(user.id)}
