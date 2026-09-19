"""Web interface for the job pipeline: see what is happening, read and edit
every tailored CV before it goes out.

  /pipeline            dashboard: funnel, queues, live event log, run controls
  /job/<id>            one job: the ad, cv-router's verdict, and the CV editor

Mounted by portal.py. Every route that changes something requires the header
X-CV-Router: 1. A browser will not send a custom header across origins without
a CORS preflight, which this app never grants — so a page on another site
cannot drive these actions on your localhost.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

import cvrouter as cr
from pipeline import config as pc
from pipeline import fetch as F
from pipeline import orchestrate as O
from pipeline import tailor as T
from pipeline import tracker as TR
from pipeline.db import DB, STATUSES

HERE = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(HERE / "templates"))
router = APIRouter()
RUN_LOG = HERE / "data" / "last_run.log"
_run: dict = {"proc": None}


def _ctx():
    pcfg, cfg = pc.load(), cr.load_config()
    return pcfg, cfg, DB(pcfg.db)


def _guard(x_cv_router: str | None):
    if x_cv_router != "1":
        raise HTTPException(403, "missing X-CV-Router header")


def _running() -> bool:
    p = _run["proc"]
    return p is not None and p.poll() is None


def _rows(db: DB, where: str, *args, limit: int = 50) -> list[dict]:
    return [dict(r) for r in db.q(
        "SELECT a.job_id, a.company, a.role, a.fit_score, a.status, a.decision, "
        "a.date, a.cv_variant, a.cv_filename, a.updated_at, m.ats_score, j.location "
        "FROM applications a LEFT JOIN matches m ON m.job_id=a.job_id "
        f"JOIN jobs j ON j.id=a.job_id WHERE {where} "
        f"ORDER BY a.fit_score DESC, a.updated_at DESC LIMIT {limit}", *args)]


# --------------------------------------------------------------- dashboard --
@router.get("/pipeline", response_class=HTMLResponse)
def dashboard(request: Request):
    return templates.TemplateResponse(request, "dashboard.html", {})


@router.get("/api/pipeline/state")
def state():
    pcfg, cfg, db = _ctx()
    events = []
    for r in db.q("SELECT ts, kind, job_id, detail FROM events "
                  "WHERE kind NOT IN ('prefilter') ORDER BY rowid DESC LIMIT 60"):
        e = dict(r)
        try:
            e["detail"] = json.loads(e["detail"] or "{}")
        except json.JSONDecodeError:
            pass
        events.append(e)
    ids = sorted({e["job_id"] for e in events if e["job_id"]})
    names = {}
    if ids:
        names = {r["id"]: f"{r['company']} · {r['title']}" for r in db.q(
            f"SELECT id, company, title FROM jobs WHERE id IN ({','.join('?' * len(ids))})",
            *ids)}
    for e in events:
        e["job"] = names.get(e["job_id"], "")

    log_tail = RUN_LOG.read_text()[-6000:] if RUN_LOG.is_file() else ""
    return JSONResponse({
        "funnel": TR.funnel(db),
        "budget": {"used": db.matches_today(), "total": pcfg.daily_match_budget},
        "thresholds": {"auto": pcfg.threshold_auto, "review": pcfg.threshold_review},
        "running": _running(),
        "lists": {
            "draft": _rows(db, "a.status='draft'"),
            "staged": _rows(db, "a.status='staged'"),
            "review": _rows(db, "a.status='review'"),
            "pending": _rows(db, "a.status='pending'"),
            "candidates": [dict(r) for r in db.q(
                "SELECT id AS job_id, company, title AS role, location, prefilter_score "
                "FROM jobs WHERE stage='candidate' ORDER BY prefilter_score DESC LIMIT 30")],
            "recent": _rows(db, "a.decision IN ('auto','review','skip') "
                                "AND a.fit_score IS NOT NULL", limit=30),
            "outcomes": _rows(db, "a.status IN ('applied','interview','rejected','offer')"),
        },
        "events": events,
        "boards": [dict(r) for r in db.q(
            "SELECT source, board, last_fetched, n_jobs, last_error FROM boards "
            "ORDER BY last_fetched DESC")],
        "log": log_tail,
    })


@router.post("/api/pipeline/run")
def run(payload: dict, x_cv_router: str | None = Header(default=None)):
    """Start one pipeline cycle in the background; follow it in the log."""
    _guard(x_cv_router)
    if _running():
        raise HTTPException(409, "a run is already in progress")
    args = [sys.executable, str(HERE / "run_pipeline.py")]
    if payload.get("mode") == "dry":
        args.append("--dry-run")
    if not payload.get("fetch", False):
        args.append("--no-fetch")
    if payload.get("max_matches") is not None:
        args += ["--max-matches", str(int(payload["max_matches"]))]
    RUN_LOG.parent.mkdir(parents=True, exist_ok=True)
    fh = open(RUN_LOG, "w")
    fh.write(f"$ {' '.join(Path(a).name if i < 2 else a for i, a in enumerate(args))}\n")
    fh.flush()
    _run["proc"] = subprocess.Popen(args, cwd=str(HERE), stdout=fh,
                                    stderr=subprocess.STDOUT,
                                    env={**os.environ, "PYTHONUNBUFFERED": "1"})
    return {"started": True, "pid": _run["proc"].pid}


@router.post("/api/jobs")
def add_job(payload: dict, x_cv_router: str | None = Header(default=None)):
    """Add a posting by hand — LinkedIn, Rekrute, a recruiter's email."""
    _guard(x_cv_router)
    jd = (payload.get("jd") or "").strip()
    if len(jd) < 40 or not payload.get("company") or not payload.get("title"):
        raise HTTPException(400, "company, title and a job description are required")
    pcfg, cfg, db = _ctx()
    jid = F.add_manual(db, jd, company=payload["company"], title=payload["title"],
                       url=payload.get("url", ""), location=payload.get("location", ""))
    return {"job_id": jid}


