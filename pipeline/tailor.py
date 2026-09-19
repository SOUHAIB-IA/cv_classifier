#!/usr/bin/env python3
"""CV Auto-Tailoring Engine — apply cv-router's edits to the chosen base CV.

  python -m pipeline.tailor <job_id>        tailor one job's CV
  python -m pipeline.tailor --pending       tailor every job waiting for it

The base CVs are PDFs from a CV builder; there is no editable source behind
them. So each base CV is first extracted into a structured document, once, with
its text copied verbatim — and that extraction is checked against the PDF
before anything is built on it. Tailoring then only swaps text the edit list
quotes exactly: it never rewrites freely, so it cannot invent experience and
the layout stays under control. The result is rendered to PDF by headless
Chrome and read back with pdftotext, the way an ATS would, before it is used.

Output:  applications/<date>/<Owner>_<Variant>_<Lang>_<Company>_<Date>.pdf
         plus a .json beside it listing every edit applied or refused, and why.
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

import cvrouter as cr

from . import config as pc
from .db import DB
from .orchestrate import _variant_label

ROOT = Path(__file__).resolve().parent.parent

EXTRACT_SYSTEM = """You convert one CV into a structured JSON document.

The text will be edited mechanically by searching for exact quotes, so COPY
EVERY PIECE OF TEXT VERBATIM. Do not paraphrase, shorten, translate, correct,
reorder or merge anything. Do not add anything that is not in the CV. Keep the
CV's own language and its own section titles.

Return ONLY this JSON:
{
 "name": "full name",
 "headline": "the tagline under the name, or \\"\\"",
 "contact": {"email": "", "phone": "", "location": "",
             "links": [{"label": "LinkedIn", "url": "https://..."}]},
 "summary": "the profile / summary paragraph, verbatim, or \\"\\"",
 "sections": [
   {"title": "section title as written", "kind": "experience|projects|education|other",
    "items": [{"heading": "role or project or degree", "org": "company / school / stack",
               "dates": "as written", "location": "as written",
               "bullets": ["each bullet verbatim"]}]},
   {"title": "...", "kind": "skills",
    "groups": [{"label": "group label as written, or \\"\\"", "items": ["skill", "..."]}]},
   {"title": "...", "kind": "list", "lines": ["each line verbatim"]}
 ]
}

Every line of the CV must land somewhere. The profile paragraph goes in
"summary", not in a section. Use "list" for languages, certifications,
interests, awards. Sections stay in the CV's order."""

_ABSENT = {"", "(absent)", "absent", "(aucun)", "aucun", "n/a", "(none)", "none", "-"}


# --------------------------------------------------------------- text helpers --
def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "")
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    s = s.replace("–", "-").replace("—", "-").replace("•", " ")
    return re.sub(r"\s+", " ", s).strip().lower()


def _words(s: str) -> list[str]:
    return re.findall(r"[a-z0-9àâçéèêëîïôûùüÿñæœ+#]{2,}", _norm(s))


def doc_text(doc: dict) -> str:
    """Every piece of text the structured document holds."""
    out = [doc.get("name", ""), doc.get("headline", ""), doc.get("summary", "")]
    c = doc.get("contact") or {}
    out += [c.get("email", ""), c.get("phone", ""), c.get("location", "")]
    out += [f"{l.get('label', '')} {l.get('url', '')}" for l in c.get("links") or []]
    for sec in doc.get("sections") or []:
        out.append(sec.get("title", ""))
        for it in sec.get("items") or []:
            out += [it.get("heading", ""), it.get("org", ""), it.get("dates", ""),
                    it.get("location", "")] + list(it.get("bullets") or [])
        for g in sec.get("groups") or []:
            out += [g.get("label", "")] + list(g.get("items") or [])
        out += list(sec.get("lines") or [])
    return "\n".join(x for x in out if x)


