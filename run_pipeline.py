#!/usr/bin/env python3
"""One full pipeline cycle — what the scheduler runs every 45 minutes.

  python run_pipeline.py              fetch -> route -> tailor -> export
  python run_pipeline.py --dry-run    rehearse routing; fetch, but write nothing else
  python run_pipeline.py --no-fetch   route what is already sourced

Submission is deliberately not part of the cycle: it needs you at the screen.
When something is staged or waiting for review, a desktop notification says so.
"""
from __future__ import annotations

import argparse
import json
import sys

import cvrouter as cr
from pipeline import config as pc
from pipeline import fetch as F
from pipeline import orchestrate as O
from pipeline import tailor as T
from pipeline import tracker as TR
from pipeline.db import DB, run_lock


def cycle(*, dry: bool = False, do_fetch: bool = True, boards: int | None = None,
          max_matches: int | None = None, log=print) -> dict:
    pcfg, cfg = pc.load(), cr.load_config()
    db = DB(pcfg.db)
    out: dict = {}
    with run_lock(pcfg.lock_file):
        if do_fetch:
            log("fetch")
            out["fetch"] = F.fetch(db, pcfg, log=log,
                                   max_boards=pcfg.boards_per_run if boards is None else boards)
        log("route")
        out["route"] = O.route(db, pcfg, cfg, dry=dry, log=log, max_matches=max_matches)
        if dry:
            return out

        tailored, failed = 0, 0
        if pcfg.tailor_enabled:
            ids = T.pending_jobs(db)
            if ids:
                log("tailor")
            for jid in ids:
                try:
                    T.tailor_job(db, pcfg, cfg, jid, log=log)
                    tailored += 1
                except (T.TailorError, cr.AIError) as e:
                    failed += 1
                    log(f"  !! {jid}: {e}")
        out["tailor"] = {"tailored": tailored, "failed": failed}

        TR.export(db, pcfg.tracker_xlsx)
        n = dict(db.q("SELECT status, COUNT(*) FROM applications "
                      "WHERE status IN ('draft','staged','review') GROUP BY status"))
        draft, staged, review = n.get("draft", 0), n.get("staged", 0), n.get("review", 0)
        out["waiting"] = {"draft": draft, "staged": staged, "review": review}
        if tailored or out["route"].get("review"):  # drafts or reviews wait for you
            cr.notify(cfg, "filed", "cv-router: candidatures prêtes",
                      f"{draft} CV à relire · {staged} à soumettre · {review} en revue\n"
                      f"http://127.0.0.1:{cfg.port}/pipeline")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-fetch", action="store_true")
    ap.add_argument("--boards", type=int, default=None, help="boards to fetch this run")
    ap.add_argument("--max-matches", type=int, default=None)
    args = ap.parse_args()
    try:
        out = cycle(dry=args.dry_run, do_fetch=not args.no_fetch,
                    boards=args.boards, max_matches=args.max_matches)
    except RuntimeError as e:          # another run holds the lock
        print(e, file=sys.stderr)
        return 1
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
