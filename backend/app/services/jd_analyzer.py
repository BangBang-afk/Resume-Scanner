"""JD -> required/preferred skills. Manual entry always works, LLM optional."""
from __future__ import annotations

import json
import os
import re
import urllib.request


def _rule_split(jd_text: str) -> tuple[list[str], list[str], float]:
    from .taxonomy import _ALIAS_TO_CANONICAL

    low = jd_text.lower()
    pref_at = low.find("prefer")
    required: list[str] = []
    preferred: list[str] = []
    for alias, canon in _ALIAS_TO_CANONICAL.items():
        m = re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", low)
        if not m:
            continue
        if canon in required or canon in preferred:
            continue
        if pref_at != -1 and m.start() > pref_at:
            preferred.append(canon)
        else:
            required.append(canon)
    if not required:
        required = preferred[:5] or required
        preferred = [s for s in preferred if s not in required]
    m = re.search(r"(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)", low)
    min_years = float(m.group(1)) if m else 2.0
    return required, preferred, min_years


def analyze_jd(jd_text: str) -> dict:
    provider = os.getenv("LLM_PROVIDER", "none").lower()
    if provider in ("gemini", "auto") and os.getenv("GEMINI_API_KEY"):
        try:
            model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={os.getenv('GEMINI_API_KEY')}"
            prompt = (
                'Split JD into JSON {"required":[],"preferred":[],"min_years":2}. '
                "required=must-have skills, preferred=nice-to-have. JSON only. JD:\n" + jd_text[:4000]
            )
            body = json.dumps({"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0}}).encode()
            req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=8) as r:
                data = json.loads(r.read().decode())
            txt = data["candidates"][0]["content"]["parts"][0]["text"]
            txt = re.sub(r"^```json|^```|```$", "", txt.strip(), flags=re.MULTILINE).strip()
            out = json.loads(txt)
            return {"required": out.get("required", []), "preferred": out.get("preferred", []),
                    "min_years": float(out.get("min_years", 2.0))}
        except Exception:
            pass
    required, preferred, min_years = _rule_split(jd_text)
    return {"required": required, "preferred": preferred, "min_years": min_years}
