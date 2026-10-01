"""Lint a resume against the Canadian rules.

A resume reaches the linter either as a PDF, which is what an employer sees, or
as a cv-router structured document, which is what the converter produces. The
two carry different evidence and the checks are split accordingly:

  PDF only    paper size, page count, columns, images, selectable text, fonts,
              headers and footers
  doc only    section order, summary length, bullets per section
  both        forbidden content, spelling, dates, banned openers, pronouns

Anything a format cannot answer is listed in `Report.not_checked` rather than
reported as a pass. A rule that silently did not run is worse than a warning.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree as ET

from .rules import Rules, SEVERITIES

# Paper sizes in points, with the tolerance Chrome's own output needs: it
# rounds, so an "A4" page measures 594.96 x 841.92 rather than 595 x 842.
PAPERS = {"letter": (612.0, 792.0), "a4": (595.28, 841.89),
          "legal": (612.0, 1008.0), "a5": (419.53, 595.28)}
PAPER_TOL = 4.0

EMAIL_RX = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
URL_RX = re.compile(r"(?:https?://|www\.)\S+|\b[\w-]+\.(?:com|org|net|io|ca|dev|app|vercel\.app)\b")
PHONE_RX = re.compile(r"(?:\+\d{1,3}[\s.-]?)?(?:\(\d{2,4}\)[\s.-]?|\d{2,4}[\s.-])\d{2,4}[\s.-]?\d{2,4}")
ISO_DATE_RX = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
NUM_DATE_RX = re.compile(r"\b(0?[1-9]|1[0-2])/(19|20)\d{2}\b")
SLASH_DMY_RX = re.compile(r"\b\d{1,2}/\d{1,2}/(19|20)?\d{2}\b")

# "I" is a pronoun, but also an initial, a roman numeral and half of "I/O".
PRONOUN_I_RX = re.compile(r"\bI\b(?!\s*[/.)])(?!\s*-\s*\d)")

FR_MARKERS = ("é", "è", "à", "ê", "ô", "ç", "formation", "expérience",
              "compétences", "développ", "conception", "courriel")


# ---------------------------------------------------------------------- model
@dataclass
class Finding:
    check: str
    severity: str
    message: str
    fix: str = ""
    where: str = ""
    evidence: str = ""

    def __post_init__(self) -> None:
        assert self.severity in SEVERITIES, self.severity

    def line(self) -> str:
        mark = {"fail": "FAIL", "warn": "WARN", "info": "info"}[self.severity]
        s = f"  {mark:<4} [{self.check}] {self.message}"
        if self.where:
            s += f"  ({self.where})"
        if self.evidence:
            s += f"\n         found: {self.evidence!r}"
        if self.fix:
            s += f"\n         fix: {self.fix}"
        return s


@dataclass
class Report:
    target: str
    lang: str
    findings: list[Finding] = field(default_factory=list)
    not_checked: list[str] = field(default_factory=list)

    def add(self, rules: Rules, check: str, message: str, fix: str = "",
            where: str = "", evidence: str = "", severity: str | None = None
            ) -> None:
        """Record a finding at the severity the rules file asks for.

        `severity` overrides it only where an entry carries its own, as the
        forbidden_content items do.
        """
        if not rules.enabled(check):
            return
        self.findings.append(Finding(
            check=check, severity=severity or rules.severity(check),
            message=message, fix=fix, where=where, evidence=evidence))

    @property
    def fails(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "fail"]

    @property
    def warns(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "warn"]

    @property
    def ok(self) -> bool:
        """Compliant means no failure. Warnings are for a human to judge."""
        return not self.fails

    def counts(self) -> dict[str, int]:
        return {s: sum(1 for f in self.findings if f.severity == s)
                for s in SEVERITIES}

    def to_dict(self) -> dict:
        return {"target": self.target, "lang": self.lang, "ok": self.ok,
                "counts": self.counts(), "not_checked": self.not_checked,
                "findings": [vars(f) for f in self.findings]}

    def merge(self, other: "Report") -> "Report":
        """Combine a document report and a PDF report of the same resume.

        Each one's `not_checked` is the other one's job, so anything both of them
        could not reach is what survives here.
        """
        mine = {n for n in self.not_checked}
        theirs = {n for n in other.not_checked}
        out = Report(target=other.target or self.target, lang=self.lang)
        out.findings = self.findings + other.findings
        covered = ("paper size, page count, columns, fonts",
                   "tables", "font size", "section order, summary length")
        out.not_checked = sorted(
            n for n in (mine | theirs)
            if not any(n.startswith(c) for c in covered))
        return out

    def text(self) -> str:
        c = self.counts()
        head = (f"{'PASS' if self.ok else 'FAIL'}  {self.target}  "
                f"[{self.lang}]  "
                f"{c['fail']} failure(s), {c['warn']} warning(s), "
                f"{c['info']} note(s)")
        order = {"fail": 0, "warn": 1, "info": 2}
        body = [f.line() for f in sorted(self.findings,
                                         key=lambda f: order[f.severity])]
        out = [head] + body
        if self.not_checked:
            out.append("  not checked here: " + ", ".join(self.not_checked))
        return "\n".join(out)


# ------------------------------------------------------------------- probing
@dataclass
class PdfProbe:
    pages: int
    sizes: list[tuple[float, float]]
    fonts: list[str]
    images: int
    text: str
    layout: str
    words: list[tuple[int, float, float, float, float, str]]  # page,x0,y0,x1,y1,w
    page_box: tuple[float, float]


def _run(cmd: list[str]) -> str:
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    return r.stdout


def probe_pdf(path: Path) -> PdfProbe:
    for tool in ("pdfinfo", "pdftotext", "pdffonts", "pdfimages"):
        if not shutil.which(tool):
            raise RuntimeError(f"{tool} not found; install poppler-utils")

    info = _run(["pdfinfo", str(path)])
    pages = 0
    sizes: list[tuple[float, float]] = []
    for ln in info.splitlines():
        if ln.startswith("Pages:"):
            pages = int(ln.split(":", 1)[1].strip() or 0)
        m = re.match(r"Page size:\s+([\d.]+) x ([\d.]+) pts", ln)
        if m:
            sizes.append((float(m.group(1)), float(m.group(2))))

    fonts = []
    for ln in _run(["pdffonts", str(path)]).splitlines()[2:]:
        name = ln.split()[0] if ln.split() else ""
        if name:
            # poppler prints subset fonts as "AAAAAA+Carlito"
            fonts.append(name.split("+", 1)[-1])

    img_lines = _run(["pdfimages", "-list", str(path)]).splitlines()
    images = max(0, len([l for l in img_lines if re.match(r"\s*\d+\s+\d+", l)]))

    text = _run(["pdftotext", str(path), "-"])
    layout = _run(["pdftotext", "-layout", str(path), "-"])

    words: list[tuple[int, float, float, float, float, str]] = []
    box = (sizes[0] if sizes else (612.0, 792.0))
    bbox = _run(["pdftotext", "-bbox", str(path), "-"])
    try:
        root = ET.fromstring(bbox)
    except ET.ParseError:
        root = None
    if root is not None:
        ns = {"x": "http://www.w3.org/1999/xhtml"}
        for pno, page in enumerate(root.iter("{http://www.w3.org/1999/xhtml}page"), 1):
            if pno == 1:
                try:
                    box = (float(page.get("width")), float(page.get("height")))
                except (TypeError, ValueError):
                    pass
            for w in page.iter("{http://www.w3.org/1999/xhtml}word"):
                try:
                    words.append((pno, float(w.get("xMin")), float(w.get("yMin")),
                                  float(w.get("xMax")), float(w.get("yMax")),
                                  (w.text or "")))
                except (TypeError, ValueError):
                    continue
    return PdfProbe(pages=pages, sizes=sizes, fonts=fonts, images=images,
                    text=text, layout=layout, words=words, page_box=box)


def paper_name(w: float, h: float) -> str:
    for name, (pw, ph) in PAPERS.items():
        if abs(w - pw) <= PAPER_TOL and abs(h - ph) <= PAPER_TOL:
            return name
    return f"{w:.0f}x{h:.0f}pts"


def gutter(words, page: int, box: tuple[float, float]) -> tuple[float, float] | None:
    """The widest empty vertical strip that is really a column gutter, or None.

    Two measurements that the obvious version gets wrong:

    A right-aligned date on a heading row is not a column, so the text on each
    side of the strip has to run most of the way down. But "most of the way
    down the PAGE" is the wrong yardstick: a one-page resume on A4 fills about
    40% of the sheet, and requiring more rejected a genuine sidebar. The span is
    therefore measured against the height of the text block, not the paper.

    And the empty strip is narrower than the CSS gap that produced it, because a
    wrapped line in the sidebar reaches further right than the column's nominal
    edge. A 14mm gap measured 24pt here, so the threshold is a real gutter's
    minimum width rather than a fraction of the page.
    """
    pw, ph = box
    ws = [w for w in words if w[0] == page]
    if len(ws) < 40:
        return None

    ty0 = min(w[2] for w in ws)
    ty1 = max(w[4] for w in ws)
    th = ty1 - ty0
    if th < 0.25 * ph:               # too little text to tell a layout from it
        return None

    step = 2.0
    inner = (0.12 * pw, 0.88 * pw)   # the margins are not gutters
    occupied = set()
    for _, x0, _, x1, _, _ in ws:
        for b in range(int(x0 // step), int(x1 // step) + 1):
            occupied.add(b)
    runs, cur = [], None
    for b in range(int(inner[0] // step), int(inner[1] // step) + 1):
        if b in occupied:
            if cur is not None:
                runs.append(cur)
                cur = None
        else:
            cur = (cur[0], b) if cur else (b, b)
    if cur:
        runs.append(cur)
    if not runs:
        return None
    best = max(runs, key=lambda r: r[1] - r[0])
    gx0, gx1 = best[0] * step, (best[1] + 1) * step
    if gx1 - gx0 < max(12.0, 0.02 * pw):
        return None

    left = [w for w in ws if w[3] <= gx0]
    right = [w for w in ws if w[1] >= gx1]
    floor = max(15, int(0.15 * len(ws)))
    if len(left) < floor or len(right) < floor:
        return None

    def span(side) -> float:
        ys = [w[2] for w in side] + [w[4] for w in side]
        return (max(ys) - min(ys)) / th

    return (gx0, gx1) if span(left) >= 0.6 and span(right) >= 0.6 else None


def detect_lang(text: str) -> str:
    low = text.lower()
    return "fr_qc" if sum(low.count(m) for m in FR_MARKERS) > 12 else "en"


def strip_links(text: str) -> str:
    """Remove URLs and emails before any spelling check.

    `souhaib-garaaouch.vercel.app` and a GitHub path are not prose, and a
    spelling rule that fires inside one is pure noise.
    """
    return URL_RX.sub(" ", EMAIL_RX.sub(" ", text))


# ----------------------------------------------------------- shared text pass
def check_text(rep: Report, rules: Rules, text: str, lang: str,
               bullets: list[str] | None = None) -> None:
    prose = strip_links(text)

    for item in rules.forbidden:
        for rx in item.patterns:
            m = rx.search(prose)
            if m:
                rep.add(rules, "forbidden_content",
                        f"{item.id.replace('_', ' ')} found"
                        + (f": {item.why}" if item.why else ""),
                        fix=f"remove it ({item.source or 'see RESEARCH.md'})",
                        evidence=m.group(0)[:60].strip(),
                        severity=item.severity)
                break

    L = rules.lang(lang)
    keep = {k.lower() for k in L.get("keep", [])}
    for wrong, right in (L.get("substitute") or {}).items():
        if wrong.lower() in keep:
            continue
        rx = re.compile(rf"\b{re.escape(wrong)}\b", re.IGNORECASE)
        hits = rx.findall(prose)
        if hits:
            rep.add(rules, "spelling_not_canadian",
                    f"{wrong!r} is not the Canadian form"
                    f" ({len(hits)}x)",
                    fix=f"use {right!r}", evidence=hits[0])
    for word, note in (L.get("review") or {}).items():
        if re.search(rf"\b{re.escape(word)}\b", prose, re.IGNORECASE):
            rep.add(rules, "spelling_not_canadian",
                    f"{word!r} needs a human decision: {note.strip()}",
                    severity="info")

    if ISO_DATE_RX.search(prose):
        rep.add(rules, "date_format", "ISO date (YYYY-MM-DD) found",
                fix=f"use {rules.d['dates']['format']!r}",
                evidence=ISO_DATE_RX.search(prose).group(0))
    for rx, what in ((NUM_DATE_RX, "numeric month/year (MM/YYYY)"),
                     (SLASH_DMY_RX, "numeric date (DD/MM/YY)")):
        m = rx.search(prose)
        if m:
            rep.add(rules, "date_format", f"{what} found",
                    fix=f"use {rules.d['dates']['format']!r}, "
                        f"e.g. 'Feb 2026'", evidence=m.group(0))

    lines = bullets if bullets is not None else [
        l.strip() for l in prose.splitlines() if l.strip()]
    for opener in rules.d["bullets"]["banned_openers"]:
        hit = next((l for l in lines
                    if l.lower().lstrip("•-‣· ").startswith(opener.lower())), None)
        if hit:
            rep.add(rules, "banned_opener",
                    f"a bullet opens with {opener!r}",
                    fix="open with an action verb and name the result",
                    evidence=hit[:70])

    pron = [p for p in rules.d["bullets"]["banned_pronouns"] if p != "I"]
    for p in pron:
        if re.search(rf"\b{re.escape(p)}\b", prose, re.IGNORECASE):
            rep.add(rules, "pronoun_first_person",
                    f"first-person {p!r} found",
                    fix="Job Bank: write in the third person, no I / my / me")
    if PRONOUN_I_RX.search(prose):
        rep.add(rules, "pronoun_first_person", "first-person 'I' found",
                fix="Job Bank: write in the third person, no I / my / me",
                evidence=PRONOUN_I_RX.search(prose).group(0))

    ph = rules.d["bullets"]["metric"]["placeholder"]
    n = prose.count(ph)
    if n:
        rep.add(rules, "metric_placeholder_present",
                f"{n} unresolved {ph} placeholder(s)",
                fix="supply the figure, or cut the clause", severity="info")


# -------------------------------------------------------------------- PDF
def check_pdf(path: Path | str, rules: Rules, lang: str | None = None) -> Report:
    path = Path(path)
    p = probe_pdf(path)
    lang = lang or detect_lang(p.text)
    rep = Report(target=path.name, lang=lang)

    if len(p.text.strip()) < 200:
        rep.add(rules, "text_not_selectable",
                "almost no extractable text: the PDF looks like an image",
                fix="export with real text, not a scan or a screenshot")
        rep.not_checked.append("every text rule (no text to read)")
        return rep

    if p.pages > rules.max_pages:
        rep.add(rules, "page_count",
                f"{p.pages} pages, the maximum is {rules.max_pages}",
                fix="cut the weakest content; do not shrink the font")
    elif p.pages == 0:
        rep.add(rules, "page_count", "could not read a page count")

    want = rules.paper
    for i, (w, h) in enumerate(p.sizes, 1):
        got = paper_name(w, h)
        if got != want:
            rep.add(rules, "paper_size",
                    f"page size is {got}, the rule is {want}",
                    fix=f"render at {want} "
                        f"({PAPERS[want][0]:.0f} x {PAPERS[want][1]:.0f} pts)",
                    where=f"page {i}" if len(p.sizes) > 1 else "")

    image_rules = [i for i in rules.forbidden if i.pdf_has_image]
    if p.images:
        for item in image_rules:
            rep.add(rules, "forbidden_content",
                    f"{p.images} embedded image(s); if any is a {item.id}, "
                    f"remove it. A PDF does not say what an image is.",
                    fix=f"remove embedded images ({item.source or 'see RESEARCH.md'})",
                    severity=item.severity)
        if not image_rules:
            rep.add(rules, "images_present", f"{p.images} embedded image(s)",
                    fix="Greenhouse lists graphics and photos as a parse "
                        "failure; remove them")

    want_cols = int(rules.d["document"]["layout"]["columns"])
    for pg in range(1, max(1, p.pages) + 1):
        g = gutter(p.words, pg, p.page_box)
        if g and want_cols == 1:
            rep.add(rules, "column_count",
                    f"a {g[1] - g[0]:.0f}pt vertical gutter runs down the page: "
                    "this looks like two columns",
                    fix="Greenhouse lists a columned layout as a parse "
                        "failure; use one column",
                    where=f"page {pg}" if p.pages > 1 else "")

    allowed = {f.lower() for f in rules.d["document"]["font"]["allowed"]}
    seen = {f for f in p.fonts if f}
    bad = sorted({f for f in seen
                  if not any(a in f.lower() or f.lower() in a
                             for a in allowed)})
    if bad:
        rep.add(rules, "font_not_allowed",
                f"font(s) outside the allowed list: {', '.join(bad)}",
                fix="use one of: "
                    + ", ".join(sorted(rules.d['document']['font']['allowed'])))
    families = {re.split(r"[-,]", f)[0].lower() for f in seen if f}
    if len(families) > 2 and rules.d["document"]["font"]["one_family_throughout"]:
        rep.add(rules, "multiple_font_families",
                f"{len(families)} font families: {', '.join(sorted(families))}",
                fix="UBC: use one font throughout")

    if p.pages >= 2:
        _check_running_text(rep, rules, p)
    else:
        rep.not_checked.append("headers and footers (needs 2+ pages to detect)")

    if not EMAIL_RX.search(p.text):
        rep.add(rules, "missing_required_contact", "no email address found",
                fix="Job Bank requires name, address, email and phone")
    if not PHONE_RX.search(p.text):
        rep.add(rules, "missing_required_contact", "no phone number found",
                fix="Job Bank requires name, address, email and phone")

    check_text(rep, rules, p.layout, lang)
    rep.not_checked.extend([
        "tables (a PDF carries no table semantics; checked on the structured "
        "document instead)",
        "font size (estimated only from a PDF; exact on a document we render)",
        "section order, summary length, bullets per section (structured "
        "document only)",
    ])
    return rep


def _check_running_text(rep: Report, rules: Rules, p: PdfProbe) -> None:
    """A string repeated at the same height on every page is a header or footer."""
    ph = p.page_box[1]
    bands: dict[tuple[str, int], set[int]] = {}
    for pg, _x0, y0, _x1, _y1, word in p.words:
        if not word.strip():
            continue
        top, bot = y0 < 0.07 * ph, y0 > 0.93 * ph
        if top or bot:
            bands.setdefault((word.strip().lower(), int(y0 // 6)),
                             set()).add(pg)
    repeated = sorted({w for (w, _), pgs in bands.items()
                       if len(pgs) >= p.pages and len(w) > 2})
    if repeated:
        rep.add(rules, "header_footer_present",
                f"text repeats at the same height on every page: "
                f"{', '.join(repeated[:4])}",
                fix="Greenhouse cannot read a header or footer; move the "
                    "content into the body")


# -------------------------------------------------------- structured document
def check_doc(doc: dict, rules: Rules, lang: str | None = None) -> Report:
    """Lint a cv-router structured document (the .cv.json shape)."""
    flat = _doc_text(doc)
    lang = lang or detect_lang(flat)
    rep = Report(target=doc.get("name", "document"), lang=lang)

    contact = doc.get("contact", {}) or {}
    for want in rules.d["contact"]["required"]:
        if want == "name":
            present = bool(doc.get("name"))
        else:
            present = bool(contact.get(want))
        if not present:
            rep.add(rules, "missing_required_contact", f"no {want}")

    headings = rules.headings(lang)
    want_order = [headings[k] for k in rules.order(lang) if k in headings]
    got = [s.get("title", "") for s in doc.get("sections", [])]
    ranked = [want_order.index(t) for t in got if t in want_order]
    if ranked != sorted(ranked):
        rep.add(rules, "section_order",
                "sections are not in the configured order",
                fix=" -> ".join(want_order), evidence=" -> ".join(got),
                severity="info")

    lo, hi = (rules.d["sections"]["summary_lines"]["min"],
              rules.d["sections"]["summary_lines"]["max"])
    summary = (doc.get("summary") or "").strip()
    if summary:
        # ~105 characters to a rendered line at the densities this repo uses
        est = max(1, round(len(summary) / 105))
        if not lo <= est <= hi:
            rep.add(rules, "summary_length",
                    f"summary reads as about {est} line(s); the rule is "
                    f"{lo}-{hi}", severity="info")

    cap = int(rules.d["sections"]["bullets_per_section"]["max"])
    warn_at = int(rules.d["sections"]["bullets_per_section"].get(
        "warn_above", cap))
    bullets: list[str] = []
    for sec in doc.get("sections", []):
        for item in sec.get("items", []) or []:
            bs = [b for b in (item.get("bullets") or []) if b]
            bullets.extend(bs)
            if len(bs) > cap:
                rep.add(rules, "bullets_over_max",
                        f"{len(bs)} bullets, the maximum is {cap}",
                        where=f"{sec.get('title', '')} / "
                              f"{item.get('heading', '')}",
                        fix="Job Bank caps a section at 5-7 bullets")
            elif len(bs) > warn_at:
                rep.add(rules, "bullets_over_max",
                        f"{len(bs)} bullets, more than the {warn_at} Job Bank "
                        "suggests", where=f"{sec.get('title', '')} / "
                                          f"{item.get('heading', '')}",
                        severity="info")

    if doc.get("photo") or any(s.get("kind") == "table"
                               for s in doc.get("sections", [])):
        rep.add(rules, "tables_present",
                "the document declares a photo or a table")

    check_text(rep, rules, flat, lang, bullets=bullets)
    rep.not_checked.extend([
        "paper size, page count, columns, fonts (render it and check the PDF)",
    ])
    return rep


def _doc_text(doc: dict) -> str:
    out: list[str] = [str(doc.get("name", "")), str(doc.get("headline", "")),
                      str(doc.get("summary", ""))]
    c = doc.get("contact", {}) or {}
    out += [str(v) for k, v in c.items() if isinstance(v, str)]
    for sec in doc.get("sections", []):
        out.append(str(sec.get("title", "")))
        for item in sec.get("items", []) or []:
            out += [str(item.get(k, "")) for k in
                    ("heading", "org", "dates", "location")]
            out += [str(b) for b in (item.get("bullets") or [])]
        for grp in sec.get("groups", []) or []:
            out.append(str(grp.get("label", "")))
            out += [str(x) for x in (grp.get("items") or [])]
        out += [str(x) for x in (sec.get("lines") or [])]
    return "\n".join(x for x in out if x)
