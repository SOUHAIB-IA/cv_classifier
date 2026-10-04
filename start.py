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

import browsers  # noqa: E402  (after sys.path, on purpose)


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
CHROMES = browsers.NAMES

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
    return browsers.find_chrome()


# The three files the program writes to, and the examples they come from. Only
# the examples are in the repository, so a fresh clone has none of the three.
# All three matter on a first run, not just the config: settings.py reads
# pipeline.toml every time the Settings page loads, so a first run that lands
# there without it would answer 500 instead of a form.
FIRST_RUN_FILES = (("config.toml", "config.example.toml"),
                   ("pipeline.toml", "pipeline.example.toml"),
                   ("profile.toml", "profile.example.toml"))


def ensure_config(path: Path | None) -> Path:
    """The files the program writes to, copied from their examples the first
    time. Returns the config path.

    A first run used to stop with three `cp` commands, and the people this is
    for do not type commands.

    They are copied rather than generated because in these files the comments
    are the documentation, and settings.py patches them in place to keep them.
    A config built from code would lose every explanation the first time
    someone saved a setting from the web page.
    """
    cfg_path = path or ROOT / "config.toml"
    made = []
    for target, example in FIRST_RUN_FILES:
        dest = cfg_path if target == "config.toml" else ROOT / target
        src = ROOT / example
        if dest.is_file() or not src.is_file():
            continue
        shutil.copy2(src, dest)
        made.append(dest.name)
    if made:
        say(f"  first run: {', '.join(made)} written from the examples")
    return cfg_path


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
        # ensure_config() runs before this and copies the example, so reaching
        # here means the example is gone too.
        fatal.append("no config.toml, and no config.example.toml to copy it "
                     "from.\n      Restore config.example.toml from the "
                     "repository and start again.")
        return fatal, warn

    import cvrouter as cr
    try:
        cfg = cr.load_config(cfg_path)
    except Exception as e:                       # a broken TOML, most often
        fatal.append(f"config.toml could not be read: {e}")
        return fatal, warn

    # The folders are created rather than complained about, and what is missing
    # from the settings is cr.setup_todo()'s job: it decides whether the watcher
    # may start at all, which a warning printed into a scrolling terminal never
    # did.
    return fatal, warn


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

    cfg_path = ensure_config(args.config)

    fatal, warn = preflight(cfg_path)
    for w in warn:
        say(f"  note: {w}")
    if fatal:
        say("\ncv-router cannot start:")
        for f in fatal:
            say(f"  - {f}")
        return 1

    import cvrouter as cr

    cfg = cr.load_config(cfg_path)
    host = args.host or cfg.host
    port = args.port or cfg.port
    url = f"http://{host}:{port}"

    # The watcher belongs to the supervisor from here on, so the Settings page
    # can stop and start it without anyone going back to this terminal.
    from supervisor import WATCHER

    WATCHER.configure(cfg_path, dry_run=args.dry_run)

    # The Read my CVs button runs indexer.py, and it must run it against the
    # same configuration this process was started with.
    import indexing

    indexing.INDEXER.configure(cfg_path)

    # Everything still missing, as sentences. The watcher does not start while
    # this is non-empty: without a brain it can only fail, once per file, with a
    # desktop notification each time.
    todo = cr.setup_todo(cfg)

    # Settings are only half of being ready. Someone who has filled in their
    # name and key but has never read their CVs would land on the analysis page
    # with nothing to analyse, which is where the product used to lose people.
    # The welcome page holds them until there is something to work with.
    try:
        has_cvs = bool(cr.Index(cfg).records)
    except Exception:
        has_cvs = False
    ready = not todo and has_cvs

    if todo:
        # This block is in French, alone in an English file, because it is the
        # one thing a first-time user reads and it sends them to a page that is
        # in French. The language of the message and the language of the screen
        # it points at have to match.
        say("\n  Pas encore configuré. Il manque :")
        for item in todo:
            say(f"    - {item}")
        say("  La page de bienvenue s'ouvre là-dessus, et chaque étape y porte "
            "le bouton qui la règle.")
    elif not args.no_watcher:
        # The supervisor creates the folders rather than complaining about
        # them: a folder that does not exist is a thing to make.
        ok, message = WATCHER.start()
        if ok:
            say(f"  watching {cfg.watch_dir}  ->  {cfg.cv_root}"
                  + ("  (dry run, nothing moves)" if args.dry_run else ""))
        else:
            # The web app is useful on its own, so a watcher that cannot start
            # is a warning and not the end of the session.
            say(f"  note: the watcher did not start: {message}")

    if not todo and not has_cvs:
        say("\n  Aucun CV lu pour l'instant. La page de bienvenue te demande "
            "où ils sont et les lit en un clic.")

    landing = url + ("" if ready else "/bienvenue")
    say(f"  open {landing}\n  Ctrl+C to stop")

    if not args.no_browser:
        # After a short delay, so the first request does not race the server.
        threading.Timer(1.5, lambda: webbrowser.open(landing)).start()

    import uvicorn

    import portal

    try:
        uvicorn.run(portal.app, host=host, port=port, log_level="warning")
    except KeyboardInterrupt:
        pass
    finally:
        WATCHER.stop()
        say("stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
