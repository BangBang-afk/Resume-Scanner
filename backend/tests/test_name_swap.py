from app.services.extractor import extract_profile
from app.services.masking import mask_pii
from app.services.scoring import score_candidate

JD = {"required": ["python", "fastapi"], "preferred": ["docker"],
      "min_years": 2, "responsibilities_text": "python fastapi backend",
      "required_degree_level": 1}


def _score(raw: str) -> float:
    from app.services.parser import parse_file

    text, q = parse_file("r.txt", raw.encode())
    masked, _ = mask_pii(text)
    profile, ry = extract_profile(masked, q)
    return score_candidate(profile, ry, masked, JD)["total"]


def test_name_swap_delta_within_tolerance():
    import pathlib

    base = pathlib.Path(__file__).resolve().parents[2] / "sample_data" / "resumes"
    ta = (base / "nameswap_a.txt").read_text(encoding="utf-8")
    tb = (base / "nameswap_b.txt").read_text(encoding="utf-8")
    assert abs(_score(ta) - _score(tb)) <= 1.0
