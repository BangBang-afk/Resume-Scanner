"""Limiter-behavior tests run in a fully isolated interpreter (CI runs each
test module as its own pytest process with its own env), so they may freely
re-enable the limiter. The RATE_LIMIT_DISABLED toggle is checked per request
by app.main, so mutations here are visible immediately.
"""
import os

os.environ["DATABASE_URL"] = "sqlite:///./_test_security.db"
os.environ["LLM_PROVIDER"] = "none"
os.environ.pop("RATE_LIMIT_DISABLED", None)  # this file owns limiter behavior

from fastapi.testclient import TestClient  # noqa: E402

from app.main import _RATE, _test_session_header, app  # noqa: E402
from app.routers.jobs import _csv_safe  # noqa: E402


def _restore_limiter_off():
    """Restore the conftest default so any later import in THIS interpreter
    (e.g. test_auth_delete if combined) sees the limiter disabled."""
    os.environ["RATE_LIMIT_DISABLED"] = "1"


def _client():
    _RATE.clear()
    return TestClient(app, raise_server_exceptions=False)


def test_bad_extension_rejected():
    cl = _client()
    j = cl.post("/jobs", json={"title": "T", "jd_text": "Python"}, headers=_test_session_header()).json()
    r = cl.post("/jobs/" + j["id"] + "/resumes", files=[("files", ("evil.exe", b"xx"))], headers=_test_session_header())
    assert r.status_code == 400


def test_oversize_file_rejected():
    cl = _client()
    j = cl.post("/jobs", json={"title": "T", "jd_text": "Python"}, headers=_test_session_header()).json()
    big = b"x" * (10 * 1024 * 1024 + 1)
    r = cl.post("/jobs/" + j["id"] + "/resumes", files=[("files", ("big.txt", big))], headers=_test_session_header())
    assert r.status_code == 400


def test_empty_file_rejected():
    cl = _client()
    j = cl.post("/jobs", json={"title": "T", "jd_text": "Python"}, headers=_test_session_header()).json()
    r = cl.post("/jobs/" + j["id"] + "/resumes", files=[("files", ("e.txt", b"   "))], headers=_test_session_header())
    assert r.status_code == 400


def test_unbounded_bodies_rejected():
    cl = _client()
    assert cl.post("/jobs", json={"title": "x" * 500, "jd_text": ""}, headers=_test_session_header()).status_code == 422
    assert cl.post("/jobs", json={"title": "T", "jd_text": "x" * 20001}, headers=_test_session_header()).status_code == 422
    j = cl.post("/jobs", json={"title": "T", "jd_text": "Python", "required": ["python"]}, headers=_test_session_header()).json()
    up = cl.post("/jobs/" + j["id"] + "/resumes",
                 files=[("files", ("r.txt", b"Skills:\nPython"))], headers=_test_session_header()).json()
    cid = up["candidate_ids"][0]
    assert cl.post("/candidates/" + cid + "/override",
                   json={"new_decision": "reject", "reason": "x" * 501}, headers=_test_session_header()).status_code == 422


def test_security_headers_present():
    cl = _client()
    r = cl.get("/health")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"


def test_rate_limit_trips():
    cl = _client()
    # Rate limiter exempts /health only; gated 401s still count as requests.
    statuses = [cl.get("/jobs/does-not-exist").status_code for _ in range(130)]
    assert 429 in statuses
    _restore_limiter_off()


def test_csv_formula_sanitized():
    assert _csv_safe("=cmd|'/c calc'!A0") == "'=cmd|'/c calc'!A0"
    assert _csv_safe("normal.txt") == "normal.txt"
    _restore_limiter_off()