def coverage(pdf_text: str, doc: dict) -> float:
    """Share of the PDF's words found in the structured document. A low value
    means the extraction dropped content, and nothing should be built on it."""
    src = _words(pdf_text)
    if not src:
        return 0.0
    have = set(_words(doc_text(doc)))
    return sum(1 for w in src if w in have) / len(src)


# ------------------------------------------------------------ 1. structure --
def structured(cfg: cr.Config, pcfg: pc.PipelineConfig, base_rel: str,
               ask=None) -> dict:
    """The structured version of a base CV — cached by content signature, so
    each variant costs one model call ever, and an edited PDF re-extracts."""
    ask = ask or cr.ask_json
    pdf = cfg.cv_root / base_rel
    text = cr.pdf_text_cached(cfg, pdf)
    sig = cr.content_sig(text)
    cache = pcfg.structured_dir / f"{sig}.json"
    if cache.is_file():
        return attach_links(json.loads(cache.read_text()), pdf)

    doc = ask(cfg, EXTRACT_SYSTEM, f"--- CV TEXT ---\n{text[:16000]}", max_tokens=8000)
    doc.setdefault("contact", {})
    doc.setdefault("sections", [])
    cov = coverage(text, doc)
    doc["_source"] = {"path": base_rel, "sig": sig, "coverage": round(cov, 3)}
    if cov < 0.85:
        raise TailorError(f"extraction kept only {cov:.0%} of the CV's words "
                          f"— refusing to build on it")
    pcfg.structured_dir.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(doc, ensure_ascii=False, indent=1))
    return attach_links(doc, pdf)


class TailorError(RuntimeError):
    pass


def pdf_links(pdf: Path) -> list[str]:
    """The web links a CV builder stores as clickable annotations. pdftotext
    only sees their labels ("LinkedIn"), never the address behind them."""
    try:
        out = subprocess.run(["pdfinfo", "-url", str(pdf)], capture_output=True,
                             text=True, timeout=30).stdout
    except Exception:
        return []
    urls = [ln.split()[-1] for ln in out.splitlines()[1:] if ln.split()]
    return [u for u in dict.fromkeys(urls) if u.startswith(("http://", "https://"))]


def attach_links(doc: dict, pdf: Path) -> dict:
    """Give the contact links their real addresses, so the CV shows
    linkedin.com/in/... rather than a bare word, and it stays clickable."""
    urls = pdf_links(pdf)
    if not urls:
        return doc
    links = doc.setdefault("contact", {}).setdefault("links", [])

    def kind(u: str) -> str:
        return "linkedin" if "linkedin.com" in u else "github" if "github.com" in u else "site"

    def label_kind(lbl: str) -> str:
        l = (lbl or "").lower()
        return "linkedin" if "linked" in l else "github" if "git" in l else "site"

    for u in urls:
        k = kind(u)
        match = next((l for l in links if not l.get("url") and label_kind(l.get("label")) == k), None)
        if match:
            match["url"] = u
        elif not any(l.get("url") == u for l in links):
            links.append({"label": {"linkedin": "LinkedIn", "github": "GitHub"}.get(k, "Portfolio"),
                          "url": u})
    return doc


# -------------------------------------------------------------- 2. edit ------
def _fields(doc: dict):
    """Every editable text field as (label, kind, getter, setter).

    kind is one of headline | summary | bullet | skills | line, carried
    explicitly rather than guessed from the label.

    Name, contact, dates, employers and schools are deliberately absent: an
    edit list may reword how you describe your work, never who or where.
    """
    yield ("headline", "headline", lambda: doc.get("headline", "") or "",
           lambda v: doc.__setitem__("headline", v))
    yield ("summary", "summary", lambda: doc.get("summary", "") or "",
           lambda v: doc.__setitem__("summary", v))
    for sec in doc.get("sections") or []:
        title = sec.get("title", "")
        for it in sec.get("items") or []:
            bl = it.setdefault("bullets", [])
            for bi in range(len(bl)):
                yield (f"{title} / {it.get('heading', '')} / bullet {bi + 1}", "bullet",
                       (lambda bl=bl, bi=bi: bl[bi]),
                       (lambda v, bl=bl, bi=bi: bl.__setitem__(bi, v)))
        for g in sec.get("groups") or []:
            g.setdefault("items", [])
            yield (f"{title} / {g.get('label', '') or 'skills'}", "skills",
                   (lambda g=g: ", ".join(g.get("items") or [])),
                   (lambda v, g=g: g.__setitem__("items", _split_items(v))))
        lines = sec.get("lines") or []
        for li in range(len(lines)):
            yield (f"{title} / line {li + 1}", "line",
                   (lambda lines=lines, li=li: lines[li]),
                   (lambda v, lines=lines, li=li: lines.__setitem__(li, v)))


