import os

os.environ["DATABASE_URL"] = "sqlite:///./_test_override.db"
os.environ["LLM_PROVIDER"] = "none"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import _RATE, _test_session_header, app  # noqa: E402


def test_override_stores_reason_and_changes_display():
    _RATE.clear()  # clean rate window: this suite's other tests share the process
    cl = TestClient(app)
    h = _test_session_header()
    j = cl.post("/jobs", json={"title": "T", "jd_text": "Python FastAPI",
                               "required": ["python"], "preferred": []}, headers=h).json()
    up = cl.post("/jobs/" + j["id"] + "/resumes", files=[("files", ("r.txt", "Skills:\nPython\nExperience:\nDev 3 years python"))], headers=h).json()
    cid = up["candidate_ids"][0]
    import time
    time.sleep(1)
    before = cl.get("/candidates/" + cid, headers=h).json()
    assert before["overridden"] is False
    r = cl.post("/candidates/" + cid + "/override",
                json={"new_decision": "reject", "reason": "test freeze"}, headers=h)
    assert r.status_code == 200
    after = cl.get("/candidates/" + cid, headers=h).json()
    assert after["final_decision"] == "reject"
    assert after["system_decision"] == before["system_decision"]
    assert after["overridden"] is True
