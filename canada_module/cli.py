"""The studio's own entry point.

    python -m canada_module check <pdf|cv.json> [--lang en|fr_qc] [--json]
    python -m canada_module check --role de --lang en        # from the library
    python -m canada_module convert --role de --lang en      # build a Canadian one
    python -m canada_module convert <cv.json> --lang fr_qc
    python -m canada_module tailor jd.txt --company Shopify --city "Toronto, ON"
    python -m canada_module rules                            # show what loaded

Independent of run_pipeline.py on purpose: nothing here starts the pipeline,
and the pipeline never calls into here.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import re
import sys
from datetime import date
from pathlib import Path

from . import __version__, config as ccfg
from .checker import check_doc, check_pdf
from .convert import convert
from .customize import match, emphasise, pick_lang, pick_role
from .rules import RulesError, load_rules
from . import render as R

ROOT = Path(__file__).resolve().parent.parent

# The six role CVs, by the slug used in their filenames.
ROLE_FILES = {"ai": "AI_Engineer", "mlops": "MLOps", "devops": "DevOps",
              "ds": "Data_Scientist", "de": "Data_Engineer",
              "swe": "Software_Engineer"}


class LibraryMissing(RuntimeError):
    """A role CV, or its structured source, is not in the collection.

    An ordinary exception rather than SystemExit: these helpers are called from
    the CLI, where exiting is right, and from a web handler, where exiting is a
    server that stops answering. Each caller decides what it means.
    """


def _library_pdf(role: str, lang: str) -> Path:
    """Find a role CV in the indexed library, read-only.

    Uses the index rather than a hardcoded folder, so a CV that moved is still
    found. Nothing is written back.
    """
    sys.path.insert(0, str(ROOT))
    import cvrouter as cr

    cfg = cr.load_config()
    stem = f"Souhaib_Garaaouch_{ROLE_FILES[role]}_{'EN' if lang == 'en' else 'FR'}"
    hits = sorted(cfg.cv_root.rglob(f"{stem}.pdf"))
    if not hits:
        raise LibraryMissing(f"no {stem}.pdf under {cfg.cv_root}")
    return hits[0]


def cmd_check(args) -> int:
    rules = load_rules(args.rules)
    lang = args.lang

    if args.role:
        target = _library_pdf(args.role, lang or "en")
    elif args.target:
        target = Path(args.target)
    else:
        raise SystemExit("give a file, or --role")
    if not target.is_file():
        raise SystemExit(f"no such file: {target}")

    if target.suffix.lower() == ".json" or target.name.endswith(".cv.json"):
        rep = check_doc(json.loads(target.read_text(encoding="utf-8")),
                        rules, lang)
        rep.target = target.name
    else:
        rep = check_pdf(target, rules, lang)

    print(json.dumps(rep.to_dict(), ensure_ascii=False, indent=1)
          if args.json else rep.text())
    return 0 if rep.ok else 1


def _library_doc(role: str, lang: str) -> tuple[dict, Path]:
    """The structured source beside a role CV, read-only.

    The .cv.json is the source of record for a conversion. Extracting structure
    from a PDF costs a model call and loses whatever the extractor missed, so a
    resume without one is reported rather than guessed at.
    """
    pdf = _library_pdf(role, lang)
    side = pdf.with_suffix("").with_suffix(".cv.json")
    if not side.is_file():
        side = pdf.parent / (pdf.stem + ".cv.json")
    if not side.is_file():
        raise LibraryMissing(
            f"no structured source beside {pdf.name}. The converter works from "
            f"a .cv.json; build one with the pipeline, or pass a .cv.json "
            f"directly.")
    return json.loads(side.read_text(encoding="utf-8")), pdf


def cmd_convert(args) -> int:
    rules = load_rules(args.rules)
    cfg = ccfg.load(args.config)
    lang = args.lang or cfg.lang

    if args.role:
        doc, src = _library_doc(args.role, lang)
        stem = f"{ROLE_FILES[args.role]}_{lang}"
    elif args.target:
        src = Path(args.target)
        if not src.is_file():
            raise SystemExit(f"no such file: {src}")
        doc = json.loads(src.read_text(encoding="utf-8"))
        stem = f"{src.name.split('.')[0]}_{lang}"
    else:
        raise SystemExit("give a .cv.json, or --role")

    out_doc, log = convert(doc, rules, cfg, lang)
    out_dir = Path(args.out) if args.out else cfg.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / f"{stem}.cv.json"
    json_path.write_text(json.dumps(out_doc, ensure_ascii=False, indent=1),
                         encoding="utf-8")
    log_path = out_dir / f"{stem}.changelog.txt"
    log_path.write_text(
        f"{src.name} -> {stem}\n"
        f"rules {rules.path.name}  config {cfg.path.name}  lang {lang}\n\n"
        + log.text() + "\n", encoding="utf-8")

    pdf_path = out_dir / f"{stem}.pdf"
    note = ""
    if args.no_render:
        print(f"  wrote {json_path.name} and {log_path.name} (no render asked)")
    else:
        chrome = R.find_chrome(cfg.chrome_bin)
        pages, step, note = R.render_pdf(
            out_doc, lang, pdf_path, chrome,
            prefer_pages=int(rules.d["document"]["pages"]["prefer"]),
            max_pages=rules.max_pages)
        print(f"  {pdf_path.name}  {pages} page(s), {R.DENSITY[step]['fs']}pt")
        if note:
            print(f"  !! {note}")
        if cfg.emit_docx:
            docx_path = out_dir / f"{stem}.docx"
            R.render_docx(out_doc, lang, docx_path)
            print(f"  {docx_path.name}")

    rep = check_doc(out_doc, rules, lang)
    if not args.no_render and pdf_path.is_file():
        # The PDF is what an employer opens, so it is what gets linted. The
        # document check answers paper-blind questions the PDF cannot.
        rep = rep.merge(check_pdf(pdf_path, rules, lang))
    else:
        rep.target = json_path.name
    print()
    print(rep.text())
    print()
    print(log.text())
    if note:
        print(f"\nadvice: {note}")
    return 0 if rep.ok else 1


def _slug(s: str, n: int = 24) -> str:
    out = re.sub(r"[^A-Za-z0-9]+", "-", (s or "").strip()).strip("-")
    return out[:n] or "posting"


def cmd_tailor(args) -> int:
    """One posting in, one Canadian resume out, with the reasoning printed."""
    rules = load_rules(args.rules)
    cfg = ccfg.load(args.config)

    jd = (Path(args.jd).read_text(encoding="utf-8") if args.jd != "-"
          else sys.stdin.read())
    if len(jd.strip()) < 80:
        raise SystemExit("that posting is too short to read anything from")

    lang, why_lang = pick_lang(jd, args.city or "", args.lang)
    role, why_role = (args.role, "you chose it") if args.role else pick_role(jd)
    print(f"  role     {role:<6} {why_role}")
    print(f"  language {lang:<6} {why_lang}")

    # The province and city a posting names override the config defaults, so a
    # Toronto ad gets "Toronto, ON" without editing canada.toml.
    if args.city and cfg.location_mode == "city_province":
        city, _, prov = args.city.partition(",")
        cfg = dataclasses.replace(cfg, city_default=city.strip(),
                                  province=(prov.strip() or cfg.province))
        print(f"  contact  {city.strip()}, {prov.strip() or cfg.province}")
    elif args.city:
        # A flag that silently does nothing is worse than no flag.
        print(f"  contact  location_mode is {cfg.location_mode!r}, so --city "
              f"{args.city!r} only chose the language, not the contact line")

    doc, src = _library_doc(role, lang)
    canadian, log = convert(doc, rules, cfg, lang)
    m = match(canadian, jd, rules, lang)
    tailored = emphasise(canadian, m, log, bullets=not args.no_bullets)
    after = match(tailored, jd, rules, lang)

    out_dir = Path(args.out) if args.out else cfg.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = (f"{ROLE_FILES[role]}_{lang}_{_slug(args.company)}_"
            f"{date.today().isoformat()}")

    (out_dir / f"{stem}.cv.json").write_text(
        json.dumps(tailored, ensure_ascii=False, indent=1), encoding="utf-8")
    (out_dir / f"{stem}.changelog.txt").write_text(
        f"{src.name} -> {stem}\n"
        f"role {role} ({why_role})\nlanguage {lang} ({why_lang})\n"
        f"company {args.company or '-'}  city {args.city or '-'}\n\n"
        + m.text() + "\n\n" + log.text() + "\n", encoding="utf-8")

    note = ""
    pdf_path = out_dir / f"{stem}.pdf"
    if not args.no_render:
        chrome = R.find_chrome(cfg.chrome_bin)
        pages, step, note = R.render_pdf(
            tailored, lang, pdf_path, chrome,
            prefer_pages=int(rules.d["document"]["pages"]["prefer"]),
            max_pages=rules.max_pages)
        print(f"  {pdf_path.name}  {pages} page(s), {R.DENSITY[step]['fs']}pt")
        if cfg.emit_docx:
            R.render_docx(tailored, lang, out_dir / f"{stem}.docx")
            print(f"  {stem}.docx")

    rep = check_doc(tailored, rules, lang)
    if not args.no_render and pdf_path.is_file():
        rep = rep.merge(check_pdf(pdf_path, rules, lang))
    print()
    print(m.text())
    if after.score != m.score:
        print(f"  !! reordering changed the score {m.score} -> {after.score}; "
              f"it should not, since no word changed")
    print()
    print(rep.text())
    print()
    print(log.text())
    if note:
        print(f"\nadvice: {note}")
    return 0 if rep.ok else 1


def cmd_rules(args) -> int:
    rules = load_rules(args.rules)
    cfg = ccfg.load(args.config)
    print(f"rules   {rules.path}")
    print(f"config  {cfg.path}")
    print(f"output  {cfg.output_dir}")
    print(f"paper {rules.paper}  max pages {rules.max_pages}  "
          f"columns {rules.d['document']['layout']['columns']}")
    print(f"forbidden content: {len(rules.forbidden)} rules")
    print(f"EN-CA substitutions: "
          f"{len(rules.d['language']['en_ca']['substitute'])}")
    print(f"checks: {len(rules.d['checks'])}")
    print(f"location {cfg.location_mode}  work authorization {cfg.auth_mode}  "
          f"credential {cfg.credential_mode}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m canada_module",
        description="Canada Resume Studio — Canadian-format resumes.")
    ap.add_argument("--version", action="version", version=__version__)
    ap.add_argument("--rules", default=None, help="override canada_rules.yaml")
    ap.add_argument("--config", default=None, help="override canada.toml")
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("check", help="lint a resume against the Canada rules")
    c.add_argument("target", nargs="?", help="a .pdf or a .cv.json")
    c.add_argument("--role", choices=sorted(ROLE_FILES),
                   help="lint a role CV straight from the library")
    c.add_argument("--lang", choices=("en", "fr_qc"), default=None,
                   help="default: detected from the text")
    c.add_argument("--json", action="store_true")
    c.set_defaults(fn=cmd_check)

    v = sub.add_parser("convert",
                       help="build a Canadian resume from a structured source")
    v.add_argument("target", nargs="?", help="a .cv.json")
    v.add_argument("--role", choices=sorted(ROLE_FILES),
                   help="convert a role CV from the library")
    v.add_argument("--lang", choices=("en", "fr_qc"), default=None,
                   help="default: [defaults] lang in canada.toml")
    v.add_argument("--out", default=None, help="override the output folder")
    v.add_argument("--no-render", action="store_true",
                   help="write the document and the changelog, skip Chrome")
    v.set_defaults(fn=cmd_convert)

    s = sub.add_parser("tailor",
                       help="tailor a Canadian resume to one job posting")
    s.add_argument("jd", help="a file with the posting text, or - for stdin")
    s.add_argument("--company", default="", help="for the output filename")
    s.add_argument("--city", default="",
                   help='target, e.g. "Toronto, ON" or "Montreal, QC"')
    s.add_argument("--role", choices=sorted(ROLE_FILES),
                   help="override the detected role")
    s.add_argument("--lang", choices=("en", "fr_qc"), default=None,
                   help="override the detected language")
    s.add_argument("--out", default=None)
    s.add_argument("--no-bullets", action="store_true",
                   help="leave bullet order exactly as written")
    s.add_argument("--no-render", action="store_true")
    s.set_defaults(fn=cmd_tailor)

    r = sub.add_parser("rules", help="show the loaded rules and config")
    r.set_defaults(fn=cmd_rules)

    args = ap.parse_args(argv)
    try:
        return args.fn(args)
    except RulesError as e:
        print(f"rules error: {e}", file=sys.stderr)
        return 2
    except ccfg.ConfigError as e:
        print(f"config error: {e}", file=sys.stderr)
        return 2
    except LibraryMissing as e:
        print(f"{e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
