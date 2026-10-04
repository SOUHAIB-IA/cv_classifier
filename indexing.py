"""Reading the CV collection, as a job the interface can start and watch.

Indexing is the first mandatory action of this product and it lived only on the
command line. The interface's answer to "what do I do now" was an error message
in English telling the reader to open a terminal, which is where the first user
outside this machine got stuck.

This runs `indexer.py` as a subprocess rather than importing it. That is
deliberate: the CLI path stays the one true path, so the button and the command
cannot drift apart, and a run that dies takes a child process with it and not
the web application. Progress is parsed from the lines the indexer already
prints, so neither file had to grow a callback.
"""
from __future__ import annotations

import re
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# The three lines indexer.py already logs. Parsing them keeps the progress
# honest: it is the indexer's own count, not an estimate drawn beside it.
RE_TOTAL = re.compile(r"(\d+) PDFs under ")
RE_SPLIT = re.compile(r"(\d+) unchanged, (\d+) to index")
RE_STEP = re.compile(r"\s(\d+)/(\d+)…")


class Indexer:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._proc: subprocess.Popen | None = None
        self._cfg_path: Path | None = None
        self._tail: list[str] = []
        self.managed = False
        self._st = self._idle()

    @staticmethod
    def _idle() -> dict:
        return {"state": "idle", "done": 0, "total": 0, "skipped": 0,
                "started_at": None, "error": None}

    # ------------------------------------------------------------- state --
    def running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def status(self) -> dict:
        with self._lock:
            out = dict(self._st)
            out["running"] = self.running()
            out["managed"] = self.managed
            return out

    def configure(self, cfg_path: Path | None) -> None:
        self.managed = True
        self._cfg_path = cfg_path

    # ------------------------------------------------------------ orders --
    def start(self) -> tuple[bool, str]:
        with self._lock:
            if not self.managed:
                # Without this, _cfg_path is None and indexer.py runs against
                # the config.toml beside the code. The watcher had the same
                # hole and a test caught it reading the real download folder.
                return False, ("aucun lanceur ne lui a confié la lecture : "
                               "rien à démarrer ici")
            if self.running():
                return False, "la lecture est déjà en cours"

            cmd = [sys.executable, str(ROOT / "indexer.py")]
            if self._cfg_path:
                cmd += ["--config", str(self._cfg_path)]
            try:
                # stderr into stdout: the indexer logs to stderr, and one stream
                # keeps the order of the lines we parse.
                self._proc = subprocess.Popen(
                    cmd, cwd=str(ROOT), stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT, text=True, bufsize=1)
            except OSError as e:
                self._st = self._idle() | {"state": "error", "error": str(e)}
                return False, f"la lecture n'a pas pu démarrer : {e}"

            self._tail = []
            self._st = self._idle() | {"state": "running", "started_at": time.time()}
            threading.Thread(target=self._follow, name="cv-router-index",
                             daemon=True).start()
            return True, "lecture démarrée"

    # ------------------------------------------------------------ reading --
    def _follow(self) -> None:
        """Read the child's output and keep the status in step with it."""
        proc = self._proc
        assert proc is not None and proc.stdout is not None
        for line in proc.stdout:
            line = line.rstrip()
            self._tail.append(line)
            del self._tail[:-40]              # enough to explain a failure
            with self._lock:
                m = RE_SPLIT.search(line)
                if m:
                    self._st["skipped"] = int(m.group(1))
                    self._st["total"] = int(m.group(2))
                    continue
                m = RE_STEP.search(line)
                if m:
                    self._st["done"] = int(m.group(1))
                    self._st["total"] = int(m.group(2))
                    continue
                m = RE_TOTAL.search(line)
                if m and not self._st["total"]:
                    self._st["total"] = int(m.group(1))

        code = proc.wait()
        with self._lock:
            if code == 0:
                self._st["state"] = "done"
                self._st["done"] = self._st["total"]
            else:
                self._st["state"] = "error"
                self._st["error"] = self._explain(code)

    def _explain(self, code: int) -> str:
        """Why it stopped, as a sentence rather than an exit code.

        The indexer saves after every batch, so a failure never costs the work
        already done. Saying that is the difference between an error the reader
        can act on and one that reads like lost time.
        """
        joined = "\n".join(self._tail)
        done = self._st["done"]
        kept = (f" Les {done} CV déjà lus sont gardés." if done else "")
        if "AI unavailable" in joined or "backend was unavailable" in joined:
            return ("Le modèle n'a pas répondu. Vérifie ta clé dans Réglages, "
                    "puis relance." + kept)
        last = next((l for l in reversed(self._tail) if l.strip()), "")
        return f"Code {code}. {last[-160:]}{kept}"


INDEXER = Indexer()