def _in_protected(doc: dict, quote: str) -> bool:
    """Does the quote point at a field tailoring must never touch?"""
    q = [w for w in _words(quote) if len(w) > 2 or w.isdigit()]
    if not q:
        return False
    c = doc.get("contact") or {}
    protected = [doc.get("name", ""), c.get("email", ""), c.get("phone", ""),
                 c.get("location", "")]
    for sec in doc.get("sections") or []:
        for it in sec.get("items") or []:
            # a quote can straddle them ("Acme 2025", "06/2026 | Taroudant"),
            # so also test the entry's protected parts taken together
            parts = [it.get("org", ""), it.get("dates", ""), it.get("location", "")]
            protected += parts + [" ".join(parts)]
    for field in protected:
        have = set(_words(field))
        if have and sum(w in have for w in q) / len(q) >= 0.8:
            return True
    return False


def _split_items(s: str) -> list[str]:
    parts = re.split(r"\s*[|,;•·]\s*", s)
    return [p.strip() for p in parts if p.strip()]


def _strip_label(s: str) -> str:
    """'Cloud & DevOps: FastAPI | Docker' -> 'FastAPI | Docker'."""
    return re.sub(r"^[^:|]{2,40}:\s*", "", s).strip()


def _skills_groups(doc: dict) -> list[dict]:
    return [g for sec in doc.get("sections") or [] if sec.get("kind") == "skills"
            for g in sec.get("groups") or []]


