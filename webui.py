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
import re
import subprocess
import sys
import threading
from datetime import date, timedelta
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.templating import Jinja2Templates

import cvrouter as cr
from pipeline import config as pc
from pipeline import fetch as F
from pipeline import orchestrate as O
from pipeline import tailor as T
from pipeline import submit as SUB
from pipeline import autoapply as AA
from pipeline import sources as SRC
from pipeline import tracker as TR
from pipeline.db import DB, STATUSES
import settings as ST

HERE = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(HERE / "templates"))
router = APIRouter()
RUN_LOG = HERE / "data" / "last_run.log"
_run: dict = {"proc": None}
# One pre-fill at a time, per job: the browser window is the shared resource.
_prefill: dict = {}
_auto: dict = {}
_test: dict = {}


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
    return templates.TemplateResponse(request, "dashboard.html", {"here": "pipeline"})


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
        "autoapply": {"enabled": pcfg.auto_apply, "rehearse": pcfg.auto_rehearse,
                      "sent_today": AA.sent_today(db),
                      "max_per_day": pcfg.auto_max_per_day},
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


# -------------------------------------------------------------------- data --
# One view over jobs, their evaluation and their application. Five thousand
# postings had nowhere to be looked at: the dashboard shows queues, which is
# what is happening now, not what happened.
SORTS = {"first_seen": "j.first_seen", "posted": "j.posted_date",
         "company": "j.company", "title": "j.title", "fit": "a.fit_score",
         "ats": "m.ats_score", "prefilter": "j.prefilter_score",
         "updated": "a.updated_at"}
DATA_COLS = ("j.id AS job_id, j.company, j.title, j.location, j.source, j.board, "
             "j.stage, j.posted_date, j.first_seen, j.apply_url, j.jd_url, "
             "j.prefilter_score, j.language, "
             "a.status, a.decision, a.fit_score, a.date, a.cv_filename, a.notes, "
             "m.ats_score, m.recommended_variant")


def _data_where(p: dict) -> tuple[str, list]:
    where, args = ["1=1"], []
    if q := (p.get("q") or "").strip():
        where.append("(j.company LIKE ? OR j.title LIKE ? OR j.location LIKE ?)")
        args += [f"%{q}%"] * 3
    for field, col in (("stage", "j.stage"), ("source", "j.source"),
                       ("status", "a.status"), ("decision", "a.decision")):
        v = p.get(field)
        if v:
            where.append(f"{col} = ?")
            args.append(v)
    if p.get("fit_min") not in (None, ""):
        where.append("a.fit_score >= ?")
        args.append(int(p["fit_min"]))
    if p.get("has_app"):
        where.append("a.job_id IS NOT NULL")
    return " AND ".join(where), args


def _data_rows(db: DB, p: dict, limit: int, offset: int) -> list[dict]:
    where, args = _data_where(p)
    col = SORTS.get(p.get("sort") or "first_seen", "j.first_seen")
    direction = "ASC" if (p.get("dir") or "desc").lower() == "asc" else "DESC"
    return [dict(r) for r in db.q(
        f"SELECT {DATA_COLS} FROM jobs j "
        f"LEFT JOIN applications a ON a.job_id = j.id "
        f"LEFT JOIN matches m ON m.job_id = j.id "
        f"WHERE {where} ORDER BY {col} IS NULL, {col} {direction}, j.rowid DESC "
        f"LIMIT {int(limit)} OFFSET {int(offset)}", *args)]


@router.get("/data", response_class=HTMLResponse)
def data_page(request: Request):
    return templates.TemplateResponse(request, "data.html", {"here": "data"})


