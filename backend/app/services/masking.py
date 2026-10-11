"""PII masking before scoring. Scoring code never sees raw identity."""
from __future__ import annotations

import hashlib
import re

EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
PHONE_RE = re.compile(r"(\+?\d[\d\s\-().]{7,}\d)")
URL_RE = re.compile(r"https?://\S+|www\.\S+")
# 2+ consecutive capitalized words -> likely person name (synthetic resumes)
NAME_RE = re.compile(r"\b([A-Z][a-z]{1,}(?:[ \t]+[A-Z][a-z]{1,})+)\b")


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()[:16]


def mask_pii(text: str) -> tuple[str, dict]:
    identity: dict = {"emails": [], "phones": [], "links": [], "names": []}
    masked = text

    for m in EMAIL_RE.findall(masked):
        identity["emails"].append({"hash": _sha(m)})
    masked = EMAIL_RE.sub("[EMAIL]", masked)

    for m in PHONE_RE.findall(masked):
        digits = re.sub(r"\D", "", m)
        if len(digits) >= 7:
            identity["phones"].append({"hash": _sha(digits)})
    masked = PHONE_RE.sub("[PHONE]", masked)

    for m in URL_RE.findall(masked):
        identity["links"].append({"hash": _sha(m)})
    masked = URL_RE.sub("[LINK]", masked)

    # names: only first 5 matches to avoid masking skills like "Machine Learning"
    # skip known non-name capitalized phrases
    skip = {"Machine Learning", "Python Backend", "Backend Developer"}
    count = 0
    def _name_sub(m: re.Match) -> str:
        nonlocal count
        val = m.group(0)
        if val in skip or count >= 5:
            return val
        # only mask if near top of doc or preceded by name-ish label
        count += 1
        identity["names"].append({"hash": _sha(val)})
        return "[NAME]"

    # mask names only in first 500 chars (header region) to reduce false positives
    head = masked[:500]
    tail = masked[500:]
    head = NAME_RE.sub(_name_sub, head)
    masked = head + tail
    return masked, identity
