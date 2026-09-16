#!/usr/bin/env python3
"""Build or refresh the index of the existing CV collection.

  python indexer.py                index anything new or changed
  python indexer.py --rebuild      re-read everything from scratch
  python indexer.py --no-ai        folder names + headline only, no model calls
  python indexer.py --workers 1    serial, if parallel calls trip a usage limit

The index is what the portal matches a job description against, so it needs to
exist before the portal is useful. Incremental by default: a CV whose content
signature is unchanged is not sent to the model again.

Model calls are independent and dominated by waiting, so they run in a pool.
Progress is committed as results arrive, which keeps a run resumable.
"""
from __future__ import annotations

import argparse
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import cvrouter as cr

SUMMARY_SYSTEM = """You read one CV and return ONLY a JSON object describing it,
no prose. Fields:
  summary  one sentence, max 22 words, on what role this CV is pitching and its
           strongest evidence for it.
  skills   up to 20 concrete technologies actually named in the CV.
  lang     "FR" or "EN".
  headline the tagline under the name, verbatim; "" if absent.
"""


def branch_and_specialty(rel: Path, branches: dict, roles: dict) -> tuple[str, str]:
    parts = rel.parts
    branch = parts[0] if parts and parts[0] in branches else ""
    specialty = next((p for p in parts if p in roles), "")
    return branch, specialty


def build_record(cfg: cr.Config, path: Path, text: str, sig: str) -> cr.CVRecord:
    """Everything derivable without the model."""
    rel = str(path.relative_to(cfg.cv_root))
    branch, specialty = branch_and_specialty(Path(rel), cfg.branches, cfg.roles)
    rec = cr.CVRecord(
        path=rel,
        branch=branch,
        specialty=specialty,
        role=cfg.roles.get(specialty, ""),
        headline=cr.headline_of(text, cr._junk_re(cfg.headline_noise)),
        sig=sig,
        mtime=path.stat().st_mtime,
    )
    rec.lang = "FR" if "Francais" in rel else ("EN" if "English" in rel else "")
    if not rec.lang:
        rec.lang = "FR" if path.name.endswith("_FR.pdf") or "_FR_" in path.name else "EN"
    return rec


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rebuild", action="store_true")
    ap.add_argument("--no-ai", action="store_true")
    ap.add_argument("--limit", type=int, default=0,
                    help="stop after N model calls (resume later; progress is saved)")
    ap.add_argument("--sleep", type=float, default=0.0,
                    help="seconds between calls per worker, to ease usage limits")
    ap.add_argument("--workers", type=int, default=0,
                    help="parallel model calls (default: ai.index_workers)")
    ap.add_argument("--config", type=Path, default=None)
    args = ap.parse_args()

    cfg = cr.load_config(args.config)
    log = cr.setup_logging(cfg, "indexer")
    idx = cr.Index(cfg)
    if args.rebuild:
        idx.records.clear()

    paths = idx.pdf_paths()
    log.info("%d PDFs under %s", len(paths), cfg.cv_root)

    # -- pass 1: read every PDF, decide what actually needs a model call ------
    todo: list[tuple[Path, cr.CVRecord, str]] = []
    pending: dict[str, cr.CVRecord] = {}
    skipped = 0

    for p in paths:
        rel = str(p.relative_to(cfg.cv_root))
        text = cr.pdf_text_cached(cfg, p)
        sig = cr.content_sig(text)
        old = idx.records.get(rel)
        if old and old.sig == sig and old.summary:
            skipped += 1
            continue
        rec = build_record(cfg, p, text, sig)
        if args.no_ai:
            rec.summary = rec.headline or rec.specialty.replace("-", " ")
            pending[rel] = rec
        else:
            todo.append((p, rec, text))

    if args.limit:
        todo = todo[:args.limit]

    workers = max(1, args.workers or cfg.index_workers)
    log.info("%d unchanged, %d to index%s", skipped, len(todo),
             "" if args.no_ai else f" with {workers} worker(s)")

    # -- pass 2: the model calls, in parallel --------------------------------
    failed = 0
    give_up = threading.Event()   # set once the backend is plainly unavailable

    def summarise(item):
        p, rec, text = item
        if give_up.is_set():
            return rec, None
        if args.sleep:
            time.sleep(args.sleep)
        try:
            out = cr.ask_json(cfg, SUMMARY_SYSTEM,
                              f"--- CV TEXT ---\n{text[:14000]}", max_tokens=900)
            return rec, out
        except cr.AIError as e:
            # No key, no binary, usage limit — every other call will fail too.
            give_up.set()
            log.error("AI unavailable: %s", e)
            return rec, None
        except Exception as e:
            log.warning("summary failed for %s: %s", rec.path, e)
            return rec, None

    if todo:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(summarise, it) for it in todo]
            for n, fut in enumerate(as_completed(futures), start=1):
                rec, out = fut.result()
                if out:
                    rec.summary = out.get("summary", "")
                    rec.skills = list(out.get("skills") or [])[:20]
                    rec.lang = (out.get("lang") or rec.lang).upper()
                    rec.headline = out.get("headline") or rec.headline
                else:
                    failed += 1
                if not rec.summary:
                    rec.summary = rec.headline or rec.specialty.replace("-", " ")
                pending[rec.path] = rec
                if n % 10 == 0:
                    idx.commit(upserts=pending)   # merge, don't overwrite
                    pending.clear()
                    log.info("  %d/%d…", n, len(todo))

    # Prune only after a full pass: --limit stops early, so it has not seen
    # every CV. prune checks each entry against the filesystem, so a CV the
    # watcher filed mid-run survives.
    full_pass = not args.limit and not give_up.is_set()
    idx.commit(upserts=pending, prune=full_pass)

    dropped = cr.prune_text_cache(cfg)
    log.info("indexed=%d unchanged=%d failed=%d total=%d (text cache: -%d) -> %s",
             len(todo) - failed, skipped, failed, len(idx.records), dropped,
             cfg.index_file)
    if give_up.is_set():
        log.error("stopped early: the model backend was unavailable. "
                  "Re-run to continue where this left off.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
