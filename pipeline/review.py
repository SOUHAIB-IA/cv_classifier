#!/usr/bin/env python3
"""Review queue — jobs scored between the review and auto thresholds.

  python -m pipeline.review                  walk the queue interactively
  python -m pipeline.review --list           just list it
  python -m pipeline.review approve <job_id> send it to tailoring
  python -m pipeline.review skip <job_id>    drop it

Approved jobs become 'pending' and are tailored on the next pipeline run (or
right away with: python -m pipeline.tailor --pending).
"""
from __future__ import annotations

import argparse
import json
import sys
import textwrap

from . import config as pc
from .db import DB


def queue(db: DB) -> list:
    return db.q("SELECT a.*, j.title, j.location, j.apply_url, m.raw "
                "FROM applications a JOIN jobs j ON j.id=a.job_id "
                "LEFT JOIN matches m ON m.job_id=a.job_id "
                "WHERE a.status='review' ORDER BY a.fit_score DESC")


def decide(db: DB, job_id: str, approve: bool, note: str = "") -> None:
    row = db.one("SELECT status FROM applications WHERE job_id=?", job_id)
    if not row:
        raise SystemExit(f"unknown job {job_id}")
    if row["status"] != "review":
        raise SystemExit(f"{job_id} is '{row['status']}', not in the review queue")
    with db.tx():
        db.upsert_application(job_id, status="pending" if approve else "skipped",
                              decision="review",
                              notes=(note or ("approved in review" if approve
                                              else "skipped in review")))
        db.event("review", job_id, approved=approve, note=note)


def show(r) -> None:
    raw = json.loads(r["raw"]) if r["raw"] else {}
    print(f"\n{'─' * 72}\nfit {r['fit_score']}  ·  {r['company']} — {r['title']}")
    print(f"{r['location'] or ''}   {r['apply_url']}")
    print(f"CV: {r['cv_variant']}")
    for line in textwrap.wrap(raw.get("fit_reason", "") or r["notes"] or "", 70):
        print(f"  {line}")
    miss = raw.get("missing_keywords") or []
    if miss:
        print(f"  missing: {', '.join(miss[:8])}")
    for f in (raw.get("red_flags") or [])[:3]:
        print(f"  ! {f}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("action", nargs="?", choices=["approve", "skip"])
    ap.add_argument("job_id", nargs="?")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()
    db = DB(pc.load().db)

    if args.action:
        if not args.job_id:
            ap.error("approve/skip need a job_id")
        decide(db, args.job_id, args.action == "approve")
        print(f"{args.job_id}: {args.action}d")
        return 0

    rows = queue(db)
    if args.list or not sys.stdin.isatty():
        for r in rows:
            print(f"  fit {r['fit_score']:3d}  {r['company'][:16]:16s} "
                  f"{r['title'][:44]:44s} {r['job_id']}")
        print(f"{len(rows)} in review")
        return 0

    if not rows:
        print("review queue is empty")
        return 0
    for r in rows:
        show(r)
        ans = input("  [a]pprove / [s]kip / [l]ater / [q]uit: ").strip().lower()[:1]
        if ans == "q":
            break
        if ans in ("a", "s"):
            decide(db, r["job_id"], ans == "a")
            print("  -> " + ("approved" if ans == "a" else "skipped"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
