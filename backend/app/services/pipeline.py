"""Background processing: parse -> mask -> extract -> score -> store."""
from __future__ import annotations

from ..db import SessionLocal
from ..models import Candidate, Job


def process_candidate(candidate_id: str):
    db = SessionLocal()
    try:
        cand = db.get(Candidate, candidate_id)
        if not cand:
            return
        job = db.get(Job, cand.job_id)
        if not job:
            cand.status = "error"
            db.commit()
            return
        from .extractor import extract_profile
        from .masking import mask_pii
        from .parser import parse_file
        from .scoring import score_candidate

        cand.status = "parsing"
        db.commit()
        # raw_text stores a latin-1 round-trip for binary formats (pdf/docx bytes are
        # not utf-8-safe as text), or straight utf-8 text for .txt uploads.
        if cand.filename.endswith((".pdf", ".docx")):
            raw_bytes = (cand.raw_text or "").encode("latin-1", errors="ignore")
        else:
            raw_bytes = (cand.raw_text or "").encode("utf-8", errors="ignore")
        text, quality = parse_file(cand.filename, raw_bytes)

        cand.status = "extracting"
        db.commit()
        masked, identity = mask_pii(text)
        profile, relevant_years = extract_profile(masked, quality)

        cand.status = "scoring"
        db.commit()
        jd = {"required": job.required_json or [], "preferred": job.preferred_json or [],
              "min_years": job.min_years or 2,
              "responsibilities_text": job.jd_text or "",
              "required_degree_level": 1}
        score = score_candidate(profile, relevant_years, masked, jd)

        cand.masked_text = masked
        cand.identity_json = identity
        cand.profile_json = profile.model_dump()
        cand.score_json = score
        cand.relevant_years = relevant_years
        cand.status = "done"
        db.commit()
    except Exception:
        try:
            cand = db.get(Candidate, candidate_id)
            if cand:
                cand.status = "error"
                db.commit()
        except Exception:
            pass
    finally:
        db.close()
