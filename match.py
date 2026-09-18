#!/usr/bin/env python3
"""Headless matcher: a job description in, the best CV and its edits out, as JSON.

  python match.py --file job.txt
  pbpaste | python match.py
  python match.py --file job.txt --title "AI Engineer" --company Acme

Same logic as the portal (matcher.match_job), without the UI — this is the
entry point the job pipeline, or any script, can call.
Exit codes: 0 ok, 2 empty input, 3 model backend unavailable.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cvrouter as cr
import matcher


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", type=Path, help="job description file (default: stdin)")
    ap.add_argument("--title", default="")
    ap.add_argument("--company", default="")
    ap.add_argument("--location", default="")
    ap.add_argument("--compact", action="store_true",
                    help="only best_variant, fit_score, ats_score, suggested_edits")
    args = ap.parse_args()

    jd = args.file.read_text() if args.file else sys.stdin.read()
    if not jd.strip():
        print(json.dumps({"error": "empty job description"}))
        return 2

    cfg = cr.load_config()
    try:
        res = matcher.match_job(cfg, jd, title=args.title,
                                company=args.company, location=args.location)
    except cr.AIError as e:
        print(json.dumps({"error": str(e)}))
        return 3

    if args.compact:
        res = {k: res[k] for k in ("best_variant", "fit_score", "ats_score",
                                   "job_language", "suggested_edits")}
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
