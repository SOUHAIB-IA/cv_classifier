#!/usr/bin/env python3
"""Background daemon: watch the Downloads folder and file every CV PDF that
lands there into the right specialty folder.

  python watcher.py            run in the foreground
  python watcher.py --once     sweep the existing PDFs in watch_dir, then exit
  python watcher.py --dry-run  decide and log, but move nothing

Anything that is not a CV, or not the owner's CV, is left exactly where it is.
"""
from __future__ import annotations

import argparse
import shutil
import threading
import sys
import time
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

import cvrouter as cr


class Router:
    def __init__(self, cfg: cr.Config, dry_run: bool = False):
        self.cfg = cfg
        self.dry_run = dry_run or cfg.dry_run
        self.log = cr.setup_logging(cfg, "watcher")
        self.index = cr.Index(cfg)
        # Paths being processed right now — collapses the burst of created /
        # modified / moved events a single download fires.
        self._inflight: set[str] = set()
        # Identities already dealt with, so a file we deliberately left in
        # Downloads is not re-classified on every later event. Keyed on
        # path+size+mtime, NOT on path alone: browsers reuse filenames, and a
        # fresh download of an old name must still be processed.
        self._done: dict[str, float] = {}
        # The observer thread and the startup sweep both call handle(), so the
        # claim and every index mutation have to be atomic.
        self._claim_lock = threading.Lock()
        self._index_lock = threading.Lock()

    @staticmethod
    def _fingerprint(path: Path) -> str:
        st = path.stat()
        return f"{path.resolve()}|{st.st_size}|{st.st_mtime_ns}"

    def _already_done(self, fp: str) -> bool:
        with self._claim_lock:
            if fp in self._done:
                return True
            if len(self._done) > 2000:          # keep the newest half
                for k in sorted(self._done, key=self._done.get)[:1000]:
                    del self._done[k]
            self._done[fp] = time.time()
            return False

    # -- helpers ----------------------------------------------------------
    def _settled(self, path: Path) -> bool:
        """Wait until the file stops growing, so we don't read a partial download."""
        last = -1
        for _ in range(40):
            if not path.exists():
                return False
            size = path.stat().st_size
            if size == last and size > 0:
                return True
            last = size
            time.sleep(self.cfg.settle_seconds)
        return path.exists() and path.stat().st_size > 0

    def _skip(self, path: Path) -> bool:
        n = path.name
        return (
            n.startswith(".")
            or n.endswith((".crdownload", ".part", ".tmp"))
            or path.suffix.lower() != ".pdf"
        )

    # -- main entry point -------------------------------------------------
    def handle(self, path: Path) -> None:
        if self._skip(path):
            return
        key = str(path.resolve())
        with self._claim_lock:
            if key in self._inflight:
                return
            self._inflight.add(key)
        try:
            self._handle(path)
        finally:
            with self._claim_lock:
                self._inflight.discard(key)

    def _handle(self, path: Path) -> None:
        if not self._settled(path):
            # Usually the browser's temp name being renamed to the real one;
            # the rename fires its own event, so there is nothing to do here.
            self.log.debug("vanished before settling: %s", path.name)
            return

        # Only now is the file whole, so only now is its identity stable.
        if self._already_done(self._fingerprint(path)):
            return

        try:
            res = cr.classify_pdf(self.cfg, path)
        except cr.AIError as e:
            self.log.error("AI unavailable, leaving %s in place: %s", path.name, e)
            cr.notify(self.cfg, "error", "cv-router: IA indisponible",
                      f"{path.name} laissé dans Downloads.\n{e}")
            return
        except Exception as e:
            self.log.exception("classify failed for %s: %s", path.name, e)
            cr.notify(self.cfg, "error", "cv-router: échec du classement",
                      f"{path.name}\n{e}")
            return

        if not res.get("is_cv"):
            self.log.info("not a CV, left alone: %s (%s)",
                          path.name, res.get("reason", ""))
            cr.notify(self.cfg, "skipped", "cv-router: pas un CV",
                      f"{path.name}\n{res.get('reason', '')}")
            return
        if not res.get("is_owner"):
            self.log.info("someone else's CV, left alone: %s (%s)",
                          path.name, res.get("reason", ""))
            cr.notify(self.cfg, "skipped", "cv-router: CV d'une autre personne",
                      f"{path.name} laissé dans Downloads.")
            return

        conf = float(res.get("confidence") or 0)
        if conf < self.cfg.min_confidence:
            self.log.warning("low confidence %.2f, left alone: %s (%s)",
                             conf, path.name, res.get("reason", ""))
            cr.notify(self.cfg, "lowconf",
                      f"cv-router: doute ({conf:.0%}) — à classer à la main",
                      f"{path.name} laissé dans Downloads.\n{res.get('reason', '')}")
            return

        # Already have this exact content?
        dup = self.index.find_by_sig(res["_sig"])
        if dup:
            self.cfg.dupe_dir.mkdir(parents=True, exist_ok=True)
            target = self.cfg.dupe_dir / cr.unique_name(
                self.cfg.dupe_dir, path.stem)
            self.log.info("duplicate of %s -> %s", dup, target.name)
            if not self.dry_run:
                shutil.move(str(path), str(target))
            cr.notify(self.cfg, "duplicate", "cv-router: doublon",
                      f"{path.name}\nMême contenu que « {Path(dup).name} ».\n"
                      f"Déplacé dans _Duplicates-auto/")
            return

        folder, name = cr.destination(self.cfg, res)
        self.log.info(
            "FILE %s -> %s/%s  [conf %.2f] %s",
            path.name, folder.relative_to(self.cfg.cv_root), name, conf,
            res.get("reason", ""),
        )
        if self.dry_run:
            return

        folder.mkdir(parents=True, exist_ok=True)
        dest = folder / name
        shutil.move(str(path), str(dest))

        rel = str(dest.relative_to(self.cfg.cv_root))
        record = cr.CVRecord(
            path=rel,
            branch=res.get("branch", ""),
            specialty=res.get("specialty") or res.get("new_specialty", ""),
            role=self.cfg.roles.get(res.get("specialty", ""), ""),
            lang=res.get("lang", ""),
            headline=res.get("headline", ""),
            summary=res.get("summary", ""),
            skills=list(res.get("skills") or [])[:20],
            sig=res["_sig"],
            mtime=dest.stat().st_mtime,
        )
        with self._index_lock:
            # Merges into the live file under an flock, so a concurrent
            # indexer.py run cannot overwrite this entry.
            self.index.commit(upserts={rel: record})

        cr.notify(
            self.cfg, "filed", "cv-router: CV rangé",
            f"{path.name}\n→ {folder.relative_to(self.cfg.cv_root)}\n"
            f"   {name}\n{res.get('reason', '')}",
        )

    def sweep(self) -> None:
        for p in sorted(self.cfg.watch_dir.glob("*.pdf")):
            self.handle(p)


