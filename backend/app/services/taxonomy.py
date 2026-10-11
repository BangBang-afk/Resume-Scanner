import json
from pathlib import Path

_TAXONOMY_PATH = Path(__file__).resolve().parent.parent / "data" / "skills_taxonomy.json"

with open(_TAXONOMY_PATH, encoding="utf-8") as f:
    _DATA: dict[str, list[str]] = json.load(f)

_ALIAS_TO_CANONICAL: dict[str, str] = {}
for canonical, aliases in _DATA.items():
    _ALIAS_TO_CANONICAL[canonical.lower()] = canonical
    for alias in aliases:
        _ALIAS_TO_CANONICAL[alias.lower()] = canonical


def normalize(raw: str) -> str:
    key = raw.strip().lower()
    return _ALIAS_TO_CANONICAL.get(key, raw.strip())
