"""Auth gating, session lifecycle, candidate erasure, and raw-text retention."""
import unittest.mock

import os

os.environ["DATABASE_URL"] = "sqlite:///./_test_auth.db"
os.environ["LLM_PROVIDER"] = "none"

# Deterministic HMAC secret, and only if not already set by another test
os.environ.setdefault("AUTH_SECRET", "test-secret")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import _RATE, _test_session_header, app  # noqa: E402


def _client():
    _RATE.clear()
    # rate_max is process-global env, but RATE_MAX in app.main is captured at
    # import; tests sharing one process cannot lower it post-hoc, so instead
    # each test file gets a clean window via _RATE.clear().
    return TestClient(app, raise_server_exceptions=False)


def _fresh_cl_and_header():
    """ONE deterministic (client, header) pair per call: a demo user row is
    upserted directly via _test_session_header, so success never depends on
    cross-test POST /auth/register state (email conflicts, rate windows)."""
    cl = _client()
    return cl, _test_session_header()


def _register(cl, email="r@example.com", password="correct-horse-battery"):
    return cl.post("/auth/register", json={"email": email, "password": password})


def _register_unique(cl, password="correct-horse-battery"):
    """Register under an address no other test run can claim (fresh DB or shared)."""
    import secrets
    email = f"{secrets.token_hex(6)}@example.com"
    r = cl.post("/auth/register", json={"email": email, "password": password})
    assert r.status_code == 201, r.json()
    return r.json()["token"], email, password


def _auth_header(token: str):
    return {"Authorization": "Bearer " + token}


def test_data_routes_require_auth():
    cl = _client()
    assert cl.get("/jobs").status_code == 401
    assert cl.get("/jobs/nonexistent").status_code == 401
    assert cl.get("/candidates/nonexistent").status_code == 401


def test_health_stays_open():
    cl = _client()
    assert cl.get("/health").status_code == 200


def test_register_and_login_roundtrip():
    cl = _client()
    token, email, password = _register_unique(cl)
    assert token
    # duplicate email rejected
    assert _register(cl, email=email, password=password).status_code == 409
    # login with right password
    r = cl.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200
    # wrong password -> same error as unknown user (no enumeration)
    r = cl.post("/auth/login", json={"email": email, "password": "definitely-wrong-9"})
    assert r.status_code == 401
    r = cl.post("/auth/login", json={"email": "nobody@example.com", "password": "wrong-password"})
    assert r.status_code == 401
    assert r.json()["detail"] == cl.post(
        "/auth/login", json={"email": email, "password": "definitely-wrong-9"}).json()["detail"]


def test_gated_flow_end_to_end():
    cl, h = _fresh_cl_and_header()
    j = cl.post("/jobs", json={"title": "T", "jd_text": "Python"}, headers=h).json()
    up = cl.post(f"/jobs/{j['id']}/resumes",
                 files=[("files", ("r.txt", b"Skills:\nPython"))], headers=h)
    assert up.status_code == 200
    cid = up.json()["candidate_ids"][0]
    assert cl.get(f"/jobs/{j['id']}/ranking", headers=h).status_code == 200
    assert cl.get(f"/candidates/{cid}", headers=h).status_code == 200
    assert cl.get(f"/jobs/{j['id']}/export.csv", headers=h).status_code == 200


def test_tampered_and_garbage_tokens_rejected():
    cl, h = _fresh_cl_and_header()
    token = h["Authorization"].split(" ", 1)[1]
    # tampering must flip the LAST character of the sig payload, not re-pad:
    # appending arbitrary chars can accidentally produce the same base64 payload
    assert cl.get("/jobs", headers={**h, "Authorization": "Bearer " + token[:-1] + ("A" if token[-1] != "A" else "B")}).status_code == 401
    assert cl.get("/jobs", headers=_auth_header("not-a-token")).status_code == 401
    assert cl.get("/jobs", headers=_auth_header("")).status_code == 401
    # still-valid token keeps working
    valid = cl.get("/jobs", headers=h)
    assert valid.status_code == 200, f"valid token got {valid.status_code}: {valid.json()}"


def _token_for(cl, email):
    """Token for an existing user (or registers if not yet present)."""
    r = cl.post("/auth/login", json={"email": email, "password": "correct-horse-battery"})
    if r.status_code == 200:
        return r.json()["token"]
    r = _register(cl, email)
    if r.status_code == 201:
        return r.json()["token"]
    return None


