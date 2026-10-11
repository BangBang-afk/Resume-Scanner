"""Eval: pipeline on sample set vs gold labels. Only quote numbers this prints."""
import csv
import os
import pathlib
import sys
import time

os.environ["LLM_PROVIDER"] = "none"
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "backend"))

from app.services.extractor import extract_profile  # noqa: E402
from app.services.jd_analyzer import analyze_jd  # noqa: E402
from app.services.masking import mask_pii  # noqa: E402
from app.services.parser import parse_file  # noqa: E402
from app.services.scoring import assign_ranks, score_candidate  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "sample_data" / "resumes"
JD_TEXT = (ROOT / "sample_data" / "jd_python_backend.txt").read_text(encoding="utf-8")

gold: dict[str, str] = {}
with open(ROOT / "eval" / "gold_shortlist.csv", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        gold[row["resume"]] = row["decision"]


def main() -> None:
    auto = analyze_jd(JD_TEXT)
    jd = {**auto, "responsibilities_text": JD_TEXT, "required_degree_level": 1}
    print("JD required:", jd["required"], "preferred:", jd["preferred"])
    items, times = [], []
    for path in sorted(SAMPLES.glob("*.txt")):
        raw = path.read_bytes()
        t0 = time.time()
        text, q = parse_file(path.name, raw)
        masked, _ = mask_pii(text)
        profile, ry = extract_profile(masked, q)
        r = score_candidate(profile, ry, masked, jd)
        dt = time.time() - t0
        times.append(dt)
        items.append({"candidate_id": path.name, "total": r["total"], "decision": r["decision"],
                      "flags": r["flags"], "missing": r["missing_skills"]})
    ranked = assign_ranks([{"candidate_id": i["candidate_id"], "total": i["total"],
                            "must_coverage": 0, "preferred_coverage": 0, "mean_confidence": 0} for i in items])
    order = {r["candidate_id"]: r["rank"] for r in ranked}
    by_id = {i["candidate_id"]: i for i in items}

    tp = fp = fn = 0
    for name, g in gold.items():
        s = by_id[name]["decision"]
        if s == "shortlist" and g == "shortlist":
            tp += 1
        elif s == "shortlist":
            fp += 1
        elif g == "shortlist":
            fn += 1
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    print(f"shortlist precision={prec:.2f} recall={rec:.2f} F1={f1:.2f} (tp={tp} fp={fp} fn={fn})")
    print("ranking:")
    for r in ranked:
        i = by_id[r["candidate_id"]]
        print(f"  #{r['rank']} {r['candidate_id']} total={i['total']} sys={i['decision']} gold={gold[r['candidate_id']]} flags={i['flags']}")

    # name-swap
    ta = (SAMPLES / "nameswap_a.txt").read_bytes()
    tb = (SAMPLES / "nameswap_b.txt").read_bytes()

    def _score(raw: bytes) -> float:
        text, q = parse_file("r.txt", raw)
        masked, _ = mask_pii(text)
        profile, ry = extract_profile(masked, q)
        return score_candidate(profile, ry, masked, jd)["total"]

    delta = abs(_score(ta) - _score(tb))
    print(f"name-swap delta={delta:.3f} (tolerance 1.0) {'PASS' if delta <= 1.0 else 'FAIL'}")
    avg = sum(times) / len(times)
    print(f"avg time per resume={avg:.2f}s over {len(times)} resumes")


if __name__ == "__main__":
    main()