def apply_edits(doc: dict, edits: list[dict]) -> tuple[dict, list[dict]]:
    """Apply what can be anchored, refuse the rest. Returns (doc, report)."""
    doc = json.loads(json.dumps(doc))          # never mutate the cached base
    report = []
    for e in edits:
        cur = (e.get("current") or "").strip().strip('"«»“”').strip()
        new = (e.get("suggested") or "").strip()
        sec = _norm(e.get("section", ""))
        entry = {"section": e.get("section", ""), "priority": e.get("priority", ""),
                 "current": cur, "suggested": new, "why": e.get("why", "")}
        if not new:
            report.append({**entry, "status": "skipped", "reason": "no replacement text"})
            continue

        # -- nothing to replace: only safe as an addition to skills or headline
        if _norm(cur) in _ABSENT:
            if re.search(r"comp[eé]tence|skill|stack|outil|tool", sec):
                groups = _skills_groups(doc)
                if not groups:
                    report.append({**entry, "status": "skipped",
                                   "reason": "no skills section to add to"})
                    continue
                target = max(groups, key=lambda g: difflib.SequenceMatcher(
                    None, _norm(g.get("label", "")), sec).ratio())
                have = {_norm(x) for x in target["items"]}
                added = [x for x in _split_items(_strip_label(new)) if _norm(x) not in have]
                target["items"].extend(added)
                report.append({**entry, "status": "applied" if added else "skipped",
                               "where": f"skills / {target.get('label', '')}",
                               "reason": f"added {', '.join(added)}" if added
                               else "already listed"})
            elif re.search(r"titre|title|headline|accroche", sec):
                doc["headline"] = new
                report.append({**entry, "status": "applied", "where": "headline",
                               "reason": "headline was empty"})
            else:
                report.append({**entry, "status": "skipped",
                               "reason": "nothing quoted to replace; not a skills or "
                                         "headline addition, so not applied blind"})
            continue

        # -- guard: an edit may reword, not rewrite the document
        if len(new) > 2.5 * len(cur) + 220:
            report.append({**entry, "status": "skipped",
                           "reason": "replacement much longer than the text it "
                                     "replaces — looks like a rewrite, not an edit"})
            continue

        n_cur, n_cur_bare = _norm(cur), _norm(_strip_label(cur))
        best = None                        # (score, label, kind, get, set, mode)
        for label, kind, get, set_ in _fields(doc):
            val = get()
            if not val:
                continue
            nv = _norm(val)
            if kind == "skills":
                # compare as lists: "A | B" and "A, B" are the same group
                nv = _norm(", ".join(_split_items(val)))
                probe = _norm(", ".join(_split_items(_strip_label(cur))))
                score = 1.0 if probe and probe in nv else \
                    difflib.SequenceMatcher(None, probe, nv).ratio()
                mode = "list"
            elif n_cur and n_cur in nv:
                score, mode = 1.0 + len(n_cur) / max(len(nv), 1), "substring"
            elif n_cur_bare and n_cur_bare in nv:
                score, mode = 0.99 + len(n_cur_bare) / max(len(nv), 1), "substring"
            else:
                score, mode = difflib.SequenceMatcher(
                    None, n_cur_bare or n_cur, nv).ratio(), "fuzzy"
            if best is None or score > best[0]:
                best = (score, label, kind, get, set_, mode)

        if not best or best[0] < 0.72:
            if _in_protected(doc, cur):
                reason = ("targets a protected field — dates, places, employers, "
                          "schools and contact details are never edited")
            else:
                reason = "quoted text not found in the CV" + (
                    f" (closest: {best[1]}, {best[0]:.0%})" if best else "")
            report.append({**entry, "status": "skipped", "reason": reason})
            continue

        score, label, kind, get, set_, mode = best
        if kind == "skills":
            set_(_strip_label(new))            # the suggestion is the whole new list
        elif mode == "substring":
            # replace just the quoted span, keeping the rest of the field
            val = get()
            quoted = cur if _norm(cur) in _norm(val) else _strip_label(cur)
            replacement = new if quoted == cur else _strip_label(new)
            pat = re.compile(r"\s+".join(map(re.escape, quoted.split())), re.I)
            out, n = pat.subn(lambda _m: replacement, val, count=1)
            set_(out if n else replacement)
        else:
            set_(new)                          # fuzzy: the field was the quote
        report.append({**entry, "status": "applied", "where": label,
                       "reason": f"{mode} match ({min(score, 1):.0%})"})
    return doc, report


# ------------------------------------------------------------ 3. render ------
LABELS = {"fr": {"summary": "Profil"}, "en": {"summary": "Profile"}}

# The typefaces recruiters and ATS guides recommend. Each names the metric
# clone installed on Linux first (same glyph widths as the Microsoft font, so
# the page breaks the same), then the original, then a safe fallback. Chrome
# embeds the face in the PDF, so the recruiter sees it without having it.
# `scale` evens out optical size: Calibri and Garamond set small for their
# point size, so they get more of it.
STYLES = {
    "calibri": {"label": "Calibri", "scale": 1.08, "accent": "#1f3a5f", "name_ls": "0",
                "org_style": "normal",
                "font": '"Carlito", "Calibri", "Liberation Sans", Arial, sans-serif'},
    "cambria": {"label": "Cambria", "scale": 1.0, "accent": "#23344d", "name_ls": ".005em",
                "org_style": "italic",
                "font": '"Caladea", "Cambria", Georgia, "DejaVu Serif", serif'},
    "garamond": {"label": "Garamond", "scale": 1.16, "accent": "#2a2a2a", "name_ls": ".02em",
                 "org_style": "italic",
                 "font": '"EB Garamond 12", "EB Garamond", Garamond, "Times New Roman", serif'},
    "arial": {"label": "Arial", "scale": 1.0, "accent": "#1f3a5f", "name_ls": "0",
              "org_style": "normal",
              "font": '"Liberation Sans", Arial, Helvetica, sans-serif'},
}
DEFAULT_STYLE = "calibri"

