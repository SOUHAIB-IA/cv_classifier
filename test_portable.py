#!/usr/bin/env python3
"""Tests for running on Linux, macOS and Windows.

The guard that matters is the first one: no module may import something that
exists only on Unix. `fcntl` was imported at the top of cvrouter.py and
pipeline/db.py, so on Windows nothing started at all — not a feature that
failed, the whole program, before a single line of ours ran. That class of
defect is invisible on the machine you develop on, so it needs a test that does
not depend on which machine that is.

Run:  ./.venv/bin/python test_portable.py
"""
from __future__ import annotations

import ast
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import locking                                           # noqa: E402
import start as S                                        # noqa: E402

ok = True

# Modules the standard library ships only on Unix. Importing one at module level
# makes the file unimportable on Windows.
UNIX_ONLY = {"fcntl", "pwd", "grp", "termios", "tty", "pty", "resource",
             "syslog", "posix", "crypt", "spwd", "nis", "readline"}

# Where our own code lives. The venv is not ours to police.
OURS = ["cvrouter.py", "indexer.py", "matcher.py", "match.py", "portal.py",
        "run_pipeline.py", "settings.py", "watcher.py", "webui.py",
        "locking.py", "start.py", "testkit.py", "pipeline", "canada_module",
        "build"]


def check(label, cond, detail=""):
    global ok
    print(("  PASS  " if cond else "  FAIL  ") + label
          + (f"   ({detail})" if detail and not cond else ""))
    ok = ok and bool(cond)


def py_files() -> list[Path]:
    out = []
    for name in OURS:
        p = HERE / name
        if p.is_file() and p.suffix == ".py":
            out.append(p)
        elif p.is_dir():
            out += [f for f in p.rglob("*.py") if "__pycache__" not in f.parts]
    return out


