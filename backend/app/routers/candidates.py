import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..db import get_db
from ..models import AuditLog, Candidate, Job, Override, User
from ..services.explain import explain

logger = logging.getLogger(__name__)

router = APIRouter()


# --- PII retention -----------------------------------------------------------
# raw_text keeps the original resume bytes; masked_text is the redacted version
# used for scoring/display. PURGE_RAW_TEXT_AFTER_DAYS controls how long the
# original (PII-full) text is kept before zeroing it out.
from datetime import datetime, timedelta  # noqa: E402

PURGE_RAW_TEXT_AFTER_DAYS = int(__import__("os").getenv("PURGE_RAW_TEXT_AFTER_DAYS", "30"))


def purge_stale_raw_text(db: Session, days: int = PURGE_RAW_TEXT_AFTER_DAYS) -> int:
    cutoff = datetime.utcnow() - timedelta(days=days)
    stale = db.query(Candidate).filter(
        Candidate.raw_text != "", Candidate.created_at < cutoff).all()
    for c in stale:
        c.raw_text = ""
        db.add(AuditLog(event="raw_text_purged", payload_json={"candidate_id": c.id}))
    if stale:
        db.commit()
    return len(stale)


class OverrideIn(BaseModel):
    new_decision: str = Field(min_length=1, max_length=20)
    reason: str = Field(min_length=1, max_length=500)
    user: str = Field(default="recruiter", min_length=1, max_length=80)


@router.get("/candidates/{cid}")
def candidate_detail(cid: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    c = db.get(Candidate, cid)
    if not c:
        raise HTTPException(404, "candidate not found")
    ov = db.query(Override).filter(Override.candidate_id == cid).order_by(Override.id.desc()).first()
    score = c.score_json or {}
    return {"id": c.id, "filename": c.filename, "status": c.status,
            "profile": c.profile_json or {}, "score": score,
            "evidence": score.get("evidence", []),
            "explanation": explain(score, c.masked_text or "") if c.status == "done" else None,
            "system_decision": score.get("decision"),
            "final_decision": ov.new_decision if ov else score.get("decision"),
            "overridden": bool(ov),
            "masked_text": (c.masked_text or "")[:4000]}
@router.delete("/candidates/{cid}")
def delete_candidate(cid: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Hard delete: the candidate must be deletable per privacy policy (GDPR art. 17
    style erasure). Overrides cascade via DB FK; audit log keeps a non-PII trace."""
    c = db.get(Candidate, cid)
    if not c:
        raise HTTPException(404, "candidate not found")
    db.add(AuditLog(event="candidate_deleted", payload_json={
        "candidate_id": cid, "job_id": c.job_id, "delete_by": user.email}))
    db.query(Override).filter(Override.candidate_id == cid).delete()
    db.delete(c)
    db.commit()
    return {"ok": True, "deleted": cid}


@router.post("/candidates/{cid}/override")
def override(cid: str, payload: OverrideIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    c = db.get(Candidate, cid)
    if not c:
        raise HTTPException(404, "candidate not found")
    if payload.new_decision not in ("shortlist", "review", "reject"):
        raise HTTPException(400, "bad decision")
    if not payload.reason or not payload.reason.strip():
        raise HTTPException(400, "reason required")
    old = (c.score_json or {}).get("decision", "review")
    ov = Override(candidate_id=cid, old_decision=old, new_decision=payload.new_decision,
                  reason=payload.reason.strip(), user=user.email)
    db.add(ov)
    db.add(AuditLog(event="override", payload_json={"candidate_id": cid, "old": old,
                                                   "new": payload.new_decision, "reason": payload.reason,
                                                   "user": user.email}))
    db.commit()
    return {"ok": True, "old_decision": old, "final_decision": payload.new_decision}


@router.get("/candidates/{cid}/interview-questions")
def interview_questions(cid: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    c = db.get(Candidate, cid)
    if not c:
        raise HTTPException(404, "candidate not found")
    try:
        from ..services.interview import questions_for

        return {"questions": questions_for((c.score_json or {}).get("missing_skills", []))}
    except Exception:
        # LLM-backed question generation can fail offline; deterministic fallback
        # keeps the endpoint usable, failure visible in server logs.
        logger.exception("interview question generation failed for %s", cid)
        missing = (c.score_json or {}).get("missing_skills", [])
        return JSONResponse({"questions": [f"Describe your experience with {s}." for s in missing[:5]]})