# Tried in order until the CV fits the target page count. The last step is the
# readability floor: below it a recruiter squints, so a CV that still overflows
# is left at two pages rather than shrunk further.
DENSITY = [
    {"fs": 9.6, "lh": 1.36, "margin": "13mm 14mm 12mm", "h2": "4mm", "item": "2.1mm",
     "h1": 19, "hl": 11, "ph": 25, "li": ".5mm"},
    {"fs": 9.1, "lh": 1.28, "margin": "11mm 12mm 10mm", "h2": "3.2mm", "item": "1.6mm",
     "h1": 17, "hl": 10.4, "ph": 23, "li": ".4mm"},
    {"fs": 8.7, "lh": 1.22, "margin": "9mm 11mm 8mm", "h2": "2.6mm", "item": "1.2mm",
     "h1": 16, "hl": 10, "ph": 21, "li": ".3mm"},
    {"fs": 8.4, "lh": 1.15, "margin": "8mm 10mm 7mm", "h2": "2.2mm", "item": "1mm",
     "h1": 15, "hl": 9.6, "ph": 19, "li": ".15mm"},
]

# Section order by career stage. A graduate applying for a job leads with what
# they did; a student leads with what they are studying.
ORDER = {
    "graduate": ["experience", "projects", "skills", "education", "other", "list"],
    "student":  ["education", "experience", "projects", "skills", "other", "list"],
}


def reorder(doc: dict, stage: str) -> dict:
    """Canonical section order; sections of one kind keep their relative order
    (sort is stable), and list sections — certifications, languages — close."""
    rank = {k: i for i, k in enumerate(ORDER.get(stage, ORDER["graduate"]))}
    doc["sections"] = sorted(doc.get("sections") or [],
                             key=lambda s: rank.get(s.get("kind", "other"), len(rank)))
    return doc


# The em dash is never used in a CV. Spaced, it becomes a comma ("Engineer —
# Acme" -> "Engineer, Acme"); glued, a hyphen. Applied to the whole document
# before every render, so it holds for model suggestions, the original CV's
# own text and your manual edits alike.
_EM_SPACED = re.compile(r"\s*[—―]\s*(?=\S)")
_EM = re.compile(r"[—―]")


# A spaced en dash used as a separator ("Essentials – Coursera") reads as the
# same mark and gets the same treatment. Between dates or numbers
# ("09/2023 – 06/2026") it is a range, which is its proper use, and stays.
_EN_SEPARATOR = re.compile(r"(?<![\d/.])\s+–\s+(?![\d/])")


def no_em_dash(obj):
    if isinstance(obj, str):
        obj = _EN_SEPARATOR.sub(", ", obj)
        out = _EM_SPACED.sub(lambda m: ", " if m.group(0).strip() != m.group(0) else "-", obj)
        return _EM.sub("", out).strip() if out.rstrip().endswith(("—", "―")) else _EM.sub("-", out)
    if isinstance(obj, list):
        return [no_em_dash(x) for x in obj]
    if isinstance(obj, dict):
        return {k: no_em_dash(v) for k, v in obj.items()}
    return obj


_photo_cache: dict = {}


def photo_uri(pcfg: pc.PipelineConfig, lang: str) -> str | None:
    """Your photo as a data URI, or None if there is none for this language."""
    if not pcfg.photo or not pcfg.photo.is_file():
        return None
    if pcfg.photo_langs and lang.lower() not in pcfg.photo_langs:
        return None
    key = (str(pcfg.photo), pcfg.photo.stat().st_mtime_ns)
    if key not in _photo_cache:
        import base64
        import mimetypes
        mime = mimetypes.guess_type(pcfg.photo.name)[0] or "image/png"
        _photo_cache.clear()
        _photo_cache[key] = f"data:{mime};base64," + base64.b64encode(pcfg.photo.read_bytes()).decode()
    return _photo_cache[key]