class Handler(FileSystemEventHandler):
    def __init__(self, router: Router):
        self.router = router

    def on_created(self, event):
        if not event.is_directory:
            self.router.handle(Path(event.src_path))

    def on_moved(self, event):
        # Browsers write foo.pdf.crdownload then rename to foo.pdf
        if not event.is_directory:
            self.router.handle(Path(event.dest_path))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true", help="sweep then exit")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--config", type=Path, default=None)
    args = ap.parse_args()

    cfg = cr.load_config(args.config)
    router = Router(cfg, dry_run=args.dry_run)
    router.log.info("cv-router watching %s -> %s (dry_run=%s)",
                    cfg.watch_dir, cfg.cv_root, router.dry_run)

    if cfg.backend == "claude_cli":
        binp = cr.find_claude_bin()
        if binp:
            router.log.info("AI backend: claude CLI (%s, model=%s)", binp, cfg.cli_model)
        else:
            router.log.error("AI backend is claude_cli but no Claude Code binary "
                             "was found; the watcher cannot classify.")
    elif not cfg.api_key:
        router.log.error("no API key; the watcher cannot classify. "
                         "Set $ANTHROPIC_API_KEY or fill %s", cfg.key_file)

    if args.once:
        router.sweep()
        return 0

    # Start watching BEFORE the catch-up sweep. The sweep can take a while (one
    # model call per PDF already sitting there), and anything downloaded during
    # it would otherwise fall through the gap: too late for the sweep's glob,
    # too early for the observer. Router.seen makes the overlap harmless.
    obs = Observer()
    obs.schedule(Handler(router), str(cfg.watch_dir), recursive=False)
    obs.start()
    router.sweep()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        obs.stop()
        obs.join()
    return 0


if __name__ == "__main__":
    sys.exit(main())