@router.get("/api/data")
def data(q: str = "", stage: str = "", source: str = "", status: str = "",
         decision: str = "", fit_min: str = "", has_app: str = "",
         sort: str = "first_seen", dir: str = "desc",
         page: int = 1, per: int = 50):
    pcfg, cfg, db = _ctx()
    p = {"q": q, "stage": stage, "source": source, "status": status,
         "decision": decision, "fit_min": fit_min or None, "has_app": has_app,
         "sort": sort, "dir": dir}
    where, args = _data_where(p)
    total = db.one(f"SELECT COUNT(*) FROM jobs j "
                   f"LEFT JOIN applications a ON a.job_id=j.id "
                   f"LEFT JOIN matches m ON m.job_id=j.id WHERE {where}", *args)[0]
    per = max(10, min(int(per), 200))
    page = max(1, int(page))
    return JSONResponse({
        "rows": _data_rows(db, p, per, (page - 1) * per),
        "total": total, "page": page, "per": per,
        "pages": max(1, -(-total // per)),
        "facets": {
            "stage": [dict(zip(("v", "n"), r)) for r in db.q(
                "SELECT stage, COUNT(*) FROM jobs GROUP BY stage ORDER BY 2 DESC")],
            "source": [dict(zip(("v", "n"), r)) for r in db.q(
                "SELECT source, COUNT(*) FROM jobs GROUP BY source ORDER BY 2 DESC")],
            "status": [dict(zip(("v", "n"), r)) for r in db.q(
                "SELECT status, COUNT(*) FROM applications GROUP BY status ORDER BY 2 DESC")],
        },
        "sorts": sorted(SORTS),
    })


@router.get("/api/data.csv")
def data_csv(q: str = "", stage: str = "", source: str = "", status: str = "",
             decision: str = "", fit_min: str = "", has_app: str = "",
             sort: str = "first_seen", dir: str = "desc"):
    """The rows you are looking at, as a file, so the data is yours to keep."""
    import csv
    import io
    pcfg, cfg, db = _ctx()
    rows = _data_rows(db, {"q": q, "stage": stage, "source": source,
                           "status": status, "decision": decision,
                           "fit_min": fit_min or None, "has_app": has_app,
                           "sort": sort, "dir": dir}, 20_000, 0)
    buf = io.StringIO()
    cols = ["company", "title", "location", "source", "board", "stage", "status",
            "decision", "fit_score", "ats_score", "prefilter_score", "posted_date",
            "first_seen", "date", "cv_filename", "apply_url", "job_id"]
    w = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
    w.writeheader()
    w.writerows(rows)
    return Response(buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition":
                             'attachment; filename="cv-router-offres.csv"'})


@router.get("/api/search")
def search(q: str = "", limit: int = 12):
    """What the Ctrl+K box needs: a few good matches, fast."""
    q = q.strip()
    if len(q) < 2:
        return {"rows": []}
    pcfg, cfg, db = _ctx()
    like = f"%{q}%"
    return {"rows": [dict(r) for r in db.q(
        "SELECT j.id AS job_id, j.company, j.title, j.location, j.stage, "
        "a.status, a.fit_score FROM jobs j "
        "LEFT JOIN applications a ON a.job_id = j.id "
        "WHERE j.company LIKE ? OR j.title LIKE ? "
        # something you acted on beats a posting nobody ever looked at
        "ORDER BY a.job_id IS NULL, a.fit_score DESC, j.first_seen DESC LIMIT ?",
        like, like, max(1, min(int(limit), 30)))]}


@router.get("/api/job/{job_id:path}/neighbours")
def job_neighbours(job_id: str):
    """The application before and after this one, so a review is a run, not a
    series of returns to the dashboard."""
    pcfg, cfg, db = _ctx()
    rows = [r["job_id"] for r in db.q(
        "SELECT a.job_id FROM applications a WHERE a.status IN "
        "('draft','staged','review','pending') "
        "ORDER BY a.fit_score DESC, a.updated_at DESC")]
    if job_id not in rows:
        return {"prev": None, "next": None, "i": None, "n": len(rows)}
    i = rows.index(job_id)
    return {"prev": rows[i - 1] if i else None,
            "next": rows[i + 1] if i + 1 < len(rows) else None,
            "i": i + 1, "n": len(rows)}


# ---------------------------------------------------------------- settings --
@router.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request):
    return templates.TemplateResponse(request, "settings.html", {"here": "settings"})


