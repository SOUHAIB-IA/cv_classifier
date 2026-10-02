"""The studio's page in the existing interface.

Its own APIRouter, so portal.py gains one include_router line and webui.py is not
touched at all. Follows the app's convention: anything that writes requires the
X-CV-Router header, which a cross-origin page cannot send without a CORS
preflight this app never grants.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from . import config as ccfg
from . import render as R
from .checker import check_doc, check_pdf
from .cli import ROLE_FILES, LibraryMissing, _library_doc, _slug
from .convert import convert
from .customize import emphasise, match, pick_lang, pick_role
from .rules import load_rules

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
# Two search paths: the module's own page first, then the repo's, because the
# page includes the shared _nav.html and that lives with the rest of the app.
templates = Jinja2Templates(directory=[str(HERE / "templates"),
                                       str(ROOT / "templates")])
router = APIRouter(prefix="/canada")


def _guard(x_cv_router: str | None) -> None:
    if x_cv_router != "1":
        raise HTTPException(403, "missing X-CV-Router header")


@router.get("")
@router.get("/")
def page(request: Request):
    return templates.TemplateResponse(request, "canada.html", {"here": "canada"})


@router.get("/api/state")
def state():
    """What the page needs to draw itself: the rules in force and the config."""
    rules, cfg = load_rules(), ccfg.load()
    return {
        "roles": {k: v.replace("_", " ") for k, v in ROLE_FILES.items()},
        "paper": rules.paper,
        "pages": rules.d["document"]["pages"],
        "location_mode": cfg.location_mode,
        "auth_mode": cfg.auth_mode,
        "credential_mode": cfg.credential_mode,
        "emit_docx": cfg.emit_docx,
        "output_dir": str(cfg.output_dir),
        "equivalence_set": bool(cfg.equivalence_text),
    }


@router.post("/api/check")
def api_check(payload: dict, x_cv_router: str | None = Header(default=None)):
    """Lint a role CV from the library, or a document pasted into the page."""
    _guard(x_cv_router)
    rules = load_rules()
    lang = payload.get("lang") or "en"
    if payload.get("role"):
        try:
            doc, pdf = _library_doc(payload["role"], lang)
        except LibraryMissing as e:
            raise HTTPException(404, str(e)) from e
        rep = check_doc(doc, rules, lang).merge(check_pdf(pdf, rules, lang))
    elif payload.get("doc"):
        rep = check_doc(payload["doc"], rules, lang)
    else:
        raise HTTPException(400, "give a role or a document")
    return rep.to_dict()


@router.post("/api/tailor")
def api_tailor(payload: dict, x_cv_router: str | None = Header(default=None)):
    """Convert, score against a posting, reorder, render. The CLI's work, as JSON."""
    _guard(x_cv_router)
    jd = (payload.get("jd") or "").strip()
    if len(jd) < 80:
        raise HTTPException(400, "that posting is too short to read anything from")

    rules, cfg = load_rules(), ccfg.load()
    lang, why_lang = pick_lang(jd, payload.get("city") or "",
                               payload.get("lang") or None)
    role, why_role = ((payload["role"], "you chose it") if payload.get("role")
                      else pick_role(jd))

    try:
        doc, src = _library_doc(role, lang)
    except LibraryMissing as e:
        raise HTTPException(404, str(e)) from e
    canadian, log = convert(doc, rules, cfg, lang)
    m = match(canadian, jd, rules, lang)
    tailored = emphasise(canadian, m, log,
                         bullets=not payload.get("no_bullets"))

    stem = (f"{ROLE_FILES[role]}_{lang}_{_slug(payload.get('company', ''))}_"
            f"{date.today().isoformat()}")
    out_dir = cfg.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{stem}.cv.json").write_text(
        json.dumps(tailored, ensure_ascii=False, indent=1), encoding="utf-8")
    (out_dir / f"{stem}.changelog.txt").write_text(
        m.text() + "\n\n" + log.text() + "\n", encoding="utf-8")

    note, pages = "", 0
    if not payload.get("no_render"):
        chrome = R.find_chrome(cfg.chrome_bin)
        pages, _step, note = R.render_pdf(
            tailored, lang, out_dir / f"{stem}.pdf", chrome,
            prefer_pages=int(rules.d["document"]["pages"]["prefer"]),
            max_pages=rules.max_pages)
        if cfg.emit_docx:
            R.render_docx(tailored, lang, out_dir / f"{stem}.docx")

    rep = check_doc(tailored, rules, lang)
    pdf = out_dir / f"{stem}.pdf"
    if pdf.is_file():
        rep = rep.merge(check_pdf(pdf, rules, lang))

    return {"stem": stem, "role": role, "why_role": why_role,
            "lang": lang, "why_lang": why_lang, "source": src.name,
            "pages": pages, "advice": note, "match": m.to_dict(),
            "report": rep.to_dict(), "changelog": log.to_dict(),
            "files": [f.name for f in sorted(out_dir.glob(f"{stem}.*"))]}


@router.get("/api/file/{name}")
def api_file(name: str):
    """Serve one file out of the studio's output folder, and only from there."""
    cfg = ccfg.load()
    p = (cfg.output_dir / name).resolve()
    # A name like ../../etc/passwd must not escape the output folder.
    if not str(p).startswith(str(cfg.output_dir.resolve()) + "/") \
            or not p.is_file():
        raise HTTPException(404, "no such file in the studio's output")
    return FileResponse(p, filename=p.name)


@router.get("/api/output")
def api_output():
    cfg = ccfg.load()
    if not cfg.output_dir.is_dir():
        return JSONResponse({"files": []})
    rows = []
    for p in sorted(cfg.output_dir.glob("*"), key=lambda x: -x.stat().st_mtime):
        if p.is_file():
            rows.append({"name": p.name, "size": p.stat().st_size,
                         "mtime": int(p.stat().st_mtime)})
    return {"files": rows[:200], "dir": str(cfg.output_dir)}
