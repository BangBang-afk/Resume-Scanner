"""Role lifecycle: isolation per role, edit re-scores, delete cascades."""
import os
import time

os.environ["DATABASE_URL"] = "sqlite:///./_test_roles.db"
os.environ["LLM_PROVIDER"] = "none"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import _RATE, _test_session_header, app  # noqa: E402

PY_RESUME = "Priya Dev\npriya@mail.com\nSkills:\nPython, FastAPI\nExperience:\nDev 3 years python apis\nEducation:\nB.Tech 2020"


def _client():
    _RATE.clear()
    return TestClient(app)


def _job(cl, h, title="Python Backend"):
    return cl.post("/jobs", json={"title": title, "jd_text": "Python backend. Required: Python, FastAPI. 2 years.",
                                  "required": ["python", "fastapi"], "preferred": []}, headers=h).json()


def _upload(cl, h, job_id, name="r.txt", text=PY_RESUME):
    up = cl.post("/jobs/" + job_id + "/resumes", files=[("files", (name, text))], headers=h).json()
    for _ in range(20):
        time.sleep(0.5)
        st = cl.get("/jobs/" + job_id + "/status", headers=h).json()
        if all(s["status"] in ("done", "error") for s in st):
            break
    return up["candidate_ids"][0]


def test_resumes_stay_in_their_role():
    with _client() as cl:
        h = _test_session_header()
        a = _job(cl, h, "Role A")
        b = _job(cl, h, "Role B")
        _upload(cl, h, a["id"], "a.txt")
        ra = cl.get("/jobs/" + a["id"] + "/ranking", headers=h).json()
        rb = cl.get("/jobs/" + b["id"] + "/ranking", headers=h).json()
        assert len(ra["ranking"]) == 1 and len(rb["ranking"]) == 0
        assert ra["ranking"][0]["filename"] == "a.txt"


def test_edit_role_details_rescores():
    with _client() as cl:
        h = _test_session_header()
        a = _job(cl, h, "Role Edit")
        cid = _upload(cl, h, a["id"], "e.txt")
        before = cl.get("/candidates/" + cid, headers=h).json()["score"]["total"]
        r = cl.put("/jobs/" + a["id"] + "/skills", headers=h,
                   json={"title": "Role Edit v2", "required": ["python", "fastapi", "kubernetes", "rust", "go"]})
        assert r.status_code == 200 and r.json()["rescored"] == 1
        after = cl.get("/candidates/" + cid, headers=h).json()
        assert after["score"]["total"] != before  # new must-haves change the score
        assert "MISSING_MUST_HAVE" in after["score"]["flags"]
        job = cl.get("/jobs/" + a["id"], headers=h).json()
        assert job["title"] == "Role Edit v2"


def test_delete_role_removes_everything():
    with _client() as cl:
        h = _test_session_header()
        a = _job(cl, h, "Role Doomed")
        cid = _upload(cl, h, a["id"], "d.txt")
        cl.post("/candidates/" + cid + "/override", headers=h,
                json={"new_decision": "reject", "reason": "x"})
        r = cl.delete("/jobs/" + a["id"], headers=h)
        assert r.status_code == 200 and r.json()["deleted_candidates"] == 1
        assert cl.get("/jobs/" + a["id"], headers=h).status_code == 404
        assert cl.get("/candidates/" + cid, headers=h).status_code == 404
