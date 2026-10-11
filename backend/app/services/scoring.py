"""Deterministic scoring per brief section 5. LLM never produces final number."""
from __future__ import annotations

from .embeddings import cosine, embed
from .taxonomy import normalize

WEIGHTS = {"must": 0.40, "preferred": 0.20, "experience": 0.20, "projects": 0.10, "education": 0.10}
RELATED_THRESHOLD = 0.75


def _skill_score(jd_skill: str, cand_canonicals: set[str], cand_texts: list[str]) -> tuple[float, str]:
    canon = normalize(jd_skill)
    if canon in cand_canonicals:
        return 1.0, "exact"
    # related via embedding
    try:
        js = embed(canon)
        best = 0.0
        for t in cand_texts:
            best = max(best, cosine(js, embed(t)))
        if best >= RELATED_THRESHOLD:
            return 0.7, "related"
    except Exception:
        pass
    return 0.0, "missing"


def _education_score(profile, required_level: int | None) -> float:
    from ..schemas import ResumeProfile

    assert isinstance(profile, ResumeProfile)
    if required_level is None:
        return 1.0
    levels = [0]
    rank = {"b.tech": 1, "btech": 1, "bachelor": 1, "b.sc": 1, "bsc": 1,
            "m.tech": 2, "mtech": 2, "master": 2, "m.sc": 2, "msc": 2,
            "phd": 3, "ph.d": 3}
    for e in profile.education:
        d = (e.degree or "").lower()
        levels.append(rank.get(d, 1 if d else 0))
    best = max(levels)
    if best >= required_level:
        return 1.0
    if best == required_level - 1 and best > 0:
        return 0.6
    return 0.3


def score_candidate(profile, relevant_years: float, masked_text: str, jd: dict) -> dict:
    required: list[str] = jd.get("required", [])
    preferred: list[str] = jd.get("preferred", [])
    min_years: float = float(jd.get("min_years", 2) or 2)
    jd_resp: str = jd.get("responsibilities_text", " ".join(required + preferred))

    cand_canonicals = {(s.canonical or normalize(s.raw)) for s in profile.skills}
    cand_texts = [s.raw for s in profile.skills] + [masked_text[:2000]]

    matched, related, missing = [], [], []
    must_scores: list[float] = []
    for sk in required:
        v, kind = _skill_score(sk, cand_canonicals, cand_texts)
        must_scores.append(v)
        (matched if kind == "exact" else related if kind == "related" else missing).append(sk)
    pref_scores: list[float] = []
    for sk in preferred:
        v, kind = _skill_score(sk, cand_canonicals, cand_texts)
        pref_scores.append(v)
        (matched if kind == "exact" else related if kind == "related" else missing).append(sk)

    must = sum(must_scores) / len(must_scores) if must_scores else 1.0
    pref = sum(pref_scores) / len(pref_scores) if pref_scores else 1.0

    # experience
    exp_text = " ".join((e.summary or "") for e in profile.experience) or masked_text[:2000]
    try:
        exp_cos = cosine(embed(exp_text[:2000]), embed(jd_resp[:2000]))
    except Exception:
        exp_cos = 0.0
    experience = 0.5 * min(1.0, relevant_years / min_years) + 0.5 * max(0.0, min(1.0, exp_cos))

    # projects
    proj_text = " ".join((p.summary or "") for p in profile.projects)
    if not proj_text:
        projects_val: float | None = None
    else:
        try:
            pc = cosine(embed(proj_text[:2000]), embed(jd_resp[:2000]))
        except Exception:
            pc = 0.0
        projects_val = max(0.0, min(1.0, (pc - 0.3) / (0.8 - 0.3)))

    education = _education_score(profile, jd.get("required_degree_level"))

    factors: dict[str, dict] = {
        "must": {"value": round(must, 3), "weight": WEIGHTS["must"]},
        "preferred": {"value": round(pref, 3), "weight": WEIGHTS["preferred"]},
        "experience": {"value": round(experience, 3), "weight": WEIGHTS["experience"]},
        "projects": {"value": round(projects_val, 3) if projects_val is not None else None, "weight": WEIGHTS["projects"]},
        "education": {"value": round(education, 3), "weight": WEIGHTS["education"]},
    }

    flags: list[str] = []
    # incomplete: section absent or parse_quality low -> N/A (except must)
    if "projects" in getattr(profile, "missing_sections", []) or projects_val is None:
        factors["projects"] = {"value": None, "weight": WEIGHTS["projects"]}
    if profile.parse_quality < 0.5:
        flags.append("INCOMPLETE_RESUME")
        for k in ("preferred", "experience", "projects", "education"):
            if factors[k]["value"] is not None and factors[k]["value"] == 0:
                factors[k] = {"value": None, "weight": WEIGHTS[k]}
    if any(factors[k]["value"] is None for k in factors if k != "must"):
        if "INCOMPLETE_RESUME" not in flags:
            flags.append("INCOMPLETE_RESUME")

    # renormalize over present factors (must never dropped)
    present = {k: v for k, v in factors.items() if v["value"] is not None}
    wsum = sum(v["weight"] for v in present.values())
    total = 100 * sum(v["value"] * v["weight"] for v in present.values()) / wsum if wsum else 0.0

    # must-have gate
    if any(s < 0.5 for s in must_scores):
        flags.append("MISSING_MUST_HAVE")
        total = min(total, 69.0)

    total = round(total, 2)
    band = "strong" if total >= 80 else "moderate" if total >= 60 else "weak"
    decision = "shortlist" if total >= 80 else "review" if total >= 60 else "reject"

    mean_conf = 0.0
    confs = [s.evidence.confidence for s in profile.skills if s.evidence]
    if confs:
        mean_conf = sum(confs) / len(confs)

    evidence = [
        {"quote": s.evidence.quote, "skill": s.canonical or s.raw}
        for s in profile.skills if s.evidence and s.evidence.quote in masked_text
    ]

    return {
        "total": total,
        "band": band,
        "decision": decision,
        "factors": factors,
        "matched_skills": matched,
        "related_skills": related,
        "missing_skills": missing,
        "flags": flags,
        "evidence": evidence,
        "must_coverage": round(must, 3),
        "preferred_coverage": round(pref, 3),
        "mean_confidence": round(mean_conf, 3),
        "relevant_years": relevant_years,
    }


def assign_ranks(items: list[dict]) -> list[dict]:
    """Sort desc by total, group ties within 2.0, order tie-break rules."""
    ordered = sorted(items, key=lambda d: (-d["total"], d.get("candidate_id", "")))
    # tie groups: sequential within 2.0 of group top
    group_id = 0
    group_top: float | None = None
    for d in ordered:
        if group_top is None or abs(group_top - d["total"]) > 2.0:
            group_id += 1
            group_top = d["total"]
        d["tie_group"] = group_id
    # stable tie-break inside group
    ranked: list[dict] = []
    i = 0
    while i < len(ordered):
        j = i
        while j < len(ordered) and ordered[j]["tie_group"] == ordered[i]["tie_group"]:
            j += 1
        group = ordered[i:j]
        group.sort(key=lambda d: (-d.get("must_coverage", 0), -d.get("preferred_coverage", 0),
                                  -d.get("mean_confidence", 0), str(d.get("candidate_id", ""))))
        ranked.extend(group)
        i = j
    for idx, d in enumerate(ranked, start=1):
        d["rank"] = idx
        d["close_call"] = sum(1 for x in ranked if x["tie_group"] == d["tie_group"]) > 1
    return ranked