def render_html(doc: dict, lang: str, density: dict | None = None,
                photo: str | None = None) -> str:
    env = Environment(loader=FileSystemLoader(ROOT / "templates"),
                      autoescape=select_autoescape(["html"]))
    doc = no_em_dash(doc)
    # tolerate a document edited down to its bones
    doc.setdefault("contact", {})
    doc.setdefault("sections", [])
    st = STYLES.get(doc.get("style") or DEFAULT_STYLE, STYLES[DEFAULT_STYLE])
    return env.get_template("cv.html").render(
        doc=doc, lang=lang, labels=LABELS.get(lang, LABELS["en"]),
        d=density or DENSITY[0], photo=photo, st=st)


def page_count(pdf: Path) -> int:
    out = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True).stdout
    m = re.search(r"Pages:\s+(\d+)", out)
    return int(m.group(1)) if m else 0


def render_fitted(doc: dict, lang: str, out: Path, chrome: str,
                  max_pages: int = 1, photo: str | None = None) -> tuple[int, int]:
    """Render at the loosest density that fits max_pages.
    Returns (pages, density step used)."""
    for step, d in enumerate(DENSITY):
        html_to_pdf(render_html(doc, lang, d, photo), out, chrome)
        pages = page_count(out)
        if pages <= max_pages:
            return pages, step
    return pages, len(DENSITY) - 1


def find_chrome(pcfg: pc.PipelineConfig) -> str:
    for c in ([pcfg.chrome_bin] if pcfg.chrome_bin else []) + [
            "google-chrome", "google-chrome-stable", "chromium", "chromium-browser"]:
        p = shutil.which(c) if c and not Path(c).is_file() else c
        if p:
            return p
    raise TailorError("no Chrome/Chromium found to render the PDF")


def html_to_pdf(html: str, out: Path, chrome: str) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "cv.html"
        src.write_text(html, encoding="utf-8")
        r = subprocess.run(
            [chrome, "--headless=new", "--disable-gpu", "--no-sandbox",
             "--no-pdf-header-footer", f"--user-data-dir={td}/profile",
             f"--print-to-pdf={out}", src.as_uri()],
            capture_output=True, text=True, timeout=90)
    if not out.is_file() or out.stat().st_size < 1000:
        raise TailorError(f"Chrome did not produce a PDF: {r.stderr[-300:]}")


# ------------------------------------------------------------ 4. verify ------
def verify(pdf: Path, doc: dict, report: list[dict], max_pages: int = 2) -> list[str]:
    """Read the PDF back the way an ATS would. Returns problems, [] if none."""
    text = cr.pdf_text(pdf, layout=False)
    probs = []
    nt = _norm(text)
    if _norm(doc.get("name", ""))[:20] not in nt:
        probs.append("name not readable in the PDF")
    for r in report:
        if r["status"] != "applied":
            continue
        probe = _norm(_strip_label(r["suggested"]))[:40]
        if probe and probe not in nt and not all(w in nt for w in _words(probe)[:5]):
            probs.append(f"applied edit not readable in the PDF: {r['suggested'][:60]}")
    pages = page_count(pdf)
    if pages > max_pages:
        probs.append(f"{pages} pages, over the {max_pages}-page target even at "
                     f"the densest readable setting")
    return probs