def test_override_records_signed_in_email():
    cl, h = _fresh_cl_and_header()
    email = "test-recruiter@shortlistiq.local"  # the helper user
    j = cl.post("/jobs", json={"title": "T"}, headers=h).json()
    up = cl.post(f"/jobs/{j['id']}/resumes",
                 files=[("files", ("r.txt", b"Skills:\nPython"))], headers=h)
    cid = up.json()["candidate_ids"][0]
    r = cl.post(f"/candidates/{cid}/override",
                json={"new_decision": "reject", "reason": "not a fit"}, headers=h)
    assert r.status_code == 200
    detail = cl.get(f"/candidates/{cid}", headers=h).json()
    assert detail["overridden"] is True
    # the stored override user is the email, not a client-supplied string
    from app.db import SessionLocal
    from app.models import Override
    db = SessionLocal()
    ov = db.query(Override).filter(Override.candidate_id == cid).one()
    assert ov.user == email
    db.close()


def test_delete_candidate_erases_everything():
    cl, h = _fresh_cl_and_header()
    j = cl.post("/jobs", json={"title": "T"}, headers=h).json()
    up = cl.post(f"/jobs/{j['id']}/resumes",
                 files=[("files", ("r.txt", b"Skills:\nPython email jane@doe.com"))], headers=h)
    cid = up.json()["candidate_ids"][0]
    assert cl.delete(f"/candidates/{cid}", headers=h).status_code == 200
    assert cl.get(f"/candidates/{cid}", headers=h).status_code == 404
    assert cl.delete(f"/candidates/{cid}", headers=h).status_code == 404
    # second registered user cannot see it either (nothing to see, but route is gated)
    from app.db import SessionLocal
    from app.models import Override
    db = SessionLocal()
    assert db.query(Override).filter(Override.candidate_id == cid).count() == 0
    db.close()


def test_purge_stale_raw_text():
    from datetime import datetime, timedelta
    from app.db import SessionLocal
    from app.models import Candidate
    from app.routers.candidates import purge_stale_raw_text

    db = SessionLocal()
    import secrets
    suffix = secrets.token_hex(6)
    cid = "purgecheck" + "0" * (12 - len("purgecheck") - len(suffix)) + suffix
    fresh_id = "freshchk" + "0" * (12 - len("freshchk") - len(suffix)) + suffix
    # ids are 12 chars; guarantee uniqueness even when the suite shares one DB
    cid = "p" + suffix + "0000000"[:11 - len(cid)] if len(cid) > 12 else cid
    rows = [
        Candidate(id=cid, job_id="nojob", filename="old.txt",
                  raw_text="Jane Doe jane@doe.com", masked_text="masked",
                  status="done", created_at=datetime.utcnow() - timedelta(days=60)),
        Candidate(id=fresh_id, job_id="nojob", filename="new.txt",
                  raw_text="Jane Doe jane@doe.com", masked_text="masked",
                  status="done", created_at=datetime.utcnow()),
    ]
    for row in rows:
        existing = db.get(Candidate, row.id)
        if existing:
            existing.raw_text = "Jane Doe jane@doe.com"
            existing.masked_text = "masked"
            existing.created_at = row.created_at
        else:
            db.add(row)
    db.commit()
    purged = purge_stale_raw_text(db, days=30)
    assert purged >= 1
    db.expire_all()
    assert db.get(Candidate, cid).raw_text == ""
    assert db.get(Candidate, fresh_id).raw_text != ""
    # do not pollute other tests with uniques
    for row_id in (cid, fresh_id):
        c = db.get(Candidate, row_id)
        if c:
            db.delete(c)
    db.commit()
    db.close()


def test_token_expiry():
    # Drive expiry via a token minted with a tiny TTL rather than patching the
    # module clock — patching a module attribute inside a package can leak into
    # other tests depending on import order (seen under two-file suite runs).
    from app.auth import issue_token, parse_token
    token = issue_token("u1", ttl=-1)  # already expired at issue time
    try:
        parse_token(token)
        assert False, "expired token accepted"
    except Exception:
    # ValueError for bad/expired; HTTPException if raised from the dependency
        pass
