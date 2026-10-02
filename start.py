#!/usr/bin/env python3
"""Start cv-router: one command, one window, Linux, macOS or Windows.

    python start.py

The watcher runs in a background thread and the web app in the main one, so
there is no service to install and nothing to configure in systemd. That matters
beyond convenience: half of what was Linux-only in this project existed only to
serve systemd — the `systemctl --user restart` button, and the DISPLAY /
WAYLAND_DISPLAY / XAUTHORITY plumbing that exists because a service starts with
no screen and has to find one. Started from your own session, none of that is
needed.

Prerequisites are checked before anything starts, and a missing one is reported
as the sentence you need rather than as a traceback three minutes later.
"""
from __future__ import annotations

import argparse
import os
import platform
import shutil
import sys
import threading
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def say(*a) -> None:
    """Print and flush.

    Python buffers stdout when it is not a terminal, so a launcher started from
    a shortcut or a pipe printed nothing until it exited — the one moment a
    first-time user most needs to be told what is happening.
    """
    print(*a, flush=True)


# poppler reads the PDFs: text for matching, page count and fonts for the
# checks. Chrome renders them. Neither ships with Python.
POPPLER = ("pdftotext", "pdfinfo")
CHROMES = ("google-chrome", "google-chrome-stable", "chromium",
           "chromium-browser", "chrome", "msedge")

INSTALL_HINT = {
    "Linux": {"poppler": "sudo apt install poppler-utils   (or: dnf install poppler-utils)",
              "chrome": "install Google Chrome or Chromium from your package manager"},
    "Darwin": {"poppler": "brew install poppler",
               "chrome": "install Google Chrome from google.com/chrome"},
    "Windows": {"poppler": "download poppler for Windows and add its bin\\ folder to PATH\n"
                           "      https://github.com/oschwartz10612/poppler-windows/releases",
                "chrome": "install Google Chrome from google.com/chrome"},
}


def find_chrome() -> str | None:
    """Chrome, wherever this platform keeps it."""
    for name in CHROMES:
        p = shutil.which(name)
        if p:
            return p
    # Windows installs it outside PATH more often than not.
    for base in (os.environ.get("PROGRAMFILES", r"C:\Program Files"),
                 os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"),
                 os.environ.get("LOCALAPPDATA", "")):
        if not base:
            continue
        for rel in (r"Google\Chrome\Application\chrome.exe",
                    r"Microsoft\Edge\Application\msedge.exe"):
            p = Path(base) / rel
            if p.is_file():
                return str(p)
    # macOS keeps it in a bundle, which is not on PATH either.
    for p in ("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
              "/Applications/Chromium.app/Contents/MacOS/Chromium"):
        if Path(p).is_file():
            return p
    return None


def preflight(cfg_path: Path | None) -> tuple[list[str], list[str]]:
    """Everything that must be true before starting. (fatal, warnings)"""
    system = platform.system()
    hint = INSTALL_HINT.get(system, INSTALL_HINT["Linux"])
    fatal: list[str] = []
    warn: list[str] = []

    missing = [t for t in POPPLER if not shutil.which(t)]
    if missing:
        fatal.append(f"{', '.join(missing)} not found. cv-router reads your PDFs "
                     f"with poppler.\n      {hint['poppler']}")

    if not find_chrome():
        fatal.append(f"no Chrome or Chromium found. cv-router renders CVs with "
                     f"it.\n      {hint['chrome']}")

    if not (cfg_path or ROOT / "config.toml").is_file():
        fatal.append("no config.toml. Copy the example and open the Settings "
                     "page to fill it in:\n"
                     "      cp config.example.toml config.toml")
        return fatal, warn

    import cvrouter as cr
    try:
        cfg = cr.load_config(cfg_path)
    except Exception as e:                       # a broken TOML, most often
        fatal.append(f"config.toml could not be read: {e}")
        return fatal, warn

    if not cfg.cv_root.is_dir():
        warn.append(f"the CV folder does not exist yet: {cfg.cv_root}")
    if not cfg.watch_dir.is_dir():
        warn.append(f"the watch folder does not exist: {cfg.watch_dir}")
    if cfg.backend == "claude_cli" and not cr.find_claude_bin():
        warn.append("the brain is set to the Claude Code CLI but no Claude Code "
                    "install was found. Open Settings and pick a provider, or "
                    "paste an API key.")
    elif cfg.backend == "api" and not cfg.api_key:
        warn.append("the brain is set to an API key and there is none. Open "
                    "Settings and paste one.")
    return fatal, warn


def start_watcher(cfg, dry_run: bool = False):
    """The folder watcher, in a thread of its own.

    watchdog picks the platform's own mechanism: inotify on Linux,
    ReadDirectoryChangesW on Windows, FSEvents on macOS. Nothing here is
    Linux-specific.

    It is a daemon thread, so Ctrl+C in the web app stops everything, and any
    error inside it is logged rather than taking the whole application down:
    a CV that fails to classify must not close the window you are reading.
    """
    from watchdog.observers import Observer

    import watcher as W

    router = W.Router(cfg, dry_run=dry_run)
    obs = Observer()
    obs.schedule(W.Handler(router), str(cfg.watch_dir), recursive=False)
    obs.start()

    def sweep():
        try:
            router.sweep()
        except Exception:
            router.log.exception("the catch-up sweep failed; "
                                 "the watcher is still running")

    threading.Thread(target=sweep, name="cv-router-sweep", daemon=True).start()
    return obs, router


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="python start.py",
        description="Start cv-router: the watcher and the web app, together.")
    ap.add_argument("--config", type=Path, default=None)
    ap.add_argument("--no-watcher", action="store_true",
                    help="web app only, do not watch the download folder")
    ap.add_argument("--no-browser", action="store_true",
                    help="do not open a browser window")
    ap.add_argument("--dry-run", action="store_true",
                    help="the watcher decides and logs, but moves nothing")
    ap.add_argument("--host", default=None)
    ap.add_argument("--port", type=int, default=None)
    args = ap.parse_args(argv)

    say(f"cv-router on {platform.system()} {platform.release()}, "
          f"Python {platform.python_version()}")

    fatal, warn = preflight(args.config)
    for w in warn:
        say(f"  note: {w}")
    if fatal:
        say("\ncv-router cannot start:")
        for f in fatal:
            say(f"  - {f}")
        return 1

    import cvrouter as cr

    cfg = cr.load_config(args.config)
    host = args.host or cfg.host
    port = args.port or cfg.port

    obs = None
    if not args.no_watcher:
        try:
            obs, _ = start_watcher(cfg, dry_run=args.dry_run)
            say(f"  watching {cfg.watch_dir}  ->  {cfg.cv_root}"
                  + ("  (dry run, nothing moves)" if args.dry_run else ""))
        except Exception as e:
            # The web app is useful on its own, so a watcher that cannot start
            # is a warning and not the end of the session.
            say(f"  note: the watcher could not start: {e}")

    url = f"http://{host}:{port}"
    say(f"  open {url}\n  Ctrl+C to stop")

    if not args.no_browser:
        # After a short delay, so the first request does not race the server.
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()

    import uvicorn

    import portal

    try:
        uvicorn.run(portal.app, host=host, port=port, log_level="warning")
    except KeyboardInterrupt:
        pass
    finally:
        if obs is not None:
            obs.stop()
            obs.join(timeout=5)
        say("stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
