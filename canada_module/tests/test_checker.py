#!/usr/bin/env python3
"""Tests for the Canada compliance checker.

Self-contained: the structured-document checks need nothing but the fixtures,
and the PDF checks render two fixture pages with Chrome and are skipped when
Chrome is absent. Nothing here reads or writes the CV index or the pipeline
database.

Run:  ./.venv/bin/python canada_module/tests/test_checker.py
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))

from canada_module import config as ccfg          # noqa: E402
from canada_module.checker import (check_doc, check_pdf, detect_lang,  # noqa: E402
                                  gutter, paper_name, probe_pdf, strip_links)
from canada_module.rules import RulesError, load_rules  # noqa: E402

FIX = HERE / "fixtures"
ok = True


def check(label, cond, detail=""):
    global ok
    print(("  PASS  " if cond else "  FAIL  ") + label
          + (f"   ({detail})" if detail and not cond else ""))
    ok = ok and bool(cond)


def ids(rep) -> set[str]:
    return {f.check for f in rep.findings}


def msgs(rep, check_id) -> str:
    return " | ".join(f.message + " " + f.evidence
                      for f in rep.findings if f.check == check_id)


def find_chrome() -> str | None:
    for c in ("google-chrome", "google-chrome-stable", "chromium",
              "chromium-browser"):
        p = shutil.which(c)
        if p:
            return p
    return None


def render(html: Path, out: Path, chrome: str) -> None:
    with tempfile.TemporaryDirectory() as td:
        subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-sandbox",
                        "--no-pdf-header-footer", f"--user-data-dir={td}/p",
                        f"--print-to-pdf={out}", html.as_uri()],
                       capture_output=True, timeout=90, check=False)


def main() -> int:
    rules = load_rules()

    # ------------------------------------------------------- 1. rules loading
    print("\n1. the rules file")
    check("canada_rules.yaml loads", rules.paper == "letter"
          and rules.max_pages == 2)
    check("every forbidden_content regex is compiled at load time",
          all(p.pattern for i in rules.forbidden for p in i.patterns))

    with tempfile.TemporaryDirectory() as td:
        bad = Path(td) / "r.yaml"
        src = rules.path.read_text(encoding="utf-8")
        # A check named in the file but not implemented would look like a rule
        # that passes, so loading must refuse it.
        bad.write_text(src + "\n  no_such_check: fail\n", encoding="utf-8")
        try:
            load_rules(bad)
            check("an unimplemented check id is refused", False)
        except RulesError as e:
            check("an unimplemented check id is refused",
                  "no_such_check" in str(e))
        bad.write_text(src.replace("  page_count: fail",
                                   "  page_count: catastrophe"),
                       encoding="utf-8")
        try:
            load_rules(bad)
            check("an unknown severity is refused", False)
        except RulesError as e:
            check("an unknown severity is refused", "severity" in str(e))
        bad.write_text(src.replace("version: 1", "version: 1\n")
                       .replace("  paper: letter", ""), encoding="utf-8")
        try:
            load_rules(bad)
            check("a missing required key is refused", False)
        except RulesError as e:
            check("a missing required key is refused", "paper" in str(e))

    # ------------------------------------------------------ 2. the config gates
    print("\n2. config refuses what it cannot vouch for")
    cfg = ccfg.load()
    check("the example config loads and is usable",
          cfg.output_dir.name == "output" and cfg.auth_mode == "omit")
    import dataclasses
    for field, value, word in (("auth_mode", "one_line", "authorized_to_work"),
                               ("credential_mode", "eca_reference", "eca_body"),
                               ("lang", "fr", "lang must be"),
                               ("location_mode", "city", "location_mode")):
        try:
            dataclasses.replace(cfg, **{field: value})
            check(f"{field}={value!r} refused", False)
        except ccfg.ConfigError as e:
            check(f"{field}={value!r} refused", word in str(e))

    # --------------------------------------------- 3. the compliant document
    print("\n3. a compliant document passes")
    good = json.loads((FIX / "compliant.cv.json").read_text(encoding="utf-8"))
    rep = check_doc(good, rules, "en")
    check("no failures", rep.ok, rep.text())
    check("no forbidden content", "forbidden_content" not in ids(rep),
          msgs(rep, "forbidden_content"))
    check("no spelling complaint", "spelling_not_canadian" not in ids(rep),
          msgs(rep, "spelling_not_canadian"))
    check("no date complaint", "date_format" not in ids(rep),
          msgs(rep, "date_format"))
    check("no banned opener", "banned_opener" not in ids(rep))
    check("no first-person pronoun", "pronoun_first_person" not in ids(rep),
          msgs(rep, "pronoun_first_person"))
    check("what it could not check is listed, not passed",
          any("paper size" in n for n in rep.not_checked))

    # ------------------------------------------ 4. the non-compliant document
    print("\n4. a non-compliant document is caught, item by item")
    bad_doc = json.loads((FIX / "noncompliant.cv.json").read_text(encoding="utf-8"))
    rep = check_doc(bad_doc, rules, "en")
    check("it fails", not rep.ok)
    forb = msgs(rep, "forbidden_content")
    for want in ("date of birth", "marital status", "nationality", "sin",
                 "gender", "references section", "visa status",
                 "street address"):
        check(f"catches {want}", want.replace("_", " ") in forb.lower(), forb)
    check("catches the declared photo", "tables_present" in ids(rep)
          or "photo" in forb.lower())
    sp = msgs(rep, "spelling_not_canadian")
    for wrong, right in (("modeling", "modelling"), ("center", "centre"),
                         ("labeling", "labelling"), ("analysing", "analyzing")):
        check(f"{wrong} -> {right}", wrong in sp, sp)
    check("ISO date caught", "ISO" in msgs(rep, "date_format"))
    check("MM/YYYY caught", "MM/YYYY" in msgs(rep, "date_format"))
    bo = msgs(rep, "banned_opener")
    for opener in ("Responsible for", "Duties included", "Worked on",
                   "Helped with", "Tasked with"):
        check(f"banned opener {opener!r}", opener in bo, bo)
    pr = msgs(rep, "pronoun_first_person")
    check("first-person I caught", "'I'" in pr, pr)
    check("first-person my caught", "'my'" in pr.lower(), pr)
    check("8 bullets over the cap of 7", "bullets_over_max" in ids(rep),
          msgs(rep, "bullets_over_max"))
    check("[METRIC?] placeholder reported, not as a failure",
          "metric_placeholder_present" in ids(rep)
          and all(f.severity == "info" for f in rep.findings
                  if f.check == "metric_placeholder_present"))
    check("section order reported", "section_order" in ids(rep),
          msgs(rep, "section_order"))

    # ------------------------------------------------- 5. the regression guards
    print("\n5. the false positives this linter has already made")
    # 'single' in "a single analysable base" was reported as marital status on
    # the very first real CV. A status value with an everyday meaning cannot be
    # a detector on its own.
    rep = check_doc({"name": "X", "contact": {"email": "a@b.co",
                     "phone": "+1 514 555 0199"},
                     "summary": "Consolidated the sources into a single base.",
                     "sections": []}, rules, "en")
    check("'single' alone is not marital status",
          "marital" not in msgs(rep, "forbidden_content").lower(),
          msgs(rep, "forbidden_content"))
    # A URL is not prose: a spelling rule firing inside a domain is pure noise.
    check("a URL is stripped before the spelling pass",
          "center" not in strip_links("see https://data-center.example.com/x"))
    check("an email is stripped before the spelling pass",
          "colors" not in strip_links("mail colors@example.com now"))
    # "I/O" and an initial are not the pronoun.
    rep = check_doc({"name": "X", "contact": {"email": "a@b.co", "phone": "+1 514 555 0199"},
                     "summary": "Tuned disk I/O with S. I. Smith on the team.",
                     "sections": []}, rules, "en")
    check("'I/O' is not the pronoun I",
          "pronoun_first_person" not in ids(rep),
          msgs(rep, "pronoun_first_person"))
    # -ize is Canadian: optimize must never be "corrected" to optimise.
    rep = check_doc({"name": "X", "contact": {"email": "a@b.co", "phone": "+1 514 555 0199"},
                     "summary": "Optimized and containerized the service, and "
                                "analyzed the organization's colour palette.",
                     "sections": []}, rules, "en")
    check("-ize and -yze forms are left alone",
          "spelling_not_canadian" not in ids(rep),
          msgs(rep, "spelling_not_canadian"))

    # --------------------------------------------------- 6. Quebec French pass
    print("\n6. the Quebec French variant")
    fr = {"name": "Souhaib GARAAOUCH",
          "contact": {"email": "a@b.co", "phone": "+1 514 555 0199"},
          "summary": "Ingenieur de donnees. Adresse e-mail et telephone "
                     "portable ci-dessus. Job recherche au Quebec.",
          "sections": [{"title": "FORMATION", "kind": "list", "lines": ["ENSIASD"]}]}
    rep = check_doc(fr, rules, "fr_qc")
    sp = msgs(rep, "spelling_not_canadian")
    for wrong, right in (("e-mail", "courriel"), ("portable", "cellulaire"),
                         ("job", "emploi")):
        check(f"Quebec: {wrong} -> {right}", wrong in sp, sp)
    check("language auto-detection finds French",
          detect_lang("formation expérience compétences développement "
                      "conception courriel à é è ê ô ç") == "fr_qc")
    check("language auto-detection finds English",
          detect_lang("Designed and built a data pipeline for anomaly "
                      "detection in production") == "en")

    # ----------------------------------------------------- 7. the PDF checks
    print("\n7. PDF-level checks")
    chrome = find_chrome()
    if not chrome:
        print("  skip  PDF checks (no Chrome)")
    else:
        check("letter is recognized", paper_name(612.0, 792.0) == "letter")
        check("A4 is recognized, tolerating Chrome's rounding",
              paper_name(594.96, 841.92) == "a4")
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            good_pdf, bad_pdf = td / "good.pdf", td / "bad.pdf"
            render(FIX / "compliant.html", good_pdf, chrome)
            render(FIX / "noncompliant.html", bad_pdf, chrome)
            if not good_pdf.is_file() or not bad_pdf.is_file():
                check("fixtures rendered", False, "Chrome produced no PDF")
            else:
                rep = check_pdf(good_pdf, rules, "en")
                check("the compliant PDF passes", rep.ok, rep.text())
                check("letter accepted", "paper_size" not in ids(rep))
                check("one column accepted", "column_count" not in ids(rep),
                      msgs(rep, "column_count"))
                check("no image complaint",
                      "forbidden_content" not in ids(rep),
                      msgs(rep, "forbidden_content"))
                check("email and phone found",
                      "missing_required_contact" not in ids(rep),
                      msgs(rep, "missing_required_contact"))

                rep = check_pdf(bad_pdf, rules, "en")
                check("the non-compliant PDF fails", not rep.ok)
                check("A4 caught", "paper_size" in ids(rep),
                      msgs(rep, "paper_size"))
                check("the sidebar is caught as two columns",
                      "column_count" in ids(rep), msgs(rep, "column_count"))
                check("the embedded image is caught",
                      "image" in msgs(rep, "forbidden_content").lower(),
                      msgs(rep, "forbidden_content"))
                check("the font outside the allowed list is caught",
                      "font_not_allowed" in ids(rep),
                      msgs(rep, "font_not_allowed"))
                forb = msgs(rep, "forbidden_content").lower()
                for want in ("date of birth", "nationality", "sin", "gender"):
                    check(f"PDF text: {want}", want in forb, forb)

                # a right-aligned date is not a column: the real CVs put dates
                # on the right of a heading row and must not trip the gutter test
                p = probe_pdf(good_pdf)
                check("no gutter found on a single-column page",
                      gutter(p.words, 1, p.page_box) is None)

    print("\n" + ("ALL PASS" if ok else "FAILURES ABOVE"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
