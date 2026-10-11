"""Rule-based extractor + Gemini wrapper -> ResumeProfile. LLM never scores."""
from __future__ import annotations

import json
import os
import re
import urllib.request

from ..schemas import Education, Evidence, Experience, Project, ResumeProfile, SkillMention
from .taxonomy import normalize

SECTION_HEADERS = ["experience", "projects", "project", "education", "skills", "certifications"]


def _find_quote(snippet: str, text: str) -> Evidence | None:
    if snippet and snippet in text:
        return Evidence(quote=snippet, confidence=0.9)
    return None


def _split_sections(text: str) -> dict[str, str]:
    lowers = text.lower()
    idxs: list[tuple[int, str]] = []
    for h in SECTION_HEADERS:
        for m in re.finditer(rf"(?m)^\s*{h}\s*:?\s*$", lowers):
            idxs.append((m.start(), h))
    idxs.sort()
    out: dict[str, str] = {}
    for i, (pos, h) in enumerate(idxs):
        end = idxs[i + 1][0] if i + 1 < len(idxs) else len(text)
        # map header line position back to original text
        out[h] = text[pos:end].strip()
    if not out:
        out["full"] = text
    return out


def _extract_skills(text: str, sections: dict[str, str]) -> list[SkillMention]:
    from .taxonomy import _ALIAS_TO_CANONICAL

    found: list[SkillMention] = []
    seen: set[str] = set()
    low = text.lower()
    for alias, canon in _ALIAS_TO_CANONICAL.items():
        # word-boundary search
        if re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", low):
            if canon in seen:
                continue
            seen.add(canon)
            # evidence: first line containing alias
            ev = None
            for line in text.splitlines():
                if alias in line.lower():
                    ev = _find_quote(line.strip()[:200], text)
                    break
            found.append(SkillMention(raw=alias, canonical=canon, evidence=ev))
    return found


def _extract_experience(masked: str, sections: dict[str, str]) -> tuple[list[Experience], float]:
    exp_text = sections.get("experience", sections.get("full", masked))
    exps: list[Experience] = []
    # split on blank lines / bullet jobs
    blocks = [b.strip() for b in re.split(r"\n\s*\n", exp_text) if b.strip()][:4]
    total_years = 0.0
    for b in blocks:
        if len(b) < 20:
            continue
        m = re.search(r"(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)", b.lower())
        yrs = float(m.group(1)) if m else None
        if yrs:
            total_years += yrs
        first_line = b.splitlines()[0][:120]
        ev = _find_quote(first_line.strip(), masked)
        exps.append(
            Experience(
                title=first_line[:80] if first_line else None,
                org=None,
                start=None,
                end=None,
                years=yrs,
                summary=b[:300],
                skills=[],
                evidence=ev,
            )
        )
    # relevant years approx = sum explicit mentions, cap 10
    return exps, min(total_years, 10.0)


def _extract_projects(masked: str, sections: dict[str, str]) -> list[Project]:
    proj_text = sections.get("projects", sections.get("project", ""))
    if not proj_text:
        return []
    blocks = [b.strip() for b in re.split(r"\n\s*\n", proj_text) if b.strip()][:4]
    out: list[Project] = []
    for b in blocks:
        if len(b) < 15:
            continue
        first = b.splitlines()[0][:100]
        out.append(Project(name=first, summary=b[:300], skills=[], evidence=_find_quote(first.strip(), masked)))
    return out


DEGREE_RANK = {"phd": 3, "ph.d": 3, "m.tech": 2, "mtech": 2, "master": 2, "m.sc": 2, "msc": 2, "b.tech": 1, "btech": 1, "bachelor": 1, "b.sc": 1, "bsc": 1}


def _extract_education(masked: str, sections: dict[str, str]) -> list[Education]:
    edu_text = sections.get("education", "")
    if not edu_text:
        return []
    out: list[Education] = []
    for line in edu_text.splitlines()[:8]:
        l = line.strip().strip("-•* ")
        if len(l) < 5:
            continue
        low = l.lower()
        deg = None
        for k in DEGREE_RANK:
            if k in low:
                deg = k
                break
        m = re.search(r"(19|20)\d{2}", l)
        out.append(Education(degree=deg, field=l[:80], institution=None, year=int(m.group(0)) if m else None))
    return out


def rule_extract(masked_text: str, parse_quality: float) -> tuple[ResumeProfile, float]:
    sections = _split_sections(masked_text)
    skills = _extract_skills(masked_text, sections)
    exps, relevant_years = _extract_experience(masked_text, sections)
    projs = _extract_projects(masked_text, sections)
    edus = _extract_education(masked_text, sections)
    missing: list[str] = []
    for s in ("experience", "projects", "education", "skills"):
        if s not in sections:
            missing.append(s)
    certs: list[str] = []
    if "certifications" in sections:
        certs = [l.strip("-•* ")[:80] for l in sections["certifications"].splitlines() if len(l.strip()) > 4][:5]
    profile = ResumeProfile(
        skills=skills,
        experience=exps,
        projects=projs,
        education=edus,
        certifications=certs,
        missing_sections=missing,
        parse_quality=parse_quality,
    )
    return profile, relevant_years


def _gemini_extract(masked_text: str, timeout: int = 8) -> dict | None:
    key = os.getenv("GEMINI_API_KEY", "")
    if not key:
        return None
    model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    prompt = (
        "Extract resume JSON only. Schema: {skills:[{raw, evidence:{quote,confidence}}], "
        "experience:[{title,org,start,end,years,summary}], projects:[{name,summary}], "
        "education:[{degree,field,institution,year}], certifications:[], missing_sections:[], parse_quality:0..1}. "
        "Quotes must be exact substrings. Resume:\n" + masked_text[:6000]
    )
    body = json.dumps({"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0}}).encode()
    try:
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode())
        txt = data["candidates"][0]["content"]["parts"][0]["text"]
        # strip code fences
        txt = re.sub(r"^```json|^```|```$", "", txt.strip(), flags=re.MULTILINE).strip()
        return json.loads(txt)
    except Exception:
        return None


def extract_profile(masked_text: str, parse_quality: float) -> tuple[ResumeProfile, float]:
    provider = os.getenv("LLM_PROVIDER", "none").lower()
    if provider in ("gemini", "auto"):
        raw = _gemini_extract(masked_text)
        if raw:
            try:
                # normalize through taxonomy + validate quotes
                skills: list[SkillMention] = []
                for s in raw.get("skills", [])[:30]:
                    r = str(s.get("raw", ""))[:60]
                    q = (s.get("evidence") or {}).get("quote", "")
                    ev = _find_quote(q, masked_text)
                    skills.append(SkillMention(raw=r, canonical=normalize(r), evidence=ev))
                prof = ResumeProfile(
                    skills=skills,
                    experience=[],
                    projects=[],
                    education=[],
                    certifications=[str(c)[:60] for c in raw.get("certifications", [])[:5]],
                    missing_sections=[str(x) for x in raw.get("missing_sections", [])[:5]],
                    parse_quality=float(raw.get("parse_quality", parse_quality)),
                )
                return prof, 0.0
            except Exception:
                pass
    return rule_extract(masked_text, parse_quality)