@router.get("/api/settings")
def settings_read():
    pcfg, cfg, db = _ctx()
    return JSONResponse(ST.schema(cfg, pcfg))


@router.post("/api/settings")
def settings_write(payload: dict, x_cv_router: str | None = Header(default=None)):
    """Write the changed settings back into the TOML files.

    _ctx() reloads both files on every request, so a saved setting is live at
    once for this app. The watcher is a separate long-running process and has
    to be restarted to see them: /api/settings/restart does that.
    """
    _guard(x_cv_router)
    try:
        changed = ST.write(payload.get("changes") or {})
    except ST.SettingsError as e:
        raise HTTPException(400, str(e))
    pcfg, cfg, db = _ctx()
    db.event("settings", None, changed=changed)
    return {"changed": changed, "values": ST.current()}


@router.post("/api/settings/key")
def settings_key(payload: dict, x_cv_router: str | None = Header(default=None)):
    """Store the API key in its own file, owner-readable only. Never read back."""
    _guard(x_cv_router)
    pcfg, cfg, db = _ctx()
    try:
        return ST.save_key(cfg, payload.get("key", ""), payload.get("provider"))
    except ST.SettingsError as e:
        raise HTTPException(400, str(e))


@router.post("/api/settings/board")
def settings_board(payload: dict, x_cv_router: str | None = Header(default=None)):
    """Which platform hosts this company, and how many postings it has now.

    Typing a company slug wrong otherwise costs a 45-minute cycle to discover.
    """
    _guard(x_cv_router)
    slug = (payload.get("board") or "").strip().split("=")[0].lower()
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,60}", slug):
        raise HTTPException(400, "un identifiant d'entreprise, pas une adresse : "
                                 "des lettres, des chiffres et des tirets")
    found = SRC.probe(slug, timeout=15)
    hits = {k: v for k, v in found.items() if isinstance(v, int) and v > 0}
    return {"board": slug, "found": found, "hits": hits}


@router.get("/api/settings/test")
def settings_test_state():
    return _test.get("state") or {"state": "idle"}


@router.post("/api/settings/test")
def settings_test(x_cv_router: str | None = Header(default=None)):
    """One real call on the configured backend. A claude_cli call takes a
    while, so it runs in a thread and the page polls, as elsewhere here."""
    _guard(x_cv_router)
    if (_test.get("state") or {}).get("state") == "running":
        return _test["state"]
    _test["state"] = {"state": "running"}

    def work():
        pcfg, cfg, db = _ctx()
        try:
            _test["state"] = {"state": "done", **ST.test_backend(cfg)}
        except Exception as e:
            _test["state"] = {"state": "done", "ok": False, "error": str(e)[:300]}

    threading.Thread(target=work, daemon=True).start()
    return _test["state"]


