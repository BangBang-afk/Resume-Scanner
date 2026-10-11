from app.schemas import Education, Experience, Project, ResumeProfile, SkillMention
from app.services.scoring import score_candidate


def test_missing_must_have_caps_at_69():
    p = ResumeProfile(
        skills=[SkillMention(raw="python", canonical="python")],
        experience=[Experience(title="Dev", summary="python backend " * 20, years=6.0)],
        projects=[Project(name="p", summary="python backend " * 20)],
        education=[Education(degree="b.tech", field="cs")],
        missing_sections=[], parse_quality=0.95)
    jd = {"required": ["python", "fastapi"], "preferred": ["docker"],
          "min_years": 2, "responsibilities_text": "python backend", "required_degree_level": 1}
    r = score_candidate(p, 6.0, "python backend django " * 30, jd)
    assert "MISSING_MUST_HAVE" in r["flags"]
    assert r["total"] <= 69