# --------------------------------------------------------------------- job --
@router.get("/job/{job_id:path}/cv.pdf")
def cv_pdf(job_id: str):
    pcfg, cfg, db = _ctx()
    try:
        pdf, _, _ = T.cv_paths(pcfg, db, job_id)
    except T.TailorError as e:
        raise HTTPException(404, str(e))
    return FileResponse(pdf, media_type="application/pdf",
                        headers={"Cache-Control": "no-store"})


@router.get("/job/{job_id:path}", response_class=HTMLResponse)
def job_page(request: Request, job_id: str):
    return templates.TemplateResponse(request, "job.html", {"job_id": job_id})


@router.get("/api/job/{job_id:path}")
def job_data(job_id: str):
    pcfg, cfg, db = _ctx()
    job = db.one("SELECT * FROM jobs WHERE id=?", job_id)
    if not job:
        raise HTTPException(404, "unknown job")
    m = db.one("SELECT * FROM matches WHERE job_id=?", job_id)
    app = db.one("SELECT * FROM applications WHERE job_id=?", job_id)
    out = {"job": dict(job), "match": None, "app": dict(app) if app else None, "cv": None,
           "thresholds": {"auto": pcfg.threshold_auto, "review": pcfg.threshold_review},
           "events": [dict(r) for r in db.q(
               "SELECT ts, kind, detail FROM events WHERE job_id=? ORDER BY rowid", job_id)]}
    if m:
        out["match"] = {**dict(m), "raw": json.loads(m["raw"] or "{}"),
                        "suggested_edits": json.loads(m["suggested_edits"] or "[]")}
    if app and app["cv_filename"]:
        try:
            cv = T.load_cv(pcfg, cfg, db, job_id)
            out["cv"] = {"doc": cv["doc"], "base": cv["base"], "meta": cv["meta"],
                         "pdf": cv["pdf"].name}
        except T.TailorError as e:
            out["cv_error"] = str(e)
    return JSONResponse(out)


@router.post("/api/job/{job_id:path}/evaluate")
def job_evaluate(job_id: str, x_cv_router: str | None = Header(default=None)):
    """Send this job through cv-router now (two model calls)."""
    _guard(x_cv_router)
    pcfg, cfg, db = _ctx()
    job = db.one("SELECT * FROM jobs WHERE id=?", job_id)
    if not job:
        raise HTTPException(404, "unknown job")
    try:
        decision, fit, variant = O.evaluate_job(db, pcfg, cfg, dict(job))
    except cr.AIError as e:
        raise HTTPException(503, str(e))
    return {"decision": decision, "fit": fit, "variant": variant}


@router.post("/api/job/{job_id:path}/tailor")
def job_tailor(job_id: str, x_cv_router: str | None = Header(default=None)):
    """Build the tailored CV draft now, whatever the routing decided."""
    _guard(x_cv_router)
    pcfg, cfg, db = _ctx()
    try:
        with db.tx():
            db.upsert_application(job_id, status="pending")
        out = T.tailor_job(db, pcfg, cfg, job_id, log=lambda *a: None)
    except (T.TailorError, cr.AIError, KeyError) as e:
        raise HTTPException(400, str(e))
    return {"pdf": out.name}


@router.post("/api/job/{job_id:path}/preview", response_class=HTMLResponse)
def job_preview(job_id: str, payload: dict):
    """Render a document to HTML exactly as the PDF will be. Read-only."""
    doc = payload.get("doc") or {}
    lang = payload.get("lang", "fr")
    pcfg = pc.load()
    return HTMLResponse(T.render_html(doc, lang, T.DENSITY[int(payload.get("density", 0))],
                                      T.photo_uri(pcfg, lang)))


@router.post("/api/job/{job_id:path}/cv")
def job_save_cv(job_id: str, payload: dict, x_cv_router: str | None = Header(default=None)):
    """Save your edits and regenerate the PDF."""
    _guard(x_cv_router)
    pcfg, cfg, db = _ctx()
    doc = payload.get("doc")
    if not isinstance(doc, dict) or not doc.get("name"):
        raise HTTPException(400, "document is missing or has no name")
    try:
        return T.save_cv(db, pcfg, cfg, job_id, doc)
    except T.TailorError as e:
        raise HTTPException(400, str(e))


@router.post("/api/job/{job_id:path}/status")
def job_status(job_id: str, payload: dict, x_cv_router: str | None = Header(default=None)):
    """approve | skip  (review queue)   validate  (draft -> ready to submit)
    or any tracker status (applied, interview, rejected, offer, withdrawn...)."""
    _guard(x_cv_router)
    pcfg, cfg, db = _ctx()
    action = payload.get("action", "")
    notes = payload.get("notes", "")
    try:
        if action == "approve":
            with db.tx():
                db.upsert_application(job_id, status="pending",
                                      notes=notes or "approved in review")
                db.event("review", job_id, approved=True)
        elif action == "skip":
            with db.tx():
                db.upsert_application(job_id, status="skipped",
                                      notes=notes or "skipped by you")
                db.event("review", job_id, approved=False)
        elif action == "validate":
            T.validate_cv(db, job_id)
        elif action in STATUSES:
            TR.set_status(db, job_id, action, notes)
        else:
            raise HTTPException(400, f"unknown action {action!r}")
    except (T.TailorError, KeyError, ValueError) as e:
        raise HTTPException(400, str(e))
    TR.export(db, pcfg.tracker_xlsx)
    return {"ok": True, "status": db.one(
        "SELECT status FROM applications WHERE job_id=?", job_id)["status"]}