# ---------------------------------------------------------- 5. per job -------
def _slug(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-")[:30] or "Company"


def output_path(pcfg: pc.PipelineConfig, cfg: cr.Config, job, variant: str,
                lang: str) -> Path:
    d = date.today().isoformat()
    owner = cfg.file_prefix.replace("-", "_")
    name = f"{owner}_{_variant_label(variant)}_{lang.upper()}_{_slug(job['company'])}_{d}.pdf"
    return pcfg.applications_dir / d / name


def tailor_job(db: DB, pcfg: pc.PipelineConfig, cfg: cr.Config, job_id: str, *,
               ask=None, log=print) -> Path:
    job = db.one("SELECT * FROM jobs WHERE id=?", job_id)
    m = db.one("SELECT * FROM matches WHERE job_id=?", job_id)
    if not job or not m:
        raise TailorError(f"{job_id}: no job or no match on file")
    variant = m["recommended_variant"]
    lang = (m["recommended_account"] or job["language"] or "en").lower()
    edits = json.loads(m["suggested_edits"] or "[]")

    base = structured(cfg, pcfg, variant, ask=ask)
    doc, report = apply_edits(base, edits)
    stage = "student" if variant.startswith("1-") else "graduate"
    doc = no_em_dash(reorder(doc, stage))
    report = [{**r, "suggested": no_em_dash(r.get("suggested", ""))} for r in report]
    photo = photo_uri(pcfg, lang)
    doc.setdefault("show_photo", photo is not None)
    doc.setdefault("style", pcfg.cv_style)
    out = output_path(pcfg, cfg, job, variant, lang)
    pages, step = render_fitted(doc, lang, out, find_chrome(pcfg),
                                max_pages=pcfg.max_pages, photo=photo)
    problems = verify(out, doc, report, max_pages=pcfg.max_pages)

    sidecar = {
        "job_id": job_id, "company": job["company"], "title": job["title"],
        "apply_url": job["apply_url"], "base_cv": variant, "lang": lang,
        "fit_score": m["fit_score"], "ats_score": m["ats_score"],
        "edits": report, "verification": problems or "ok",
        "extraction_coverage": base.get("_source", {}).get("coverage"),
        "base_sig": base.get("_source", {}).get("sig"),
        "pages": pages, "density_step": step, "section_order": stage,
        "edited_by_hand": False,
    }
    out.with_suffix(".json").write_text(json.dumps(sidecar, ensure_ascii=False, indent=1))
    # the editable document behind the PDF, so you can open and change it
    out.with_suffix(".cv.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1))

    applied = sum(r["status"] == "applied" for r in report)
    with db.tx():
        # A tailored CV is a draft until you have read it: nothing goes out
        # that you have not seen.
        db.upsert_application(
            job_id, status="draft", cv_filename=out.name,
            notes=("" if not problems else
                   f"check before validating: {'; '.join(problems)[:300]}"))
        db.set_stage(job_id, "tailored")
        db.event("tailor", job_id, ok=not problems, applied=applied,
                 refused=len(report) - applied, file=str(out), problems=problems)

    if pcfg.register_tailored and not problems:
        shutil.copy2(out, cfg.watch_dir / out.name)
    # applications_dir is configurable and may live outside the project
    shown = out.relative_to(ROOT) if out.is_relative_to(ROOT) else out
    log(f"  draft  {job['company'][:16]:16s} "
        f"{applied}/{len(report)} edits applied -> {shown}"
        + (f"\n     to check: {'; '.join(problems)}" if problems else ""))
    return out


# ------------------------------------------------ 6. manual review/editing --
def cv_paths(pcfg: pc.PipelineConfig, db: DB, job_id: str) -> tuple[Path, Path, Path]:
    """(pdf, sidecar .json, editable .cv.json) for a job's tailored CV."""
    app = db.one("SELECT date, cv_filename FROM applications WHERE job_id=?", job_id)
    if not app or not app["cv_filename"]:
        raise TailorError(f"{job_id}: no tailored CV yet")
    pdf = pcfg.applications_dir / (app["date"] or "") / app["cv_filename"]
    if not pdf.is_file():
        found = list(pcfg.applications_dir.rglob(app["cv_filename"]))
        if not found:
            raise TailorError(f"{job_id}: {app['cv_filename']} is missing on disk")
        pdf = found[0]
    return pdf, pdf.with_suffix(".json"), pdf.with_suffix(".cv.json")


def load_cv(pcfg: pc.PipelineConfig, cfg: cr.Config, db: DB, job_id: str) -> dict:
    """Everything the editor shows: the current document, the original it came
    from, and the edit report."""
    pdf, side, docf = cv_paths(pcfg, db, job_id)
    meta = json.loads(side.read_text()) if side.is_file() else {}
    doc = json.loads(docf.read_text()) if docf.is_file() else None
    base = None
    if meta.get("base_cv"):
        try:
            base = structured(cfg, pcfg, meta["base_cv"])     # cached, no model call
        except Exception:
            base = None
    if doc is None and base is not None:
        # tailored before the editable copy was kept: rebuild it the same way
        m = db.one("SELECT suggested_edits FROM matches WHERE job_id=?", job_id)
        doc, _ = apply_edits(base, json.loads(m["suggested_edits"] or "[]") if m else [])
        doc = reorder(doc, meta.get("section_order", "graduate"))
    return {"pdf": pdf, "meta": meta, "doc": doc, "base": base}


def save_cv(db: DB, pcfg: pc.PipelineConfig, cfg: cr.Config, job_id: str,
            doc: dict) -> dict:
    """Your hand edits: re-render the PDF from the document you changed.

    Unlike automatic tailoring, nothing here is refused — it is your CV. The
    PDF is still read back, so you see if a page overflows or text is lost.
    """
    pdf, side, docf = cv_paths(pcfg, db, job_id)
    meta = json.loads(side.read_text()) if side.is_file() else {}
    lang = meta.get("lang", "fr")
    if meta.get("base_cv"):
        doc = attach_links(doc, cfg.cv_root / meta["base_cv"])
    doc = no_em_dash(doc)
    pages, step = render_fitted(doc, lang, pdf, find_chrome(pcfg), max_pages=pcfg.max_pages,
                                photo=photo_uri(pcfg, lang))
    problems = verify(pdf, doc, [], max_pages=pcfg.max_pages)
    docf.write_text(json.dumps(doc, ensure_ascii=False, indent=1))
    meta.update({"pages": pages, "density_step": step, "verification": problems or "ok",
                 "edited_by_hand": True})
    side.write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    with db.tx():
        db.event("tailor", job_id, ok=not problems, edited_by_hand=True, pages=pages)
    return {"pages": pages, "density_step": step, "problems": problems, "doc": doc}


def validate_cv(db: DB, job_id: str) -> None:
    """You have read the CV and accept it: it becomes ready to submit."""
    row = db.one("SELECT status FROM applications WHERE job_id=?", job_id)
    if not row or row["status"] not in ("draft", "staged"):
        raise TailorError(f"{job_id}: only a draft can be validated "
                          f"(status is {row['status'] if row else 'missing'})")
    with db.tx():
        db.upsert_application(job_id, status="staged")
        db.event("review", job_id, validated_cv=True)


def pending_jobs(db: DB) -> list[str]:
    """Approved or auto jobs whose CV has not been tailored yet."""
    return [r["job_id"] for r in db.q(
        "SELECT a.job_id FROM applications a JOIN matches m ON m.job_id=a.job_id "
        "WHERE a.status='pending' AND (a.cv_filename IS NULL OR a.cv_filename='') "
        "ORDER BY a.fit_score DESC")]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("job_id", nargs="?")
    ap.add_argument("--pending", action="store_true")
    args = ap.parse_args()
    pcfg, cfg = pc.load(), cr.load_config()
    db = DB(pcfg.db)
    ids = pending_jobs(db) if args.pending else [args.job_id] if args.job_id else []
    if not ids:
        print("nothing to tailor")
        return 0
    rc = 0
    for jid in ids:
        try:
            tailor_job(db, pcfg, cfg, jid)
        except (TailorError, cr.AIError) as e:
            print(f"  !! {jid}: {e}", file=sys.stderr)
            rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
