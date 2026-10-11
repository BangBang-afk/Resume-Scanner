import os
from fastapi.testclient import TestClient
from app.main import app, _RATE

def test_real_disable():
    print("env:", os.environ.get("RATE_LIMIT_DISABLED"))
    _RATE.clear()
    cl = TestClient(app)
    codes = [cl.post("/jobs", json={"title": "T", "jd_text": ""}).status_code for _ in range(5)]
    print("codes:", codes[:2], "... any 429:", 429 in codes)
