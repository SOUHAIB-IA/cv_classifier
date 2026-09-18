#!/usr/bin/env python3
"""Portal: paste a job description, get the best CV to send and the edits
needed to clear an ATS first scan.

  python portal.py           -> http://127.0.0.1:8770

The matching itself lives in matcher.py, shared with match.py and the job
pipeline, so the UI and the headless callers can never drift apart.
"""
from __future__ import annotations

import json
import sys
import threading
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

import cvrouter as cr
import matcher

HERE = Path(__file__).resolve().parent
cfg = cr.load_config()
log = cr.setup_logging(cfg, "portal")
templates = Jinja2Templates(directory=str(HERE / "templates"))
app = FastAPI(title="CV Router")

_index_cache: dict = {"mtime": None, "idx": None}
_index_lock = threading.Lock()


def _index() -> cr.Index:
    """The index, re-read only when the file on disk actually changed."""
    try:
        mtime = cfg.index_file.stat().st_mtime_ns
    except OSError:
        return cr.Index(cfg)
    with _index_lock:
        if _index_cache["mtime"] != mtime or _index_cache["idx"] is None:
            _index_cache["idx"] = cr.Index(cfg)
            _index_cache["mtime"] = mtime
        return _index_cache["idx"]


def analyse(job_text: str) -> dict:
    # An empty ad would still cost two model calls for a meaningless answer.
    if len((job_text or "").strip()) < 40:
        raise ValueError("job description is empty or too short to match")
    return matcher.match_job(cfg, job_text, idx=_index())


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    idx = _index()
    return templates.TemplateResponse(
        request, "portal.html",
        {"result": None, "job": "", "n_cvs": len(idx.records),
         "cv_root": str(cfg.cv_root), "error": None},
    )


@app.post("/", response_class=HTMLResponse)
def match(request: Request, job: str = Form(...)):
    idx = _index()
    ctx = {"job": job, "n_cvs": len(idx.records),
           "cv_root": str(cfg.cv_root), "result": None, "error": None}
    try:
        ctx["result"] = analyse(job)
    except Exception as e:
        log.exception("match failed")
        ctx["error"] = str(e)
    return templates.TemplateResponse(request, "portal.html", ctx)


@app.post("/api/match")
def api_match(payload: dict):
    """POST {"job": "...'} -> the same analysis as JSON, for scripting."""
    try:
        return JSONResponse(analyse(payload.get("job", "")))
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/v1/match")
def api_v1_match(payload: dict):
    """Headless contract for the job pipeline.

    POST {"jd": "...", "title": "", "company": "", "location": ""}
    ->   {"best_variant", "suggested_edits", "fit_score", "ats_score", ...}
    """
    jd = payload.get("jd") or payload.get("job") or ""
    if len(jd.strip()) < 40:
        return JSONResponse({"error": "job description is empty or too short to match"},
                            status_code=400)
    try:
        return JSONResponse(matcher.match_job(
            cfg, jd, title=payload.get("title", ""),
            company=payload.get("company", ""),
            location=payload.get("location", ""), idx=_index()))
    except cr.AIError as e:
        return JSONResponse({"error": str(e)}, status_code=503)
    except Exception as e:
        log.exception("v1 match failed")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/cvs")
def api_cvs():
    idx = _index()
    return JSONResponse({"count": len(idx.records),
                         "cvs": [r.compact() for r in idx.records.values()]})


if __name__ == "__main__":
    import uvicorn
    if cfg.backend == "api" and not cfg.api_key:
        print(f"WARNING: backend is \"api\" but no key. Set $ANTHROPIC_API_KEY "
              f"or fill {cfg.key_file}", file=sys.stderr)
    uvicorn.run(app, host=cfg.host, port=cfg.port)
