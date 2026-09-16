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

_FIELDS = """  summary  one sentence, max 22 words, on what role this CV is pitching
           and its strongest evidence for it.
  skills   up to 20 concrete technologies actually named in the CV.
  lang     "FR" or "EN".
  headline the tagline under the name, verbatim; "" if absent."""

SUMMARY_SYSTEM = f"""You read one CV and return ONLY a JSON object describing it,
no prose. Fields:
{_FIELDS}
"""

# Several CVs per call: the per-call overhead dominates a job this small, so
# batching cuts the call count by the batch size. Each CV carries an id and the
# reply must echo it, so a partial answer can be repaired per item rather than
# costing the whole batch.
BATCH_SYSTEM = f"""You read several CVs and describe each one.

Each CV is introduced by a line "### CV id=N". Return ONLY a JSON object:
{{"results": [{{"id": N, "summary": "...", "skills": ["..."], "lang": "FR|EN",
"headline": "..."}}, ...]}}

One entry per CV given, echoing its id. Fields:
{_FIELDS}

Describe each CV on its own content alone. They are near-identical variants of
one person's CV, so do not let one bleed into another — the small differences
between them are the whole point."""


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
    ap.add_argument("--batch", type=int, default=0,
                    help="CVs per call; 1 disables batching "
                         "(default: ai.index_batch_size)")
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
    calls = 0
    give_up = threading.Event()   # set once the backend is plainly unavailable
    call_lock = threading.Lock()

    def _ask(system: str, user: str, max_tokens: int):
        nonlocal calls
        if args.sleep:
            time.sleep(args.sleep)
        with call_lock:
            calls += 1
        return cr.ask_json(cfg, system, user, max_tokens=max_tokens,
                           model=cfg.index_model)

    def summarise_one(rec, text):
        """One CV, one call. The fallback when a batch comes back incomplete."""
        try:
            return _ask(SUMMARY_SYSTEM, f"--- CV TEXT ---\n{text[:14000]}", 900)
        except cr.AIError:
            raise
        except Exception as e:
            log.warning("summary failed for %s: %s", rec.path, e)
            return None

    def summarise_batch(items):
        """Several CVs, one call. Returns {rec.path: parsed-or-None}."""
        if give_up.is_set():
            return {rec.path: None for _, rec, _ in items}
        out: dict[str, dict | None] = {}
        try:
            if len(items) == 1:
                rec, text = items[0][1], items[0][2]
                out[rec.path] = summarise_one(rec, text)
                return out

            body = "\n\n".join(
                f"### CV id={i}\n{text[:6000]}"
                for i, (_, _, text) in enumerate(items)
            )
            res = _ask(BATCH_SYSTEM, body, 400 * len(items) + 600)
            by_id = {}
            for r in res.get("results", []):
                try:
                    by_id[int(r.get("id"))] = r
                except (TypeError, ValueError):
                    continue

            missing = []
            for i, (_, rec, text) in enumerate(items):
                if i in by_id:
                    out[rec.path] = by_id[i]
                else:
                    missing.append((rec, text))
            # Repair only what the batch dropped, rather than losing all of it.
            if missing:
                log.info("  batch returned %d/%d, retrying the rest singly",
                         len(items) - len(missing), len(items))
                for rec, text in missing:
                    out[rec.path] = summarise_one(rec, text)
        except cr.AIError as e:
            # No key, no binary, usage limit — every other call will fail too.
            give_up.set()
            log.error("AI unavailable: %s", e)
            for _, rec, _ in items:
                out.setdefault(rec.path, None)
        except Exception as e:
            log.warning("batch failed (%s), retrying singly", e)
            for _, rec, text in items:
                try:
                    out[rec.path] = summarise_one(rec, text)
                except cr.AIError as e2:
                    give_up.set()
                    log.error("AI unavailable: %s", e2)
                    out[rec.path] = None
        return out

    if todo:
        size = max(1, args.batch or cfg.index_batch_size)
        batches = [todo[i:i + size] for i in range(0, len(todo), size)]
        recs = {rec.path: rec for _, rec, _ in todo}
        log.info("  %d call(s) of up to %d CVs, %d worker(s), model=%s",
                 len(batches), size, workers, cfg.index_model)

        seen_n = 0
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(summarise_batch, b) for b in batches]
            for fut in as_completed(futures):
                for path, out in fut.result().items():
                    rec = recs[path]
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
                    seen_n += 1
                idx.commit(upserts=pending)   # merge, don't overwrite
                pending.clear()
                log.info("  %d/%d…", seen_n, len(todo))

    # Prune only after a full pass: --limit stops early, so it has not seen
    # every CV. prune checks each entry against the filesystem, so a CV the
    # watcher filed mid-run survives.
    full_pass = not args.limit and not give_up.is_set()
    idx.commit(upserts=pending, prune=full_pass)

    dropped = cr.prune_text_cache(cfg)
    log.info("indexed=%d unchanged=%d failed=%d total=%d "
             "in %d model call(s) (text cache: -%d) -> %s",
             len(todo) - failed, skipped, failed, len(idx.records), calls,
             dropped, cfg.index_file)
    if give_up.is_set():
        log.error("stopped early: the model backend was unavailable. "
                  "Re-run to continue where this left off.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
