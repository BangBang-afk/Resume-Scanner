"""Explanation from structured score + evidence only. No PII terms."""
from __future__ import annotations

import json
import os
import re
import urllib.request

BANNED = ["name", "gender", "age", "nationality", "photo", "male", "female"]


_DISPLAY = {"machine learning": "Machine Learning", "postgresql": "PostgreSQL",
            "javascript": "JavaScript", "typescript": "TypeScript", "kubernetes": "Kubernetes",
            "python": "Python", "docker": "Docker", "fastapi": "FastAPI", "django": "Django",
            "react": "React", "sql": "SQL", "aws": "AWS"}


def _nice(s: str) -> str:
    k = str(s).strip().lower()
    return _DISPLAY.get(k, str(s).strip().replace("_", " ").title())


def _template(score: dict, masked_text: str) -> dict:
    strengths = [{"point": f"Matched {_nice(s)}", "quote": q["quote"]}
                 for s, q in zip(score.get("matched_skills", [])[:3],
                                 (score.get("evidence", []) + [{"quote": ""}])[:3]) if q.get("quote")]
    concerns = [{"point": f"Missing {_nice(s)}", "quote": None} for s in score.get("missing_skills", [])[:3]]
    if not strengths and score.get("evidence"):
        strengths = [{"point": "Relevant experience shown", "quote": score["evidence"][0]["quote"]}]
    return {
        "summary": f"Scores {score.get('total')} ({score.get('band')}). "
                   f"Matched {len(score.get('matched_skills', []))}, missing {len(score.get('missing_skills', []))}.",
        "strengths": strengths[:3],
        "concerns": concerns[:3],
        "factor_notes": {k: f"{k}={v.get('value')} x weight {v.get('weight')}"
                         for k, v in score.get("factors", {}).items()},
    }


def explain(score: dict, masked_text: str) -> dict:
    out = _template(score, masked_text)
    provider = os.getenv("LLM_PROVIDER", "none").lower()
    if provider in ("gemini", "auto") and os.getenv("GEMINI_API_KEY"):
        try:
            model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={os.getenv('GEMINI_API_KEY')}"
            prompt = ("Write JSON {summary, strengths:[{point,quote}], concerns:[{point,quote}], "
                      "factor_notes:{must,preferred,experience,projects,education}}. 2-sentence summary max. "
                      "Only use given evidence quotes verbatim. Never mention name/gender/age/nationality/photo. "
                      f"Score={json.dumps(score)[:3000]}")
            body = json.dumps({"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0}}).encode()
            req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=8) as r:
                data = json.loads(r.read().decode())
            txt = data["candidates"][0]["content"]["parts"][0]["text"]
            txt = re.sub(r"^```json|^```|```$", "", txt.strip(), flags=re.MULTILINE).strip()
            cand = json.loads(txt)
            # validate quotes + ban PII
            for sec in ("strengths", "concerns"):
                for item in cand.get(sec, []):
                    q = item.get("quote")
                    if q and q not in masked_text:
                        item["quote"] = None
            blob = json.dumps(cand).lower()
            if any(b in blob for b in BANNED):
                return out
            return cand
        except Exception:
            pass
    # validate template quotes too
    for s in out["strengths"]:
        if s.get("quote") and s["quote"] not in masked_text:
            s["quote"] = None
    return out
