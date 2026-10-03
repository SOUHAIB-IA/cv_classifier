"""The watcher, startable and stoppable while the program is running.

The settings are changed on a page served by this very process, and the watcher
reads them once, when it starts. Applying a change meant Ctrl+C and a fresh
`python start.py`. The button that promised to restart the watcher called
`systemctl --user restart`, which exists only if you ran install.sh, and on
Windows and macOS it had nothing to call at all.

One object owns the observer and the catch-up sweep. The page that writes a
setting can hand the watcher a new configuration, and the person who wrote the
setting never has to find the terminal it was started from.

It is a module-level singleton because there is exactly one watcher per
process: the launcher starts it in a thread, and the web app answering the
button is in the same process.
"""
from __future__ import annotations

import threading
import time
from pathlib import Path

import cvrouter as cr


class Supervisor:
    def __init__(self) -> None:
        # Reentrant: restart() holds it across stop() and start().
        self._lock = threading.RLock()
        self._obs = None
        self._router = None
        self._sweep: threading.Thread | None = None
        self._since = 0.0
        self._cfg_path: Path | None = None
        self._dry_run = False
        # False in a bare `uvicorn portal:app`, where no launcher ever handed
        # us the job. The button then says so instead of pretending.
        self.managed = False

    # ------------------------------------------------------------ state --
    def running(self) -> bool:
        return self._obs is not None and self._obs.is_alive()

    def status(self) -> dict:
        """Everything the page shows. Never raises: a broken config has to be
        reportable, and reporting it is this function's job."""
        out = {"managed": self.managed, "running": self.running(),
               "dry_run": self._dry_run, "since": self._since or None,
               "sweeping": bool(self._sweep and self._sweep.is_alive()),
               "watch_dir": None, "cv_root": None, "todo": [], "error": None}
        if not self.managed:
            # Reading the config here would report folders this process has no
            # intention of watching.
            return out
        try:
            cfg = cr.load_config(self._cfg_path)
            out["watch_dir"] = str(cfg.watch_dir)
            out["cv_root"] = str(cfg.cv_root)
            out["todo"] = cr.setup_todo(cfg)
        except Exception as e:
            out["error"] = f"{type(e).__name__}: {e}"
        return out

    def configure(self, cfg_path: Path | None, dry_run: bool = False) -> None:
        """Called by the launcher: this process is the one running the watcher."""
        self.managed = True
        self._cfg_path = cfg_path
        self._dry_run = dry_run

    # ----------------------------------------------------------- orders --
    def start(self) -> tuple[bool, str]:
        """Build a watcher from the configuration as it stands on disk.

        Read now, not at import: the whole point is that a setting changed a
        second ago takes effect here.

        watchdog picks the platform's own mechanism, inotify on Linux,
        ReadDirectoryChangesW on Windows, FSEvents on macOS. Nothing here is
        Linux-specific.

        The sweep runs in a daemon thread, so Ctrl+C in the web app stops
        everything, and any error inside it is logged rather than taking the
        whole application down: a CV that fails to classify must not close the
        window you are reading.
        """
        with self._lock:
            if not self.managed:
                # Without this, _cfg_path is None, cr.load_config falls back to
                # the config.toml beside the code, and a supervisor nobody gave
                # a job to starts watching the real download folder. A test
                # caught exactly that.
                return False, ("aucun lanceur ne lui a confié la surveillance : "
                               "rien à démarrer ici")
            if self.running():
                return False, "la surveillance tourne déjà"
            try:
                cfg = cr.load_config(self._cfg_path)
            except Exception as e:
                return False, f"la configuration ne se lit pas : {e}"

            todo = cr.setup_todo(cfg)
            if todo:
                return False, "il manque encore " + ", et ".join(todo)

            for d in (cfg.watch_dir, cfg.cv_root):
                try:
                    d.mkdir(parents=True, exist_ok=True)
                except OSError as e:
                    return False, f"le dossier {d} n'a pas pu être créé : {e}"

            from watchdog.observers import Observer

            import watcher as W

            try:
                router = W.Router(cfg, dry_run=self._dry_run)
                obs = Observer()
                obs.schedule(W.Handler(router), str(cfg.watch_dir), recursive=False)
                obs.start()
            except Exception as e:
                return False, f"la surveillance n'a pas démarré : {e}"

            def sweep() -> None:
                try:
                    router.sweep()
                except Exception:
                    router.log.exception("the catch-up sweep failed; "
                                         "the watcher is still running")

            t = threading.Thread(target=sweep, name="cv-router-sweep", daemon=True)
            t.start()

            self._obs, self._router, self._sweep = obs, router, t
            self._since = time.time()
            return True, f"surveillance de {cfg.watch_dir}"

    def stop(self) -> tuple[bool, str]:
        with self._lock:
            if not self.running() and self._router is None:
                return False, "la surveillance est déjà à l'arrêt"

            if self._router is not None:
                self._router.stopping = True
            obs, self._obs = self._obs, None
            if obs is not None:
                obs.stop()
                obs.join(timeout=5)

            sweep, self._sweep = self._sweep, None
            self._router = None
            self._since = 0.0

            if sweep is not None and sweep.is_alive():
                # It gives up at the next file rather than in the middle of
                # one. We do not wait for it: a single model call can take the
                # configured timeout, four minutes by default, and the request
                # that asked for this cannot be held open that long. Nothing is
                # classified twice meanwhile, because the claim set in
                # watcher.Router is shared by every router in this process.
                return True, "arrêtée (le fichier en cours finit d'être classé)"
            return True, "arrêtée"

    def restart(self) -> tuple[bool, str]:
        with self._lock:
            self.stop()                       # already stopped is not an error here
            return self.start()


WATCHER = Supervisor()
