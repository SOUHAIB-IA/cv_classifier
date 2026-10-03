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
          + (f"   ({detail})" if detail and not cond else ""), flush=True)
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
    check("the launcher and the Canada renderer agree",
          S.find_chrome() == CR.find_chrome(),
          (S.find_chrome(), CR.find_chrome()))
    # The pipeline's renderer takes a PipelineConfig, and pipeline.toml is not
    # in a fresh checkout. Asking for it crashed this file on the first CI run:
    # a test about finding a browser must not need a config about something
    # else. It is checked when the file is there and skipped, out loud, when it
    # is not.
    if (HERE / "pipeline.toml").is_file():
        from pipeline import config as pc
        check("...and so does the pipeline renderer",
              PT.find_chrome(pc.load()) == S.find_chrome())
    else:
        print("  skip  the pipeline renderer (no pipeline.toml in this "
              "checkout)", flush=True)

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
                  "pdftotext" in joined and "poppler" in joined.lower(),
                  joined[:120])
        finally:
            os.environ["PATH"] = env_path

        # Chrome is NOT hidden by an empty PATH on Windows or macOS, because
        # browsers.py deliberately looks in Program Files and /Applications.
        # Emptying PATH and expecting a complaint is a Linux assumption, and it
        # failed on both other platforms in CI. Take the browser away instead.
        import browsers
        real = browsers.find_chrome
        try:
            browsers.find_chrome = lambda preferred="": None
            fatal, _warn = S.preflight(None)
            check("a missing Chrome is reported, on any platform",
                  any("chrom" in f.lower() for f in fatal), fatal)
            check("...and says where to get it",
                  any("google.com/chrome" in f or "package manager" in f
                      for f in fatal), fatal)
        finally:
            browsers.find_chrome = real

    # A first run writes its own config, because `cp` is a command and the
    # people this is for do not type commands.
    with tempfile.TemporaryDirectory() as td:
        made = S.ensure_config(Path(td) / "config.toml")
        check("a first run writes config.toml from the example", made.is_file(), made)
        check("...and every file the Settings page reads, not just that one",
              all((S.ROOT / f).is_file() for f, _ in S.FIRST_RUN_FILES),
              [f for f, _ in S.FIRST_RUN_FILES if not (S.ROOT / f).is_file()])
        check("...and it is the example, comments included",
              made.read_text() == (S.ROOT / "config.example.toml").read_text())
        check("...and a second run does not overwrite it",
              (made.write_text("# touched\n"), S.ensure_config(made),
               made.read_text() == "# touched\n")[2])

    # Only if the example is gone too is it fatal, and it says so.
    with tempfile.TemporaryDirectory() as td:
        fatal, _ = S.preflight(Path(td) / "nope.toml")
        check("with no example either, it names the file to restore",
              any("config.example.toml" in f for f in fatal), fatal)

    print("\n4c. the first run: nothing starts until it can work")
    import cvrouter as cr
    import testkit
    import watcher as W

    cfg, tmp = testkit.temp_config()
    try:
        cfg.owner_name = cfg.owner_surname = ""
        cfg.backend = "api"
        cfg.provider = "groq"
        cfg.key_file = Path(tmp) / "no-key-here"
        todo = cr.setup_todo(cfg)
        check("a blank setup asks for the name", any("nom" in s for s in todo), todo)
        check("...and for the key", any("clé API" in s for s in todo), todo)

        cfg.provider = "ollama"
        check("a provider that needs no key is not asked for one",
              not any("clé" in s for s in cr.setup_todo(cfg)), cr.setup_todo(cfg))

        cfg.owner_name, cfg.owner_surname = "Ada", "LOVELACE"
        check("a complete setup has nothing left to do", cr.setup_todo(cfg) == [],
              cr.setup_todo(cfg))

        # The shipped example must never look ready: a first run that starts the
        # watcher is a first run that files someone's CVs under a blank name.
        shipped = cr.load_config(S.ROOT / "config.example.toml")
        check("the shipped example is deliberately not ready",
              cr.setup_todo(shipped) != [], cr.setup_todo(shipped))
        check("...and its watch folder is not the download folder",
              "Downloads" not in str(shipped.watch_dir), shipped.watch_dir)

        # The sweep gives up on the first unreachable model instead of failing
        # once per file, which is what the first user outside this machine saw.
        for n in ("un", "deux", "trois", "quatre"):
            testkit.make_pdf(cfg.watch_dir / f"{n}.pdf")
        tries = []
        real = cr.classify_pdf

        def boom(c, path, text=None):
            tries.append(path.name)
            raise cr.AIError("pas de cerveau")

        cr.classify_pdf = boom
        try:
            router = W.Router(cfg)
            router.sweep()
        finally:
            cr.classify_pdf = real
        check("the sweep stops at the first unreachable model",
              len(tries) == 1, tries)
        check("...and the files it never reached are still there",
              len(list(cfg.watch_dir.glob("*.pdf"))) == 4)
        check("...and it says why it stopped", bool(router.ai_down), router.ai_down)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("\n4d. the watcher, started and stopped from the page")
    import supervisor as SUP

    sup = SUP.Supervisor()
    check("before a launcher hands it the job, it says it is not in charge",
          sup.status()["managed"] is False)
    ok, msg = sup.start()
    check("...and refuses to start something it was never given",
          not ok, msg)

    with tempfile.TemporaryDirectory() as td:
        sand = Path(td)
        # A provider that needs no key, so the setup is complete and nothing
        # here ever reaches a model.
        text = (S.ROOT / "config.example.toml").read_text()
        def put(key, value, body):
            out = []
            for line in body.splitlines():
                head = line.split("=")[0].strip()
                out.append(f'{key:<10} = "{value}"' if head == key else line)
            return "\n".join(out)
        for k, v in (("cv_root", sand / "cvs"), ("watch_dir", sand / "watch"),
                     ("index_file", sand / "index.json"), ("log_file", sand / "log.log"),
                     ("seen_file", sand / "seen.json"), ("dupe_dir", sand / "dupes"),
                     ("text_cache_dir", ""), ("provider", "ollama"),
                     ("owner_name", "Hamza"), ("owner_surname", "BENNANI")):
            text = put(k, v, text)
        cfgp = sand / "config.toml"
        cfgp.write_text(text)

        sup.configure(cfgp)
        ok, msg = sup.start()
        check("configured, it starts", ok, msg)
        check("...and says so", sup.status()["running"] is True)
        check("...and made the folder it watches", (sand / "watch").is_dir())
        check("starting twice is refused, not doubled", not sup.start()[0])

        # The whole point: a setting changed a second ago takes effect without
        # anyone going back to the terminal the program was started from.
        cfgp.write_text(put("watch_dir", sand / "ailleurs", cfgp.read_text()))
        ok, msg = sup.restart()
        check("a restart rereads the configuration", ok, msg)
        check("...and watches the folder you just chose",
              sup.status()["watch_dir"] == str(sand / "ailleurs"),
              sup.status()["watch_dir"])
        check("...and made that one too", (sand / "ailleurs").is_dir())

        check("it stops", sup.stop()[0])
        check("...and stays stopped", sup.status()["running"] is False)
        check("stopping twice is refused, not an error on the page",
              not sup.stop()[0])

        # Two routers exist for a moment during a restart. The claim set is on
        # the class, so the file one of them is finishing cannot be picked up
        # by the other.
        import watcher as W
        cfg = cr.load_config(cfgp)
        a, b = W.Router(cfg), W.Router(cfg)
        check("every router shares one claim set", a._inflight is b._inflight)
        check("...and one lock over it", a._claim_lock is b._claim_lock)

    print("\n4e. the desktop, three ways")
    import desktop as D
    check("this platform is one it knows",
          D.SYSTEM in ("Linux", "Windows", "Darwin"), D.SYSTEM)
    # These three gestures are advisory. A notification that does not appear and
    # a folder that does not open are an inconvenience; raising would stop the
    # watcher from filing a CV over a missing notifier.
    check("notify never raises, whatever the desktop answers",
          D.notify("filed", "cv-router", "test") in (True, False))
    with tempfile.TemporaryDirectory() as td:
        missing = Path(td) / "does-not-exist.pdf"
        got = D.reveal(missing)
        check("reveal returns (opened, selected) and never raises",
              isinstance(got, tuple) and len(got) == 2
              and all(isinstance(x, bool) for x in got), got)
        check("open_folder on a real folder answers a bool",
              isinstance(D.open_folder(Path(td)), bool))
    # The quoting is the part that breaks silently: an apostrophe in a company
    # name reaching PowerShell unescaped would end the string early.
    check("PowerShell quoting doubles the apostrophe",
          D._ps_quote("O'Brien & Co") == "'O''Brien & Co'", D._ps_quote("O'Brien & Co"))
    check("osascript quoting escapes the double quote",
          D._osa_quote('say "hi"') == '"say \\"hi\\""', D._osa_quote('say "hi"'))
    # start.py runs the watcher in a thread, so there is no service to restart.
    # The button must say that rather than fail with a systemctl error.
    mgr = D.service_manager()
    check("the service manager is named, or honestly absent",
          mgr in ("systemd", None), mgr)
    ok_r, msg = D.restart_watcher()
    check("restart_watcher explains itself when there is no service",
          ok_r or ("Ctrl+C" in msg or "service" in msg), msg)
    check("no module outside desktop.py calls a Linux-only tool",
          not [f for f in files
               if f.name not in ("desktop.py", "test_portable.py")
               and any(tool in f.read_text(encoding="utf-8")
                       for tool in ('"notify-send"', '"dbus-send"',
                                    '"xdg-open"'))],
          [f.name for f in files
           if f.name not in ("desktop.py", "test_portable.py")
           and any(tool in f.read_text(encoding="utf-8")
                   for tool in ('"notify-send"', '"dbus-send"', '"xdg-open"'))])

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
