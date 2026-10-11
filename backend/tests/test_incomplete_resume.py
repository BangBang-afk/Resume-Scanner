from app.schemas import Education, Experience, ResumeProfile, SkillMention
from app.services.scoring import score_candidate


def test_missing_section_na_and_renormalized():
    p = ResumeProfile(
        skills=[SkillMention(raw="python", canonical="python")],
        experience=[Experience(title="Dev", summary="python backend " * 20, years=3.0)],
        projects=[], education=[Education(degree="b.tech", field="cs")],
        missing_sections=["projects"], parse_quality=0.9)
    jd = {"required": ["python"], "preferred": ["docker"],
          "min_years": 2, "responsibilities_text": "python backend", "required_degree_level": 1}
    r = score_candidate(p, 3.0, "python backend " * 30, jd)
    assert r["factors"]["projects"]["value"] is None
    assert "INCOMPLETE_RESUME" in r["flags"]
    # weights renormalized: total uses only present factors
    present = {k: v for k, v in r["factors"].items() if v["value"] is not None}
    assert "must" in present
    exp = 100 * sum(v["value"] * v["weight"] for v in present.values()) / sum(v["weight"] for v in present.values())
    assert abs(r["total"] - round(exp, 2)) < 0.01
