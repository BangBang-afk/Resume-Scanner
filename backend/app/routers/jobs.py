import csv
import io
import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

MAX_FILES = 200
MAX_FILE_BYTES = 10 * 1024 * 1024
ALLOWED_EXTS = (".pdf", ".docx", ".txt")


def _skill_list(v: list[str] | None) -> list[str] | None:
    if v is None:
        return None
    return [s.strip()[:60] for s in v[:50] if s and s.strip()]

from ..auth import get_current_user
from ..config import DEFAULT_WEIGHTS
from ..db import get_db
from ..models import AuditLog, Candidate, Job, Override, User
from ..services.jd_analyzer import analyze_jd
from ..services.pipeline import process_candidate
from ..services.scoring import assign_ranks

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/jobs")
def list_jobs(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    jobs = db.query(Job).order_by(Job.created_at.desc()).all()
    out = []
    for j in jobs:
        n = db.query(Candidate).filter(Candidate.job_id == j.id).count()
        out.append({"id": j.id, "title": j.title, "required": j.required_json,
                    "preferred": j.preferred_json, "resumes": n, "created_at": str(j.created_at)})
    return {"jobs": out}


class JobIn(BaseModel):
    title: str = Field(default="Untitled", min_length=1, max_length=120)
    jd_text: str = Field(default="", max_length=20000)
    required: list[str] | None = Field(default=None, max_length=50)
    preferred: list[str] | None = Field(default=None, max_length=50)
    min_years: float | None = Field(default=None, ge=0, le=50)
    weights: dict | None = None


class SkillsIn(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    required: list[str] | None = Field(default=None, max_length=50)
    preferred: list[str] | None = Field(default=None, max_length=50)
    min_years: float | None = Field(default=None, ge=0, le=50)
    weights: dict | None = None


@router.post("/jobs")
def create_job(payload: JobIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    auto = analyze_jd(payload.jd_text) if payload.jd_text else {"required": [], "preferred": [], "min_years": 2.0}
    job = Job(id=uuid.uuid4().hex[:12], title=payload.title.strip(), jd_text=payload.jd_text,
              required_json=_skill_list(payload.required) if payload.required is not None else auto["required"],
              preferred_json=_skill_list(payload.preferred) if payload.preferred is not None else auto["preferred"],
              min_years=payload.min_years if payload.min_years is not None else auto["min_years"],
              weights_json=payload.weights or DEFAULT_WEIGHTS)
    db.add(job)
    db.commit()
    return {"id": job.id, "title": job.title, "required": job.required_json,
            "preferred": job.preferred_json, "min_years": job.min_years, "weights": job.weights_json}


@router.get("/jobs/{job_id}")
def get_job(job_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(404, "job not found")
    return {"id": job.id, "title": job.title, "jd_text": job.jd_text, "required": job.required_json,
            "preferred": job.preferred_json, "min_years": job.min_years, "weights": job.weights_json}


@router.put("/jobs/{job_id}/skills")
def update_skills(job_id: str, payload: SkillsIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from ..schemas import ResumeProfile
    from ..services.scoring import score_candidate

    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(404, "job not found")
    if payload.title is not None:
        job.title = payload.title.strip()
    if payload.required is not None:
        job.required_json = _skill_list(payload.required)
    if payload.preferred is not None:
        job.preferred_json = _skill_list(payload.preferred)
    if payload.min_years is not None:
        job.min_years = payload.min_years
    if payload.weights is not None:
        job.weights_json = payload.weights
    db.commit()
    # Details changed -> existing scores are stale. Re-score every finished
    # candidate against the new skills so the ranking stays truthful.
    rescored = 0
    jd = {"required": job.required_json or [], "preferred": job.preferred_json or [],
          "min_years": job.min_years or 2, "responsibilities_text": job.jd_text or "",
          "required_degree_level": 1}
    for c in db.query(Candidate).filter(Candidate.job_id == job_id, Candidate.status == "done").all():
        try:
            profile = ResumeProfile(**(c.profile_json or {}))
            c.score_json = score_candidate(profile, c.relevant_years or 0.0, c.masked_text or "", jd)
            rescored += 1
        except Exception:
            continue
    db.commit()
    return {"ok": True, "rescored": rescored}


@router.delete("/jobs/{job_id}")
def delete_job(job_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(404, "job not found")
    cands = db.query(Candidate).filter(Candidate.job_id == job_id).all()
    for c in cands:
        db.query(Override).filter(Override.candidate_id == c.id).delete()
        db.delete(c)
    db.delete(job)
    db.add(AuditLog(event="job_deleted", payload_json={"job_id": job_id, "title": job.title,
                                                       "candidates": len(cands), "by": user.email}))
    db.commit()
    return {"ok": True, "deleted_candidates": len(cands)}


@router.post("/jobs/{job_id}/resumes")
async def upload_resumes(job_id: str, files: list[UploadFile], bg: BackgroundTasks,
                         db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(404, "job not found")
    if len(files) > MAX_FILES:
        raise HTTPException(400, f"too many files (max {MAX_FILES})")
    # Validate every file BEFORE inserting anything, so one bad file cannot leave
    # the batch half-committed (candidates queued for background processing).
    rows: list[tuple[str, str, str]] = []  # (name, raw_text, encoded_bytes)
    for f in files:
        name = (f.filename or "resume.txt")[-120:]
        if not name.lower().endswith(ALLOWED_EXTS):
            raise HTTPException(400, f"bad file type for {name}: use PDF, DOCX or TXT")
        content = await f.read(MAX_FILE_BYTES + 1)
        if len(content) > MAX_FILE_BYTES:
            raise HTTPException(400, f"file too large: {name} (max 10MB)")
        if not content.strip():
            raise HTTPException(400, f"empty file: {name}")
        # store bytes-safe: latin-1 roundtrip for binary, utf-8 text otherwise
        try:
            raw_text = content.decode("utf-8")
        except Exception:
            raw_text = content.decode("latin-1", errors="ignore")
        rows.append((name, raw_text, content))
    ids: list[str] = []
    for name, raw_text, _content in rows:
        cand = Candidate(id=uuid.uuid4().hex[:12], job_id=job_id, filename=name,
                         raw_text=raw_text, status="queued")
        db.add(cand)
        ids.append(cand.id)
    db.commit()
    for cid in ids:
        bg.add_task(process_candidate, cid)
    db.add(AuditLog(event="resumes_uploaded", payload_json={"job_id": job_id, "count": len(ids)}))
    db.commit()
    return {"candidate_ids": ids}


@router.get("/jobs/{job_id}/status")
def job_status(job_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    cands = db.query(Candidate).filter(Candidate.job_id == job_id).all()
    return [{"id": c.id, "filename": c.filename, "status": c.status} for c in cands]


def _final_decisions(db: Session, cands: list[Candidate]) -> dict[str, str]:
    out: dict[str, str] = {}
    for c in cands:
        ov = db.query(Override).filter(Override.candidate_id == c.id).order_by(Override.id.desc()).first()
        out[c.id] = ov.new_decision if ov else (c.score_json or {}).get("decision", "review")
    return out


def _ranking_payload(job_id: str, db: Session):
    cands = db.query(Candidate).filter(Candidate.job_id == job_id).all()
    scored = [c for c in cands if c.status == "done"]
    # One batched query for latest overrides (was N+1).
    latest: dict[str, Override] = {}
    if scored:
        for ov in db.query(Override).filter(
                Override.candidate_id.in_([c.id for c in scored])).order_by(Override.id).all():
            latest[ov.candidate_id] = ov
    items: list[dict] = []
    for c in scored:
        s = c.score_json or {}
        ov = latest.get(c.id)
        items.append({"candidate_id": c.id, "filename": c.filename, "total": s.get("total", 0),
                      "band": s.get("band"), "flags": s.get("flags", []),
                      "system_decision": s.get("decision"),
                      "final_decision": ov.new_decision if ov else s.get("decision"),
                      "overridden": bool(ov), "must_coverage": s.get("must_coverage", 0),
                      "preferred_coverage": s.get("preferred_coverage", 0),
                      "mean_confidence": s.get("mean_confidence", 0)})
    ranked = assign_ranks(items)
    # re-sort: overridden promoted? spec: list re-sorts; keep score order, overridden badge shown
    return {"ranking": ranked,
            "pending": [{"id": c.id, "status": c.status} for c in cands if c.status != "done"]}


@router.get("/jobs/{job_id}/ranking")
def ranking(job_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _ranking_payload(job_id, db)
    cands = db.query(Candidate).filter(Candidate.job_id == job_id).all()
    scored = [c for c in cands if c.status == "done"]
    # One batched query for latest overrides (was N+1).
    latest: dict[str, Override] = {}
    if scored:
        for ov in db.query(Override).filter(
                Override.candidate_id.in_([c.id for c in scored])).order_by(Override.id).all():
            latest[ov.candidate_id] = ov
    items: list[dict] = []
    for c in scored:
        s = c.score_json or {}
        ov = latest.get(c.id)
        items.append({"candidate_id": c.id, "filename": c.filename, "total": s.get("total", 0),
                      "band": s.get("band"), "flags": s.get("flags", []),
                      "system_decision": s.get("decision"),
                      "final_decision": ov.new_decision if ov else s.get("decision"),
                      "overridden": bool(ov), "must_coverage": s.get("must_coverage", 0),
                      "preferred_coverage": s.get("preferred_coverage", 0),
                      "mean_confidence": s.get("mean_confidence", 0)})
    ranked = assign_ranks(items)
    # re-sort: overridden promoted? spec: list re-sorts; keep score order, overridden badge shown
    return {"ranking": ranked,
            "pending": [{"id": c.id, "status": c.status} for c in cands if c.status != "done"]}


def _csv_safe(v) -> str:
    # Block spreadsheet formula injection from user-controlled filenames.
    s = "" if v is None else str(v)
    if s[:1] in ("=", "+", "-", "@"):
        return "'" + s
    return s


@router.get("/jobs/{job_id}/export.csv")
def export_csv(job_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    data = _ranking_payload(job_id, db)["ranking"]
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["rank", "candidate_id", "filename", "total", "band", "system_decision", "final_decision", "flags"])
    for r in data:
        w.writerow([r.get("rank"), r.get("candidate_id"), _csv_safe(r.get("filename")), r.get("total"),
                    r.get("band"), r.get("system_decision"), r.get("final_decision"), ";".join(r.get("flags", []))])
    return PlainTextResponse(buf.getvalue(), media_type="text/csv")


@router.get("/jobs/{job_id}/duplicates")
def duplicates(job_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from ..services.duplicates import find_duplicates

    cands = db.query(Candidate).filter(Candidate.job_id == job_id).all()
    try:
        return {"pairs": find_duplicates([{"id": c.id, "text": c.masked_text or c.raw_text,
                                           "email_hash": (c.identity_json or {}).get("emails", [])} for c in cands])}
    except Exception:
        # Embedding model load can fail offline; empty pairs beats a 500 for a
        # secondary signal, but the failure is visible in server logs.
        logger.exception("duplicate detection failed for job %s", job_id)
        return {"pairs": []}
