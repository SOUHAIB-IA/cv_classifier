#!/usr/bin/env python3
"""Portal: paste a job description, get the best CV to send and the edits
needed to clear an ATS first scan.

  python portal.py           -> http://127.0.0.1:8770

Matching is two-stage to keep token use sane:
  1. the compact index (one line per CV) -> model shortlists 5
  2. the full text of those 5 -> model picks one and writes the gap analysis
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

import cvrouter as cr

HERE = Path(__file__).resolve().parent
cfg = cr.load_config()
log = cr.setup_logging(cfg, "portal")
templates = Jinja2Templates(directory=str(HERE / "templates"))
app = FastAPI(title="CV Router")

SHORTLIST_SYSTEM = """You match a job ad against a library of CVs belonging to one
person. Each library line is: [path] stage=... role=... lang=... title=... skills=... summary.

Pick the 5 lines whose CV is most likely the best to send for this job.

Weigh, in order: (1) career stage — a permanent job (CDI/full-time) needs a
graduate CV, an internship (stage/PFE) needs the student one; (2) how much of the
ad's required stack the CV actually evidences; (3) how close the CV's target role
is to the advertised role.

Return ONLY JSON: {"shortlist": ["path1", ...], "stage_wanted": "...",
"reason": "one sentence"}"""

ANALYSE_SYSTEM = """You are an expert technical recruiter and ATS specialist
helping one candidate choose and adapt a CV.

You get a job ad and the FULL text of several of the candidate's CVs. Judge each
on its whole content — profile, skills, experience, projects — never on its title
alone, which is often stale.

Return ONLY a JSON object:
{
 "best": {"path": "...", "why": "2-3 sentences citing concrete evidence from that CV"},
 "runner_up": {"path": "...", "why": "1-2 sentences"},
 "ats_score": 0-100,
 "score_reason": "one sentence on what the score reflects",
 "matched_keywords":  ["terms the ad requires that this CV already contains"],
 "missing_keywords":  ["terms the ad requires that are absent or too weak"],
 "key_changes": [
   {"section": "e.g. Titre / Profil / Compétences / Expérience",
    "current": "what the CV says now, quoted or '(absent)'",
    "suggested": "the exact replacement text to paste in",
    "why": "which line of the ad this satisfies",
    "priority": "high|medium|low"}
 ],
 "red_flags": ["things that could get it filtered out or hurt in review"],
 "cover_letter_hook": "2 sentences the candidate can open a cover letter with"
}

Rules for key_changes: give 4-8 of them, each concretely actionable with text the
candidate can copy. Never invent experience the CVs do not support — rephrase,
surface, and reorder what is already there. Write them in the CV's own language."""


def _index() -> cr.Index:
    return cr.Index(cfg)


def analyse(job_text: str) -> dict:
    idx = _index()
    if not idx.records:
        raise cr.AIError("Index is empty — run: python indexer.py")

    lines = [r.compact() for r in idx.records.values()]
    short = cr.ask_json(
        cfg, SHORTLIST_SYSTEM,
        f"=== JOB AD ===\n{job_text[:9000]}\n\n=== CV LIBRARY ===\n"
        + "\n".join(lines),
        max_tokens=1200,
    )
    picks = [p for p in short.get("shortlist", []) if p in idx.records][:5]
    if not picks:
        picks = list(idx.records)[:5]

    blocks = []
    for rel in picks:
        text = cr.pdf_text(cfg.cv_root / rel)
        blocks.append(f"=== CV [{rel}] ===\n{text[:9000]}")

    result = cr.ask_json(
        cfg, ANALYSE_SYSTEM,
        f"=== JOB AD ===\n{job_text[:9000]}\n\n" + "\n\n".join(blocks),
        max_tokens=6000,
    )
    result["_shortlist"] = picks
    result["_stage_wanted"] = short.get("stage_wanted", "")
    result["_shortlist_reason"] = short.get("reason", "")
    return result


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
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/cvs")
def api_cvs():
    idx = _index()
    return JSONResponse({"count": len(idx.records),
                         "cvs": [r.compact() for r in idx.records.values()]})


if __name__ == "__main__":
    import uvicorn
    if not cfg.api_key:
        print(f"WARNING: no API key. Set $ANTHROPIC_API_KEY or fill {cfg.key_file}",
              file=sys.stderr)
    uvicorn.run(app, host=cfg.host, port=cfg.port)
