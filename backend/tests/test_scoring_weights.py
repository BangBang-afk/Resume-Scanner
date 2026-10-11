from app.schemas import Education, Experience, Project, ResumeProfile, SkillMention
from app.services.scoring import score_candidate


def _prof():
    return ResumeProfile(
        skills=[SkillMention(raw=s, canonical=s) for s in ["python", "fastapi", "docker", "aws"]],
        experience=[Experience(title="Backend Dev", summary="python fastapi backend apis " * 20, years=3.0)],
        projects=[Project(name="api", summary="python backend api docker " * 10)],
        education=[Education(degree="b.tech", field="cs")],
        missing_sections=[],
        parse_quality=0.95,
    )


def test_known_inputs_exact_total():
    jd = {"required": ["python", "fastapi"], "preferred": ["docker", "aws"],
          "min_years": 2, "responsibilities_text": "python fastapi backend apis docker",
          "required_degree_level": 1}
    # all skills exact: must=1, pref=1, education=1; experience/projects from embeddings
    r = score_candidate(_prof(), 3.0, "python fastapi docker aws backend apis " * 30, jd)
    assert r["factors"]["must"]["value"] == 1.0
    assert r["factors"]["preferred"]["value"] == 1.0
    assert r["factors"]["education"]["value"] == 1.0
    exp = 100 * (0.40 * 1 + 0.20 * 1 + 0.20 * r["factors"]["experience"]["value"]
                 + 0.10 * r["factors"]["projects"]["value"] + 0.10 * 1)
    assert abs(r["total"] - round(exp, 2)) < 0.01