def imported_names(path: Path) -> set[str]:
    """Top-level module names this file imports, anywhere in it."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return set()
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            out.add(node.module.split(".")[0])
    return out


def main() -> int:
    print("\n1. nothing imports a Unix-only module")
    files = py_files()
    check(f"{len(files)} source files found", len(files) > 20, len(files))
    offenders = []
    for f in files:
        if f.name == "test_portable.py":
            continue                       # it names them on purpose, as data
        bad = imported_names(f) & UNIX_ONLY
        if bad:
            offenders.append(f"{f.relative_to(HERE)}: {', '.join(sorted(bad))}")
    check("no Unix-only import anywhere in our code", not offenders, offenders)

    print("\n2. the lock works on this platform")
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "x.lock"
        with locking.exclusive(p):
            check("a lock can be taken", p.is_file())
            # Two holders at once would make the index merge meaningless.
            try:
                with locking.exclusive(p, timeout=0.2):
                    check("a second holder is refused", False)
            except locking.LockBusy:
                check("a second holder is refused", True)
        with locking.exclusive(p, timeout=0.2):
            check("...and the lock is free again once released", True)

        # The waiting path: a holder that lets go is waited for, not refused.
        held = threading.Event()
        done = threading.Event()

        def hold():
            with locking.exclusive(p):
                held.set()
                time.sleep(0.4)
            done.set()

        t = threading.Thread(target=hold, daemon=True)
        t.start()
        held.wait(2)
        t0 = time.monotonic()
        try:
            with locking.exclusive(p, timeout=5.0):
                waited = time.monotonic() - t0
                check("a caller with a timeout waits for the holder",
                      0.1 < waited < 4.0, f"{waited:.2f}s")
        except locking.LockBusy:
            check("a caller with a timeout waits for the holder", False)
        t.join(2)

    print("\n3. the two callers still raise what they always raised")
    import cvrouter as cr
    from pipeline import db as D
    check("IndexLockTimeout still exists", hasattr(cr, "IndexLockTimeout"))
    with tempfile.TemporaryDirectory() as td:
        lock = Path(td) / "run.lock"
        with D.run_lock(lock):
            try:
                with D.run_lock(lock):
                    check("a second pipeline run is refused", False)
            except RuntimeError as e:
                check("a second pipeline run is refused",
                      "another pipeline run" in str(e), str(e))

    print("\n4. finding Chrome")
    import browsers
    from canada_module import render as CR
    from pipeline import tailor as PT
    check("Chrome is found on this machine", bool(S.find_chrome()),
          "none of " + ", ".join(S.CHROMES))
    # There were three copies of this list and none knew the name `chrome`,
    # which is what Windows calls the binary and what a CI runner puts on PATH.
    check("the bare name `chrome` is searched for", "chrome" in browsers.NAMES)
    check("so is chrome.exe", "chrome.exe" in browsers.NAMES)
    check("there are Windows locations off PATH", browsers.WINDOWS_RELATIVE)
    check("and macOS bundle paths", browsers.MACOS_PATHS)
    # One list, three callers: a browser one of them can find, all of them can.
    check("the launcher and the renderers agree",
          S.find_chrome() == CR.find_chrome()
          == PT.find_chrome(__import__("pipeline.config",
                                       fromlist=["load"]).load()),
          (S.find_chrome(), CR.find_chrome()))

    print("\n4b. the launcher's preflight")
    check("every platform has an install hint",
          set(S.INSTALL_HINT) >= {"Linux", "Darwin", "Windows"})
    for sysname in ("Linux", "Darwin", "Windows"):
        h = S.INSTALL_HINT[sysname]
        check(f"{sysname}: a hint for poppler and for Chrome",
              h.get("poppler") and h.get("chrome"))

    # A missing prerequisite must be a sentence, not a traceback three minutes
    # into the run.
    with tempfile.TemporaryDirectory() as td:
        env_path = os.environ["PATH"]
        try:
            os.environ["PATH"] = td          # nothing on PATH at all
            fatal, _warn = S.preflight(None)
            joined = " ".join(fatal)
            check("a missing poppler is reported, with how to install it",
                  "pdftotext" in joined and "poppler" in joined.lower(), joined[:120])
            check("a missing Chrome is reported",
                  any("chrom" in f.lower() for f in fatal), joined[:120])
        finally:
            os.environ["PATH"] = env_path

    # And a missing config says which file to copy.
    with tempfile.TemporaryDirectory() as td:
        fatal, _ = S.preflight(Path(td) / "nope.toml")
        check("a missing config names the file to copy",
              any("config.example.toml" in f for f in fatal), fatal)

    print("\n5. it starts, serves every page, and stops")
    if not (HERE / "config.toml").is_file():
        print("  skip  no config.toml on this machine")
    else:
        import socket
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        proc = subprocess.Popen(
            [sys.executable, str(HERE / "start.py"), "--no-browser",
             "--no-watcher", "--port", str(port)],
            cwd=str(HERE), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True)
        try:
            import urllib.error
            import urllib.request

            def get(path):
                try:
                    with urllib.request.urlopen(
                            f"http://127.0.0.1:{port}{path}", timeout=3) as r:
                        return r.status
                except (urllib.error.URLError, OSError):
                    return 0

            deadline = time.monotonic() + 40
            while get("/") != 200 and time.monotonic() < deadline:
                if proc.poll() is not None:
                    break
                time.sleep(0.5)
            for path in ("/", "/pipeline", "/data", "/settings", "/canada/"):
                check(f"{path} answers", get(path) == 200)
        finally:
            proc.terminate()
            try:
                out = proc.communicate(timeout=10)[0]
            except subprocess.TimeoutExpired:
                proc.kill()
                out = proc.communicate()[0]
        # stdout is not a terminal here, so this also proves the flush.
        check("it says where to open it, before it exits",
              "open http://127.0.0.1" in (out or ""), (out or "")[:200])

    print("\n" + ("ALL PASS" if ok else "FAILURES ABOVE"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