@router.post("/api/settings/restart")
def settings_restart(x_cv_router: str | None = Header(default=None)):
    """Restart the background watcher so it picks the new settings up.

    Deliberately not the portal: that is the process answering this request.
    It rereads both files per request and needs no restart.
    """
    _guard(x_cv_router)
    r = subprocess.run(["systemctl", "--user", "restart", "cv-router-watcher.service"],
                       capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        raise HTTPException(400, (r.stderr or r.stdout).strip()[:200] or "échec")
    return {"ok": True}


@router.get("/api/pipeline/charts")
def charts():
    """Aggregates for the graphs. Read-only, cheap, no model call."""
    pcfg, cfg, db = _ctx()
    days = [(date.today() - timedelta(days=i)).isoformat() for i in range(29, -1, -1)]

    def per_day(sql: str, *a) -> list[int]:
        d = {r[0]: r[1] for r in db.q(sql, *a)}
        return [d.get(x, 0) for x in days]

    hist = [0] * 10
    for r in db.q("SELECT fit_score FROM applications WHERE fit_score IS NOT NULL"):
        hist[min(int(r[0]) // 10, 9)] += 1

    sent = TR.SENT
    marks = ",".join("?" * len(sent))
    applied = db.one(f"SELECT COUNT(*) FROM applications WHERE status IN ({marks})",
                     *sent)[0]
    answered = db.one("SELECT COUNT(*) FROM applications WHERE status IN "
                      "('rejected','interview','offer')")[0]

    return JSONResponse({
        "days": days,
        "series": {
            "sourced": per_day("SELECT date(first_seen,'localtime') d, COUNT(*) "
                               "FROM jobs GROUP BY d"),
            "evaluated": per_day("SELECT date(created_at,'localtime') d, COUNT(*) "
                                 "FROM matches GROUP BY d"),
            "applied": per_day(f"SELECT date, COUNT(*) FROM applications "
                               f"WHERE status IN ({marks}) GROUP BY date", *sent),
        },
        "fit_hist": hist,
        "thresholds": {"auto": pcfg.threshold_auto, "review": pcfg.threshold_review},
        "status": [{"status": r[0] or "?", "n": r[1]} for r in db.q(
            "SELECT status, COUNT(*) FROM applications GROUP BY status "
            "ORDER BY COUNT(*) DESC")],
        "sources": [{"name": r[0], "n": r[1]} for r in db.q(
            "SELECT source, COUNT(*) FROM jobs GROUP BY source ORDER BY 2 DESC")],
        "buckets": TR.weekly(db),
        "rates": {"applied": applied, "answered": answered,
                  "rate": round(answered / applied, 3) if applied else None},
    })


@router.get("/api/pipeline/autoapply")
def autoapply_state():
    """What could be sent without you, and what is holding each one back."""
    pcfg, cfg, db = _ctx()
    return JSONResponse({
        "enabled": pcfg.auto_apply,
        "rehearse": pcfg.auto_rehearse,
        "min_fit": pcfg.auto_min_fit,
        "min_ats": pcfg.auto_min_ats,
        "max_per_day": pcfg.auto_max_per_day,
        "sent_today": AA.sent_today(db),
        "answers": len(pc.load_profile().get("answers", [])),
        "rows": AA.eligible(pcfg, db),
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
    return templates.TemplateResponse(request, "job.html", {"job_id": job_id, "here": "job"})


# Declared before the catch-all below: a {path} converter swallows slashes, so
# "/api/job/<id>/prefill" would otherwise be read as a job id ending in
# "/prefill" and answered with 404.
@router.get("/api/job/{job_id:path}/prefill")
def job_prefill_state(job_id: str):
    return _prefill.get(job_id) or {"state": "idle"}


@router.get("/api/job/{job_id:path}/autoapply")
def job_autoapply_state(job_id: str):
    return _auto.get(job_id) or {"state": "idle"}


@router.post("/api/job/{job_id:path}/autoapply")
def job_autoapply(job_id: str, payload: dict | None = None,
                  x_cv_router: str | None = Header(default=None)):
    """Fill the form and send it, but only if the gate in autoapply.py agrees.

    The browser window is visible the whole time. If anything is unanswered it
    stops and the window stays open for you.
    """
    _guard(x_cv_router)
    pcfg, cfg, db = _ctx()
    rehearse = bool((payload or {}).get("rehearse"))
    job = db.one("SELECT * FROM jobs WHERE id=?", job_id)
    app = db.one("SELECT * FROM applications WHERE job_id=?", job_id)
    m = db.one("SELECT * FROM matches WHERE job_id=?", job_id)
    blockers = AA.pre_gate(pcfg, db, job, app, m)
    if blockers:
        raise HTTPException(400, "; ".join(blockers))
    st = _auto.get(job_id)
    if st and st.get("state") in ("running", "filled"):
        return st
    _auto[job_id] = {"state": "running", "rehearse": rehearse}

    def work():
        try:
            AA.run(pcfg, DB(pcfg.db), job_id, rehearse=rehearse,
                   log=lambda *a: None,
                   on_state=lambda res: _auto.__setitem__(job_id, res))
        except Exception as e:
            _auto[job_id] = {"state": "error", "note": str(e)[:300]}

    threading.Thread(target=work, daemon=True).start()
    return {"state": "running", "rehearse": rehearse}


@router.get("/api/job/{job_id:path}")
def job_data(job_id: str):
    pcfg, cfg, db = _ctx()
    job = db.one("SELECT * FROM jobs WHERE id=?", job_id)
    if not job:
        raise HTTPException(404, "unknown job")
    m = db.one("SELECT * FROM matches WHERE job_id=?", job_id)
    app = db.one("SELECT * FROM applications WHERE job_id=?", job_id)
    out = {"job": dict(job), "match": None, "app": dict(app) if app else None, "cv": None,
           "tier": SUB.tier(job["apply_url"] or "", pcfg.submit_hosts),
           "thresholds": {"auto": pcfg.threshold_auto, "review": pcfg.threshold_review},
           "events": [dict(r) for r in db.q(
               "SELECT ts, kind, detail FROM events WHERE job_id=? ORDER BY rowid", job_id)]}
    if m:
        out["match"] = {**dict(m), "raw": json.loads(m["raw"] or "{}"),
                        "suggested_edits": json.loads(m["suggested_edits"] or "[]")}
    out["autoapply"] = {
        "enabled": pcfg.auto_apply,
        "rehearse": pcfg.auto_rehearse,
        "min_fit": pcfg.auto_min_fit, "min_ats": pcfg.auto_min_ats,
        "sent_today": AA.sent_today(db), "max_per_day": pcfg.auto_max_per_day,
        "blockers": AA.pre_gate(pcfg, db, job, app, m),
    }
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


@router.post("/api/job/{job_id:path}/prefill")
def job_prefill(job_id: str, x_cv_router: str | None = Header(default=None)):
    """Open the employer's form in a real window and fill your details and CV.

    It stops there: the window stays open for you to read it, answer what is
    left and click submit. Nothing here ever clicks.
    """
    _guard(x_cv_router)
    pcfg, cfg, db = _ctx()
    job = db.one("SELECT * FROM jobs WHERE id=?", job_id)
    app = db.one("SELECT * FROM applications WHERE job_id=?", job_id)
    if not job or not app:
        raise HTTPException(404, "unknown job")
    if SUB.tier(job["apply_url"], pcfg.submit_hosts) == 2:
        raise HTTPException(400, "this platform is not automated: apply by hand")
    try:
        cv = SUB.cv_file(pcfg, app)
    except FileNotFoundError as e:
        raise HTTPException(400, str(e))
    st = _prefill.get(job_id)
    if st and st.get("state") == "running":
        return {"state": "running"}

    ident = SUB._identity(pc.load_profile(), (app["account"] or job["language"] or "en").lower())
    _prefill[job_id] = {"state": "running", "report": None, "error": None}

    def work():
        def filled(rep):
            _prefill[job_id] = {"state": "filled", "report": rep, "error": None}
            DB(pcfg.db).event("submit", job_id, stage="prefilled", filled=rep["filled"],
                              resume=rep["resume"], captcha=rep["captcha"],
                              required_left=len(rep["required_left"]))
        try:
            SUB.open_and_fill(pcfg, job["apply_url"], ident, cv, on_filled=filled)
            cur = _prefill.get(job_id) or {}
            _prefill[job_id] = {**cur, "state": "closed"}
        except Exception as e:
            _prefill[job_id] = {"state": "error", "report": None, "error": str(e)[:300]}

    threading.Thread(target=work, daemon=True).start()
    return {"state": "running", "profile_set": bool(ident)}


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
