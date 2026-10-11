import os

os.environ["LLM_PROVIDER"] = "none"

from app.services.extractor import extract_profile
from app.services.jd_analyzer import analyze_jd
from app.services.masking import mask_pii
from app.services.parser import parse_file
from app.services.scoring import score_candidate


def test_full_pipeline_without_llm():
    raw = b"Priya Dev\npriya@mail.com\nSkills:\nPython, FastAPI\nExperience:\nDev 3 years python apis\nEducation:\nB.Tech 2020"
    text, q = parse_file("r.txt", raw)
    masked, ident = mask_pii(text)
    assert "priya@mail.com" not in masked
    profile, ry = extract_profile(masked, q)
    assert profile.parse_quality > 0
    jd = analyze_jd("Required: Python. Preferred: Docker.")
    assert "python" in jd["required"]
    r = score_candidate(profile, ry, masked, {**jd, "responsibilities_text": "python", "required_degree_level": 1})
    assert r["total"] >= 0
