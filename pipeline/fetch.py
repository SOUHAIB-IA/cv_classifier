#!/usr/bin/env python3
"""Job Sourcing Service — pull postings from the configured company boards.

  python -m pipeline.fetch                  fetch the boards that are due
  python -m pipeline.fetch --max-boards 8   at most 8 boards this run
  python -m pipeline.fetch --force          ignore the per-board interval
  python -m pipeline.fetch --probe mistral  which ATS hosts this company?
  python -m pipeline.fetch --manual job.txt --company Acme --title "ML Engineer" \\
                           --url https://...  add a posting by hand (LinkedIn etc.)

Load is spread out on purpose: each board is re-fetched at most every
board_min_interval_minutes, a run takes the boards that have waited longest,
and there is a pause between boards.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

import matcher

from . import config as pc
from . import sources
from .db import DB, now


def parse_board(spec: str) -> tuple[str, str]:
    slug, _, name = spec.partition("=")
    return slug.strip(), name.strip()


def due_boards(db: DB, cfg: pc.PipelineConfig, force: bool) -> list[tuple[str, str, str]]:
    """(source, slug, display name), oldest-fetched first."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=cfg.board_min_interval_min)
    out = []
    for source, specs in cfg.boards.items():
        if source not in sources.ADAPTERS:
            continue
        for spec in specs:
            slug, name = parse_board(spec)
            row = db.one("SELECT last_fetched FROM boards WHERE source=? AND board=?",
                         source, slug)
            last = row["last_fetched"] if row and row["last_fetched"] else ""
            if not force and last and datetime.fromisoformat(last) > cutoff:
                continue
            out.append((last, source, slug, name))
    out.sort()   # never-fetched ("") first, then oldest
    return [(s, b, n) for _, s, b, n in out]


def fetch(db: DB, cfg: pc.PipelineConfig, *, max_boards: int = 0,
          force: bool = False, log=print) -> dict:
    todo = due_boards(db, cfg, force)
    if max_boards:
        todo = todo[:max_boards]
    stats = {"boards": 0, "fetched": 0, "new": 0, "errors": 0}
    with sources.client(cfg.http_timeout) as c:
        for i, (source, slug, name) in enumerate(todo):
            if i:
                time.sleep(cfg.request_delay)
            err, jobs = "", []
            try:
                jobs = sources.ADAPTERS[source](c, slug)
            except httpx.HTTPStatusError as e:
                err = f"HTTP {e.response.status_code}"
            except Exception as e:
                err = f"{type(e).__name__}: {e}"[:200]
            new = 0
            with db.tx():
                for j in jobs:
                    if name:
                        j["company"] = name
                    new += db.upsert_job(j)
                db.conn.execute(
                    "INSERT INTO boards(source, board, last_fetched, last_error, n_jobs)"
                    " VALUES (?,?,?,?,?) ON CONFLICT(source, board) DO UPDATE SET"
                    " last_fetched=excluded.last_fetched, last_error=excluded.last_error,"
                    " n_jobs=excluded.n_jobs",
                    (source, slug, now(), err, len(jobs)))
                db.event("source", None, source=source, board=slug,
                         fetched=len(jobs), new=new, error=err)
            stats["boards"] += 1
            stats["fetched"] += len(jobs)
            stats["new"] += new
            stats["errors"] += bool(err)
            log(f"  {source:10s} {slug:16s} {len(jobs):4d} postings, {new:3d} new"
                + (f"  !! {err}" if err else ""))
    return stats


def add_manual(db: DB, text: str, *, company: str, title: str, url: str = "",
               location: str = "") -> str:
    """A posting you paste in yourself — LinkedIn, Indeed, a recruiter's email."""
    sid = hashlib.sha1(f"{company}|{title}|{url}|{text[:500]}".encode()).hexdigest()[:16]
    job = {
        "id": f"manual:{sid}", "source": "manual", "board": "", "company": company,
        "title": title, "location": location, "jd_text": text.strip(),
        "apply_url": url, "jd_url": url,
        "language": matcher.guess_language(f"{title}\n{text}"),
        "posted_date": datetime.now().date().isoformat(),
    }
    with db.tx():
        db.upsert_job(job)
        db.event("source", job["id"], source="manual")
    return job["id"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-boards", type=int, default=0)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--probe", metavar="SLUG")
    ap.add_argument("--manual", type=Path, metavar="FILE")
    ap.add_argument("--company", default="")
    ap.add_argument("--title", default="")
    ap.add_argument("--url", default="")
    ap.add_argument("--location", default="")
    args = ap.parse_args()

    if args.probe:
        for src, n in sources.probe(args.probe).items():
            print(f"  {src:10s} {n}")
        return 0

    cfg = pc.load()
    db = DB(cfg.db)
    if args.manual:
        if not (args.company and args.title):
            print("--manual needs --company and --title", file=sys.stderr)
            return 2
        jid = add_manual(db, args.manual.read_text(), company=args.company,
                         title=args.title, url=args.url, location=args.location)
        print(f"added {jid}")
        return 0

    s = fetch(db, cfg, max_boards=args.max_boards, force=args.force)
    print(f"{s['boards']} boards, {s['fetched']} postings, {s['new']} new, "
          f"{s['errors']} errors")
    return 0


if __name__ == "__main__":
    sys.exit(main())
