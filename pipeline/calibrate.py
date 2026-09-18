#!/usr/bin/env python3
"""Calibrate the fit-score thresholds against your own judgement.

  python -m pipeline.calibrate label     judge evaluated jobs yourself
  python -m pipeline.calibrate report    how well each threshold pair agrees

The spec asks for 10-15 jobs judged by hand before the auto path is trusted.
You label a job apply / maybe / no; this finds the auto and review thresholds
that best reproduce your labels (apply -> auto, maybe -> review, no -> skip),
and shows how the current ones compare. The fit score is only useful if it
ranks jobs the way you would.
"""
from __future__ import annotations

import argparse
import json
import sys
import textwrap

from . import config as pc
from .db import DB, now

SCHEMA = """CREATE TABLE IF NOT EXISTS labels (
  job_id  TEXT PRIMARY KEY REFERENCES jobs(id),
  verdict TEXT NOT NULL,           -- apply | maybe | no
  ts      TEXT NOT NULL
)"""
WANT = {"apply": "auto", "maybe": "review", "no": "skip"}


def _decide(fit: int, auto: int, review: int) -> str:
    return "auto" if fit >= auto else "review" if fit >= review else "skip"


def best_thresholds(pairs: list[tuple[int, str]]) -> list[tuple[float, int, int, int]]:
    """Every (auto, review) pair scored by agreement with your labels.

    Ties are broken towards a HIGHER auto threshold: when two settings agree
    equally, prefer the one that sends fewer applications out unreviewed.
    """
    out = []
    for auto in range(50, 96, 5):
        for review in range(20, auto, 5):
            ok = sum(_decide(f, auto, review) == WANT[v] for f, v in pairs)
            # 'apply' judged as skip is the costly miss; count those apart
            lost = sum(1 for f, v in pairs if v == "apply" and _decide(f, auto, review) == "skip")
            out.append((ok / len(pairs), -lost, auto, review))
    out.sort(key=lambda x: (x[0], x[1], x[2]), reverse=True)
    return out


def label(db: DB) -> None:
    rows = db.q("SELECT j.id, j.company, j.title, j.location, m.fit_score, m.raw "
                "FROM matches m JOIN jobs j ON j.id=m.job_id "
                "WHERE j.id NOT IN (SELECT job_id FROM labels) "
                "ORDER BY m.created_at")
    if not rows:
        print("no evaluated job left to label")
        return
    print("For each job: would YOU apply? Judge the job, not the score (hidden).")
    for r in rows:
        raw = json.loads(r["raw"] or "{}")
        print(f"\n{'─' * 72}\n{r['company']} — {r['title']}   [{r['location'] or ''}]")
        for line in textwrap.wrap(raw.get("best", {}).get("why", ""), 70)[:3]:
            print(f"  {line}")
        ans = input("  [a]pply / [m]aybe / [n]o / [s]kip / [q]uit: ").strip().lower()[:1]
        if ans == "q":
            break
        v = {"a": "apply", "m": "maybe", "n": "no"}.get(ans)
        if v:
            with db.tx():
                db.conn.execute("INSERT OR REPLACE INTO labels VALUES (?,?,?)",
                                (r["id"], v, now()))


def report(db: DB, pcfg: pc.PipelineConfig) -> None:
    pairs = [(r["fit_score"], r["verdict"]) for r in db.q(
        "SELECT m.fit_score, l.verdict FROM labels l JOIN matches m ON m.job_id=l.job_id")]
    n = len(pairs)
    print(f"{n} labelled job(s)" + ("" if n >= 10 else " — the spec asks for 10-15 "
                                     "before trusting the auto path"))
    if not n:
        return
    for v in ("apply", "maybe", "no"):
        fits = sorted(f for f, lv in pairs if lv == v)
        if fits:
            print(f"  {v:6s} n={len(fits):2d}  fit {fits[0]}-{fits[-1]}  "
                  f"median {fits[len(fits) // 2]}")
    cur = sum(_decide(f, pcfg.threshold_auto, pcfg.threshold_review) == WANT[v]
              for f, v in pairs) / n
    ranked = best_thresholds(pairs)
    agree, lost, a, r = ranked[0]
    print(f"\n  current  auto>={pcfg.threshold_auto} review>={pcfg.threshold_review}"
          f"   agreement {cur:.0%}")
    print(f"  best     auto>={a} review>={r}   agreement {agree:.0%}"
          + (f", {-lost} 'apply' job(s) would be skipped" if lost else ""))
    if (a, r) != (pcfg.threshold_auto, pcfg.threshold_review) and agree > cur:
        print(f"\n  To adopt it, set in pipeline.toml [thresholds]: auto = {a}, review = {r}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["label", "report"])
    args = ap.parse_args()
    pcfg = pc.load()
    db = DB(pcfg.db)
    db.conn.execute(SCHEMA)
    if args.cmd == "label":
        if not sys.stdin.isatty():
            print("labelling needs an interactive terminal", file=sys.stderr)
            return 2
        label(db)
    report(db, pcfg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
