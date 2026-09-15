#!/usr/bin/env python3
"""Build or refresh the index of the existing CV collection.

  python indexer.py            index anything new or changed
  python indexer.py --rebuild  re-read everything from scratch
  python indexer.py --no-ai    fill from folder names + headline only (no API cost)

The index is what the portal matches a job description against, so it needs to
exist before the portal is useful. Incremental by default: a CV whose content
signature is unchanged is not sent to the model again.
"""
from __future__ import annotations

import argparse
import sys
import time
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rebuild", action="store_true")
    ap.add_argument("--no-ai", action="store_true")
    ap.add_argument("--limit", type=int, default=0,
                    help="stop after N model calls (resume later; progress is saved)")
    ap.add_argument("--sleep", type=float, default=0.0,
                    help="seconds to wait between calls, to stay under usage limits")
    ap.add_argument("--config", type=Path, default=None)
    args = ap.parse_args()

    cfg = cr.load_config(args.config)
    log = cr.setup_logging(cfg, "indexer")
    idx = cr.Index(cfg)
    if args.rebuild:
        idx.records.clear()

    paths = idx.pdf_paths()
    log.info("%d PDFs under %s", len(paths), cfg.cv_root)

    pending: dict[str, cr.CVRecord] = {}
    done = skipped = failed = 0

    for p in paths:
        rel = str(p.relative_to(cfg.cv_root))
        text = cr.pdf_text(p)
        sig = cr.content_sig(text)
        old = idx.records.get(rel)
        if old and old.sig == sig and old.summary:
            skipped += 1
            continue

        branch, specialty = branch_and_specialty(Path(rel), cfg.branches, cfg.roles)
        rec = cr.CVRecord(
            path=rel,
            branch=branch,
            specialty=specialty,
            role=cfg.roles.get(specialty, ""),
            headline=cr.headline_of(text, cr._junk_re(cfg.headline_noise)),
            sig=sig,
            mtime=p.stat().st_mtime,
        )
        rec.lang = "FR" if "Francais" in rel else ("EN" if "English" in rel else "")
        if not rec.lang:
            rec.lang = "FR" if p.name.endswith(("_FR.pdf",)) or "_FR_" in p.name else "EN"

        if args.limit and done >= args.limit:
            log.info("--limit %d reached; re-run to continue where this stopped",
                     args.limit)
            break

        if not args.no_ai:
            if done and args.sleep:
                time.sleep(args.sleep)
            try:
                out = cr.ask_json(
                    cfg, SUMMARY_SYSTEM,
                    f"--- CV TEXT ---\n{text[:14000]}", max_tokens=900,
                )
                rec.summary = out.get("summary", "")
                rec.skills = list(out.get("skills") or [])[:20]
                rec.lang = (out.get("lang") or rec.lang).upper()
                rec.headline = out.get("headline") or rec.headline
            except cr.AIError as e:
                log.error("AI unavailable: %s", e)
                args.no_ai = True   # degrade for the rest of the run
                failed += 1
            except Exception as e:
                log.warning("summary failed for %s: %s", rel, e)
                failed += 1

        if not rec.summary:
            rec.summary = rec.headline or specialty.replace("-", " ")
        pending[rel] = rec
        done += 1
        if done % 10 == 0:
            idx.commit(upserts=pending)   # merge, don't overwrite
            pending.clear()
            log.info("  %d indexed…", done)

    # Prune only when the whole collection was walked: a --limit run stopped
    # early, so it has not seen every CV. prune checks each entry
    # against the filesystem, so a CV the watcher filed mid-run survives.
    full_pass = not (args.limit and done >= args.limit)
    idx.commit(upserts=pending, prune=full_pass)
    log.info("indexed=%d unchanged=%d failed=%d total=%d -> %s",
             done, skipped, failed, len(idx.records), cfg.index_file)
    return 0


if __name__ == "__main__":
    sys.exit(main())
