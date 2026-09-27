#!/usr/bin/env python3
"""Orchestrator — route every sourced job to auto, review or skip.

  python -m pipeline.orchestrate                  one routing pass
  python -m pipeline.orchestrate --max-matches 2  evaluate at most 2 jobs
  python -m pipeline.orchestrate --dry-run        decide and print, write nothing

Stages a job moves through (jobs.stage):

  sourced -> filtered                 failed a hard filter; never a candidate
          -> candidate                passed; has a pre-screen score
               -> skipped             pre-screen too low, or a duplicate
               -> matched             evaluated by cv-router
                    -> auto | review | skip   by fit_score thresholds

Every step is committed before the next starts, so a crashed run resumes where
it stopped. The model-call budget is charged BEFORE the call: a job that keeps
crashing mid-evaluation cannot burn the quota by being retried forever, and
after MAX_ATTEMPTS it is parked as an error.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys

import cvrouter as cr
import matcher

from . import config as pc
from .db import DB, run_lock
from .prefilter import Screener

MAX_ATTEMPTS = 2


def decide(fit: int, pcfg: pc.PipelineConfig) -> str:
    if fit >= pcfg.threshold_auto:
        return "auto"
    if fit >= pcfg.threshold_review:
        return "review"
    return "skip"


def _variant_label(path: str) -> str:
    """'2-.../AI-ML-Engineering/Souhaib-GARAAOUCH_AI-ML-Engineer_MLOps-LLM_EN.pdf'
    -> 'AI-ML-Engineer_MLOps-LLM'  (the part a human recognises)."""
    stem = path.rsplit("/", 1)[-1].removesuffix(".pdf")
    parts = stem.split("_")
    if len(parts) >= 3:
        parts = parts[1:]                       # drop the owner prefix
    while parts and (parts[-1] in ("FR", "EN") or parts[-1].isdigit()):
        parts = parts[:-1]                      # drop _FR / _EN / _2 suffixes
    return "_".join(parts) or stem


# ------------------------------------------------------------------- stages --
def prefilter_sig(pcfg: pc.PipelineConfig) -> str:
    """A fingerprint of everything the free screen decides on."""
    parts = [sorted(pcfg.title_include), sorted(pcfg.title_exclude),
             sorted(pcfg.location_include), sorted(pcfg.location_exclude),
             sorted(pcfg.languages), pcfg.max_age_days, pcfg.max_years_required,
             sorted(pcfg.work_authorization or []), pcfg.prefilter_min]
    return hashlib.sha256(
        json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()[:16]


def screen(db: DB, pcfg: pc.PipelineConfig, scr: Screener, *, dry: bool = False,
           log=print) -> dict:
    """sourced -> filtered | candidate. Free: no model calls.

    Waiting candidates are re-screened every run, so tightening a filter takes
    effect on the queue and not only on tomorrow's postings.

    Loosening one used to do nothing at all: a posting already marked filtered
    was never looked at again, so widening a location list left every earlier
    posting it would now accept stranded. When the filters change, the dropped
    ones are therefore reconsidered too. It costs nothing but CPU, which is why
    it can simply happen rather than being a button someone has to know about.
    """
    stats = {"filtered": 0, "candidates": 0, "reconsidered": 0}
    sig = prefilter_sig(pcfg)
    # No signature at all means a database screened before this existed: its
    # dropped postings were judged by filters nobody recorded, so they get the
    # one pass they never had.
    changed = db.get_meta("prefilter_sig") != sig
    stages = ("sourced", "candidate", "filtered") if changed else ("sourced", "candidate")
    revived: list[str] = []
    if changed:
        stats["reconsidered"] = db.one(
            "SELECT COUNT(*) FROM jobs WHERE stage='filtered'")[0]
        # A posting dropped for scoring under prefilter_min is stage=skipped, not
        # filtered, and carries an application row saying so. Lowering the floor
        # has to reach those too, or the setting only ever works one way. The row
        # recorded an automatic screening outcome and no decision of yours, so it
        # goes; rows you acted on say something else and are never matched here.
        revived = [r[0] for r in db.q(
            "SELECT j.id FROM jobs j JOIN applications a ON a.job_id = j.id "
            "WHERE j.stage = 'skipped' AND a.status = 'skipped' "
            "AND a.notes LIKE 'pre-screen %'")]
        if revived and not dry:
            with db.tx():
                db.conn.executemany("DELETE FROM applications WHERE job_id=?",
                                    [(i,) for i in revived])
        stats["reconsidered"] += len(revived)
        log(f"  filters changed: reconsidering {stats['reconsidered']} postings "
            f"dropped under the old ones"
            + (f", {len(revived)} of them dropped on their pre-screen score"
               if revived else ""))
    marks = ",".join("?" * len(stages))
    ids = ",".join("?" * len(revived))
    rows = db.q(
        f"SELECT * FROM jobs WHERE stage IN ({marks})"
        + (f" OR id IN ({ids})" if revived else ""), *stages, *revived)
    with db.tx():
        for r in rows:
            job = dict(r)
            ok, why = scr.hard_filter(job)
            if not ok:
                stats["filtered"] += 1
                if not dry:
                    db.set_stage(job["id"], "filtered", status="processed")
                    db.event("prefilter", job["id"], passed=False, reason=why)
                continue
            score, hits = scr.score(job)
            stats["candidates"] += 1
            if not dry:
                db.set_stage(job["id"], "candidate", prefilter_score=score)
                db.event("prefilter", job["id"], passed=True, score=score,
                         skills=hits[:12])
        if not dry:
            db.set_meta("prefilter_sig", sig)
    return stats


def _location_rank(scr: Screener, loc: str) -> int:
    """Lower is better: the position, in location_include, of the first term the
    posting's location matches. location_include is therefore also a
    preference order."""
    best = 10_000
    places, _ = scr.places(loc or "")
    for place in places:
        for i, term in enumerate(scr.p.location_include):
            if scr._any([term], place):
                best = min(best, i)
                break
    return best


def triage(db: DB, pcfg: pc.PipelineConfig, scr: Screener | None = None, *,
           dup_window_days: int = 120, log=print) -> dict:
    """Candidates that do not earn an evaluation.

    - the same role posted several times (Cohere lists one role per region):
      keep the posting in the best-ranked location, skip its twins. Without
      this, one role eats several evaluations from the daily budget.
    - a role already on file: an active application forever (the spec's
      duplicate guard — never apply twice), any other decision within
      dup_window_days (same ad, same verdict).
    - a pre-screen score under prefilter_min.
    """
    stats = {"low_prescreen": 0, "duplicate": 0, "regional_twin": 0, "company_cap": 0}
    rows = [dict(r) for r in db.q("SELECT * FROM jobs WHERE stage='candidate'")]

    # Applying to many roles at one company in a few days is read as spraying by
    # the ATS, and it is the applicant who gets flagged. The cap counts what is
    # already live there and keeps the best-scoring candidates within it.
    if pcfg.max_per_company:
        live = dict(db.q(
            "SELECT company, COUNT(*) FROM applications WHERE status IN "
            "('pending','draft','staged','applied','interview','offer') GROUP BY company"))
        rows.sort(key=lambda r: -(r["prefilter_score"] or 0))
        keep = []
        with db.tx():
            for r in rows:
                n = live.get(r["company"], 0)
                if n >= pcfg.max_per_company:
                    stats["company_cap"] += 1
                    db.set_stage(r["id"], "skipped", status="processed")
                    db.upsert_application(
                        r["id"], decision="skip", status="skipped",
                        notes=f"company cap: {n} already live at {r['company']}")
                    continue
                live[r["company"]] = n + 1
                keep.append(r)
        rows = keep

    groups: dict[str, list[dict]] = {}
    for r in rows:
        groups.setdefault(r["dedupe_key"], []).append(r)

    with db.tx():
        for dkey, members in groups.items():
            prior = db.already_applied(dkey) or db.one(
                "SELECT * FROM applications WHERE dedupe_key=? AND decision<>'' "
                "AND date >= date('now', ?) ORDER BY updated_at DESC LIMIT 1",
                dkey, f"-{dup_window_days} days")
            if prior:
                for r in members:
                    stats["duplicate"] += 1
                    db.set_stage(r["id"], "skipped", status="processed")
                    db.upsert_application(
                        r["id"], decision="skip", status="skipped",
                        notes=f"duplicate of {prior['company']} / {prior['role']} "
                              f"({prior['status']}, {prior['job_id']})")
                continue

            if len(members) > 1:
                if scr:
                    members.sort(key=lambda r: (_location_rank(scr, r["location"]),
                                                -(r["prefilter_score"] or 0),
                                                r["first_seen"]))
                keep, twins = members[0], members[1:]
                for r in twins:
                    stats["regional_twin"] += 1
                    db.set_stage(r["id"], "skipped", status="processed")
                    db.upsert_application(
                        r["id"], decision="skip", status="skipped",
                        notes=f"same role posted for several locations; kept "
                              f"'{keep['location']}' ({keep['id']})")
                members = [keep]

            r = members[0]
            if (r["prefilter_score"] or 0) < pcfg.prefilter_min:
                stats["low_prescreen"] += 1
                db.set_stage(r["id"], "skipped", status="processed")
                db.upsert_application(
                    r["id"], decision="skip", status="skipped",
                    notes=f"pre-screen {r['prefilter_score']:.2f} "
                          f"< {pcfg.prefilter_min:.2f}")
    return stats


def evaluate(db: DB, pcfg: pc.PipelineConfig, cfg: cr.Config, *,
             max_matches: int, dry: bool = False, log=print,
             match_fn=None) -> dict:
    """candidate -> matched, through cv-router, within the daily budget.

    Best pre-screen first, so a limited budget goes to the likeliest fits.
    """
    match_fn = match_fn or matcher.match_job
    stats = {"evaluated": 0, "auto": 0, "review": 0, "skip": 0, "errors": 0,
             "budget_left": 0, "waiting": 0}
    left = max(0, pcfg.daily_match_budget - db.matches_today())
    n = min(max_matches, left)
    queue = db.q("SELECT * FROM jobs WHERE stage='candidate' "
                 "ORDER BY prefilter_score DESC, first_seen ASC")
    stats["waiting"] = max(0, len(queue) - n)
    idx = cr.Index(cfg)

    for r in queue[:n]:
        job = dict(r)
        attempts = db.one("SELECT COUNT(*) FROM events WHERE kind='match' AND job_id=?",
                          job["id"])[0]
        if attempts >= MAX_ATTEMPTS:
            if not dry:
                with db.tx():
                    db.set_stage(job["id"], "error", status="processed")
                    db.event("error", job["id"], reason=f"{attempts} failed evaluations")
            continue

        if dry:
            log(f"  would evaluate {job['company']} — {job['title']} "
                f"(pre-screen {job['prefilter_score']:.2f})")
            continue

        try:
            decision, fit, variant = evaluate_job(db, pcfg, cfg, job, idx=idx,
                                                  match_fn=match_fn)
        except cr.AIError as e:
            log(f"  !! model unavailable, stopping evaluation: {e}")
            stats["errors"] += 1
            break
        except Exception as e:
            log(f"  !! {job['company']} — {job['title']}: {e}")
            stats["errors"] += 1
            continue
        stats["evaluated"] += 1
        stats[decision] += 1
        log(f"  {decision:6s} fit {fit:3d}  {job['company'][:16]:16s} "
            f"{job['title'][:46]:46s}  -> {_variant_label(variant)}")

    stats["budget_left"] = max(0, pcfg.daily_match_budget - db.matches_today())
    return stats


def evaluate_job(db: DB, pcfg: pc.PipelineConfig, cfg: cr.Config, job: dict, *,
                 idx: cr.Index | None = None, match_fn=None) -> tuple[str, int, str]:
    """Send ONE job through cv-router and record the verdict.
    Returns (decision, fit_score, chosen CV). Charges the budget first."""
    match_fn = match_fn or matcher.match_job
    db.event("match", job["id"], prefilter=job.get("prefilter_score"))
    try:
        res = match_fn(cfg, job["jd_text"], title=job["title"], company=job["company"],
                       location=job.get("location") or "", idx=idx or cr.Index(cfg))
    except Exception as e:
        db.event("error", job["id"], reason=f"{type(e).__name__}: {e}"[:300])
        raise
    fit = int(res["fit_score"])
    decision = decide(fit, pcfg)
    lang = res.get("job_language") or job.get("language") or "en"
    variant = res["best_variant"]
    with db.tx():
        db.save_match(job["id"], {
            "fit_score": fit, "ats_score": res.get("ats_score"),
            "recommended_variant": variant, "recommended_account": lang,
            "suggested_edits": res.get("suggested_edits", []),
            "decision": decision, "reason": res.get("fit_reason", ""), "raw": res,
        })
        db.set_stage(job["id"], decision if decision != "skip" else "skipped",
                     status="processed", language=lang)
        db.upsert_application(
            job["id"], decision=decision, fit_score=fit, language=lang, account=lang,
            cv_variant=_variant_label(variant),
            status={"auto": "pending", "review": "review", "skip": "skipped"}[decision],
            notes=res.get("fit_reason", "")[:500])
        db.event("route", job["id"], decision=decision, fit=fit,
                 ats=res.get("ats_score"), variant=variant)
    return decision, fit, variant


def route(db: DB, pcfg: pc.PipelineConfig, cfg: cr.Config, *, max_matches=None,
          dry: bool = False, log=print, match_fn=None) -> dict:
    """One routing pass. A dry run rehearses every stage on an in-memory copy of
    the database — so it shows exactly which jobs would be evaluated — and
    stops short of the model calls."""
    if dry:
        db = db.scratch_copy()
    scr = Screener(pcfg, cfg)
    s1 = screen(db, pcfg, scr, log=log)
    s2 = triage(db, pcfg, scr, log=log)
    s3 = evaluate(db, pcfg, cfg, dry=dry, log=log, match_fn=match_fn,
                  max_matches=pcfg.max_matches_per_run if max_matches is None else max_matches)
    return {**s1, **s2, **s3}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-matches", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    pcfg, cfg = pc.load(), cr.load_config()
    db = DB(pcfg.db)
    try:
        with run_lock(pcfg.lock_file):
            s = route(db, pcfg, cfg, max_matches=args.max_matches, dry=args.dry_run)
    except RuntimeError as e:
        print(e, file=sys.stderr)
        return 1
    print(json.dumps(s))
    return 0


if __name__ == "__main__":
    sys.exit(main())
