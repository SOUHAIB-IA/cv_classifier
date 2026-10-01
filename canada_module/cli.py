"""The studio's own entry point.

    python -m canada_module check <pdf|cv.json> [--lang en|fr_qc] [--json]
    python -m canada_module check --role de --lang en        # from the library
    python -m canada_module rules                            # show what loaded

Independent of run_pipeline.py on purpose: nothing here starts the pipeline,
and the pipeline never calls into here.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__, config as ccfg
from .checker import check_doc, check_pdf
from .rules import RulesError, load_rules

ROOT = Path(__file__).resolve().parent.parent

# The six role CVs, by the slug used in their filenames.
ROLE_FILES = {"ai": "AI_Engineer", "mlops": "MLOps", "devops": "DevOps",
              "ds": "Data_Scientist", "de": "Data_Engineer",
              "swe": "Software_Engineer"}


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
        raise SystemExit(f"no {stem}.pdf under {cfg.cv_root}")
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


if __name__ == "__main__":
    raise SystemExit(main())
