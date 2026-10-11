"""Interview questions targeting missing skills."""
from __future__ import annotations


def questions_for(missing_skills: list[str]) -> list[str]:
    out: list[str] = []
    for s in missing_skills[:5]:
        out.append(f"Walk me through a project where you used {s} in production.")
        if len(out) >= 5:
            break
    if not out:
        out = ["Describe your toughest backend debugging story and the trade-offs you made."]
    return out[:5]
