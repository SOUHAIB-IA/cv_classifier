"""Core library for cv-router: config, PDF text, the CV index, and the AI calls.

Nothing here touches the filesystem outside cv_root / watch_dir / dupe_dir.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import subprocess
import sys
import threading
import time
import tomllib
import unicodedata
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from pathlib import Path

import locking

HERE = Path(__file__).resolve().parent

# ---------------------------------------------------------------- taxonomy --
# These are DEFAULTS. Your own folders, branches and role slugs belong in the
# [taxonomy] section of config.toml — the tool reads them from there, so you can
# reshape the filing system without touching this file.
#
# Branch = career stage. The model must choose one of these two.
DEFAULT_BRANCHES = {
    "1-Etudiant-PFE":
        "The CV CALLS HIM a student: 'Élève ingénieur', 'Étudiant', 'student', "
        "'Final Year Student', or its summary asks for a PFE / stage / internship.",
    "2-Diplome-Etudes-Terminees":
        "The CV presents him as someone who has finished studying: 'Ingénieur "
        "diplômé', 'Engineering graduate', or simply 'Ingénieur IA' / 'Data "
        "Scientist' with NO student wording and NO request for an internship.",
}

# The branch is decided by the CV's own wording, not by enrolment dates. Spelling
# that out matters: a graduate-voiced CV still lists its degree period, and the
# model otherwise reads that period as 'still a student'.
BRANCH_RULE = """Choose the branch from HOW THE CV DESCRIBES HIM, never from the
dates of his degree. A CV whose summary says 'Ingénieur IA & Data with concrete
experience' belongs in 2-Diplome-Etudes-Terminees even though it still shows the
engineering-degree period, because nothing in it calls him a student or asks for
an internship. Only the words student / étudiant / élève-ingénieur / PFE / stage
put a CV in 1-Etudiant-PFE."""

# Specialty folder -> short role slug used in the filename.
DEFAULT_ROLES = {
    "AI-Agents-LLM-NLP": "AI-Agents-LLM",
    "AI-FullStack-Developer": "AI-FullStack-Dev",
    "AI-ML-Engineering": "AI-ML-Engineer",
    "Computer-Vision-Deep-Learning": "Computer-Vision-DL",
    "Data-Analysis-BI": "Data-Analyst-BI",
    "Data-Engineering-Cloud": "Data-Engineer-Cloud",
    "Data-Science-AI-General": "Data-Scientist-AI",
    "Data-Scientist-Machine-Learning": "Data-Scientist-ML",
    "Document-AI-Risk-Modeling": "Document-AI-Risk",
    "Frontend-Development": "Frontend-React-Next",
    "MLOps-DevOps": "MLOps-DevOps",
    "Python-Development": "Python-Developer",
    "Salesforce-Java-Backend": "Salesforce-Java-Backend",
    "Software-Engineering-FullStack": "Software-Engineer-FullStack",
    "Venture-Capital-Analyst": "VC-Analyst",
}

# Specialties split into per-language subfolders on disk.
DEFAULT_LANG_SPLIT = {"Data-Science-AI-General": {"FR": "Francais", "EN": "English"}}


# ------------------------------------------------------------------ config --
@dataclass
class Config:
    cv_root: Path
    watch_dir: Path
    dupe_dir: Path
    index_file: Path
    log_file: Path
    backend: str
    provider: str          # anthropic | openai | google | ... | custom
    base_url: str          # "" = the provider's own address
    model: str
    cli_model: str
    claude_bin: str
    timeout: int
    key_file: Path
    max_tokens: int
    owner_name: str
    owner_surname: str
    file_prefix: str
    branches: dict
    roles: dict
    lang_split: dict
    min_confidence: float
    settle_seconds: float
    dry_run: bool
    host: str
    port: int
    notify: dict
    headline_noise: str
    seen_file: Path
    seen_ttl_days: float
    text_cache_dir: Path | None
    index_workers: int
    index_model: str
    index_batch_size: int

    @property
    def api_key(self) -> str | None:
        """The key for whichever provider is selected.

        ANTHROPIC_API_KEY still wins for Anthropic, because that is the variable
        the SDK and every other tool already read. For the others the key lives
        in key_file, so switching provider is a key change, not an env change.
        """
        if self.provider != "anthropic":
            if self.key_file.is_file():
                return self.key_file.read_text().strip() or None
            return None
        key = os.environ.get("ANTHROPIC_API_KEY")
        if key:
            return key.strip()
        if self.key_file.is_file():
            k = self.key_file.read_text().strip()
            return k or None
        return None


def _slug_prefix(name: str, surname: str) -> str:
    """'Ada', 'LOVELACE' -> 'Ada-LOVELACE' (filename prefix)."""
    parts = [x for x in (name.strip(), surname.strip()) if x]
    return "-".join(parts).replace(" ", "-") or "CV"


def load_config(path: Path | None = None) -> Config:
    path = path or HERE / "config.toml"
    raw = tomllib.loads(path.read_text())
    p, a, b, po = raw["paths"], raw["ai"], raw["behaviour"], raw["portal"]
    tax = raw.get("taxonomy", {})

    def _abs(v: str) -> Path:
        q = Path(os.path.expanduser(v))
        return q if q.is_absolute() else (HERE / q)

    return Config(
        cv_root=_abs(p["cv_root"]),
        watch_dir=_abs(p["watch_dir"]),
        dupe_dir=_abs(p["dupe_dir"]),
        index_file=_abs(p["index_file"]),
        log_file=_abs(p["log_file"]),
        backend=a.get("backend", "claude_cli"),
        provider=a.get("provider", "anthropic"),
        base_url=a.get("base_url", ""),
        model=a["model"],
        cli_model=a.get("cli_model", "sonnet"),
        claude_bin=a.get("claude_bin", ""),
        timeout=int(a.get("timeout", 240)),
        key_file=_abs(a["key_file"]),
        max_tokens=int(a["max_tokens"]),
        owner_name=b.get("owner_name", ""),
        owner_surname=b.get("owner_surname", ""),
        file_prefix=b.get("file_prefix", "") or _slug_prefix(
            b.get("owner_name", ""), b.get("owner_surname", "")),
        branches=tax.get("branches") or DEFAULT_BRANCHES,
        roles=tax.get("roles") or DEFAULT_ROLES,
        lang_split=tax.get("lang_split") or DEFAULT_LANG_SPLIT,
        min_confidence=float(b["min_confidence"]),
        settle_seconds=float(b["settle_seconds"]),
        dry_run=bool(b["dry_run"]),
        host=po["host"],
        port=int(po["port"]),
        notify=raw.get("notify", {"enabled": False}),
        headline_noise=b.get("headline_noise", ""),
        seen_file=_abs(p.get("seen_file", "data/seen.json")),
        seen_ttl_days=float(b.get("seen_ttl_days", 30)),
        text_cache_dir=(_abs(p["text_cache_dir"])
                        if p.get("text_cache_dir") else None),
        index_workers=int(a.get("index_workers", 4)),
        # Summarising a CV is a far simpler job than deciding its branch and
        # specialty, so indexing can run on a cheaper model than filing.
        index_model=a.get("index_model", "") or a.get("cli_model", "sonnet"),
        index_batch_size=int(a.get("index_batch_size", 8)),
    )


# ------------------------------------------------------------ notifications --
def notify(cfg: Config, kind: str, title: str, body: str = "") -> None:
    """Desktop notification. Never raises — a missing notifier must not stop
    the daemon from doing its job.

    The gesture itself lives in desktop.py, which knows the three ways to make
    it: notify-send, osascript, or a PowerShell balloon.
    """
    n = cfg.notify
    if not n.get("enabled") or not n.get(f"on_{kind}", True):
        return
    try:
        import desktop
        desktop.notify(kind, title, body)
    except Exception:
        pass


def setup_logging(cfg: Config, name: str) -> logging.Logger:
    cfg.log_file.parent.mkdir(parents=True, exist_ok=True)
    log = logging.getLogger(name)
    if log.handlers:
        return log
    log.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s [%(name)s] %(message)s")
    fh = logging.FileHandler(cfg.log_file)
    fh.setFormatter(fmt)
    log.addHandler(fh)
    sh = logging.StreamHandler(sys.stderr)
    sh.setFormatter(fmt)
    log.addHandler(sh)
    return log


# --------------------------------------------------------------- pdf + text --
def pdf_text(path: Path, layout: bool = True) -> str:
    """Extract text with pdftotext. Returns '' on any failure."""
    cmd = ["pdftotext"] + (["-layout"] if layout else []) + [str(path), "-"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return r.stdout or ""
    except Exception:
        return ""


def _cache_key(path: Path) -> str:
    """Identity of a file's bytes, cheap to compute: path + size + mtime."""
    st = path.stat()
    return hashlib.md5(
        f"{path.resolve()}|{st.st_size}|{st.st_mtime_ns}".encode()
    ).hexdigest()


def pdf_text_cached(cfg: Config, path: Path) -> str:
    """pdf_text() with an on-disk cache.

    Extraction spawns a pdftotext process and is pure overhead when the same
    PDF is read again — the portal re-reads its five shortlisted CVs on every
    request, and the indexer re-reads the whole collection on every run. Keyed
    on size+mtime, so editing a PDF invalidates its entry by construction.
    """
    if not cfg.text_cache_dir:
        return pdf_text(path)
    try:
        cache = cfg.text_cache_dir / f"{_cache_key(path)}.txt"
        if cache.is_file():
            os.utime(cache, None)          # mark as used, for TTL pruning
            return cache.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return pdf_text(path)

    text = pdf_text(path)
    try:
        cfg.text_cache_dir.mkdir(parents=True, exist_ok=True)
        tmp = cache.with_suffix(f".{os.getpid()}.tmp")
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(cache)
    except OSError:
        pass                               # a cache we cannot write is not fatal
    return text


def prune_text_cache(cfg: Config, max_age_days: float = 30.0) -> int:
    """Drop cache entries untouched for a while. Returns how many went."""
    if not cfg.text_cache_dir or not cfg.text_cache_dir.is_dir():
        return 0
    cutoff, gone = time.time() - max_age_days * 86400, 0
    for f in cfg.text_cache_dir.glob("*.txt"):
        try:
            if f.stat().st_atime < cutoff:
                f.unlink()
                gone += 1
        except OSError:
            pass
    return gone


def content_sig(text: str) -> str:
    """Whitespace/case-insensitive signature — catches re-exports of one CV."""
    return hashlib.md5(
        re.sub(r"\s+", "", text).lower().encode("utf-8", "ignore")
    ).hexdigest()


def ascii_fold(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()


# Lines near the top of a CV that are contact details rather than a job title.
# Locations are person-specific, so the pattern is extendable from config via
# behaviour.headline_noise (a regex alternation, e.g. "paris|lyon|france").
_JUNK_BASE = r"@|\+\d[\d ]{6,}|\d{9}|linkedin|github|portfolio|protfolio|vercel"


def _junk_re(extra: str = "") -> re.Pattern:
    return re.compile(_JUNK_BASE + (f"|{extra}" if extra else ""), re.I)


_JUNK = _junk_re()


def headline_of(text: str, junk: re.Pattern | None = None) -> str:
    """The tagline under the name — usually line 2 of the PDF."""
    junk = junk or _JUNK
    lines = [re.sub(r"\s+", " ", l).strip() for l in text.split("\n")[:10]]
    lines = [l for l in lines if l]
    for l in lines[1:4]:
        if len(l) > 8 and l != "-" and not junk.search(l):
            return l
    m = re.search(
        r"(?:FORMATION|Profil|Profile|EDUCATION)[: ]+(.{15,120})",
        re.sub(r"\s+", " ", text),
        re.I,
    )
    return m.group(1).strip() if m else ""


def slug(s: str, maxlen: int = 28) -> str:
    s = ascii_fold(s)
    s = re.sub(r"[^A-Za-z0-9+ -]", " ", s)
    s = re.sub(r"\s*-\s*", "-", s.strip())
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s[:maxlen].strip("-")


# ------------------------------------------------------------------- index --
@dataclass
class CVRecord:
    path: str                 # relative to cv_root
    branch: str = ""
    specialty: str = ""
    role: str = ""
    lang: str = ""
    headline: str = ""
    summary: str = ""
    skills: list[str] = field(default_factory=list)
    sig: str = ""
    mtime: float = 0.0

    def compact(self) -> str:
        """One line for the stage-1 matching prompt — keeps tokens small."""
        sk = ", ".join(self.skills[:18])
        return (
            f"[{self.path}] stage={self.branch} | role={self.role} | "
            f"lang={self.lang} | title={self.headline} | skills={sk} | {self.summary}"
        )


class SeenStore:
    """Fingerprints of files already decided on, persisted across restarts.

    Without this the startup sweep re-classifies everything still sitting in the
    watch folder every time the daemon restarts — one model call each, to reach
    the same conclusion as last time. Entries for files that were filed never
    match again (the path is gone), so in practice this holds the PDFs you chose
    to leave where they were.
    """

    def __init__(self, cfg: Config):
        self.path = cfg.seen_file
        self.ttl = cfg.seen_ttl_days * 86400
        self._lock = threading.Lock()
        self._entries: dict[str, dict] = {}
        self.load()

    def load(self) -> None:
        if not self.path.is_file():
            return
        try:
            raw = json.loads(self.path.read_text())
        except (json.JSONDecodeError, OSError):
            return
        cutoff = time.time() - self.ttl
        self._entries = {k: v for k, v in raw.get("seen", {}).items()
                         if isinstance(v, dict) and v.get("ts", 0) > cutoff}

    def _save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(f".{os.getpid()}.tmp")
            tmp.write_text(json.dumps({"seen": self._entries}, indent=1))
            tmp.replace(self.path)
        except OSError:
            pass                       # losing the cache costs a call, not data

    def verdict(self, fp: str) -> str | None:
        with self._lock:
            e = self._entries.get(fp)
            return e.get("verdict") if e else None

    def remember(self, fp: str, verdict: str) -> None:
        with self._lock:
            self._entries[fp] = {"ts": time.time(), "verdict": verdict}
            if len(self._entries) > 5000:
                for k in sorted(self._entries,
                                key=lambda k: self._entries[k]["ts"])[:2500]:
                    del self._entries[k]
            self._save()

    def forget(self, fp: str) -> None:
        with self._lock:
            if self._entries.pop(fp, None) is not None:
                self._save()


class IndexLockTimeout(RuntimeError):
    pass


class Index:
    """The shared CV index.

    Three processes touch this file — the watcher, the indexer and the portal —
    so a plain load / mutate / save would lose writes: whoever saves last would
    overwrite entries the other added in between. Every write therefore goes
    through commit(), which takes an exclusive flock, RE-READS what is on disk,
    merges the caller's changes into that, and writes the result. The read is
    inside the lock, so nothing can slip in between it and the write.
    """

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.records: dict[str, CVRecord] = {}
        self.load()

    @property
    def _lockfile(self) -> Path:
        return self.cfg.index_file.with_suffix(".lock")

    @contextmanager
    def _flock(self, timeout: float = 60.0):
        try:
            with locking.exclusive(self._lockfile, timeout=timeout):
                yield
        except locking.LockBusy as e:
            raise IndexLockTimeout(
                f"index locked by another process for >{timeout:g}s "
                f"({self._lockfile})") from e

    def _read_disk(self) -> dict[str, CVRecord]:
        if not self.cfg.index_file.is_file():
            return {}
        try:
            data = json.loads(self.cfg.index_file.read_text())
        except json.JSONDecodeError:
            return {}
        return {r["path"]: CVRecord(**r) for r in data.get("cvs", [])}

    def _write_disk(self, records: dict[str, CVRecord]) -> None:
        payload = {"cvs": [asdict(r) for r in records.values()]}
        # Per-process temp name: a shared one lets two writers clobber each
        # other's staging file. Sibling path, so replace() stays atomic.
        tmp = self.cfg.index_file.with_suffix(f".{os.getpid()}.tmp")
        try:
            tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=1))
            tmp.replace(self.cfg.index_file)  # readers never see a partial file
        finally:
            tmp.unlink(missing_ok=True)

    def load(self) -> None:
        """Snapshot for reading. Readers need no lock — writes land atomically."""
        self.records = self._read_disk()

    def commit(self, upserts: dict[str, CVRecord] | None = None,
               prune: bool = False, timeout: float = 60.0) -> None:
        """Merge changes into whatever is on disk right now, under a lock.

        prune=True also drops entries whose PDF no longer exists. That check is
        made against the filesystem rather than against this process's stale
        snapshot, so a CV another process filed a moment ago is never pruned.
        """
        with self._flock(timeout):
            disk = self._read_disk()
            disk.update(upserts or {})
            if prune:
                for gone in [k for k in disk
                             if not (self.cfg.cv_root / k).is_file()]:
                    del disk[gone]
            self._write_disk(disk)
            self.records = disk

    def all_sigs(self) -> dict[str, str]:
        return {r.sig: r.path for r in self.records.values() if r.sig}

    def find_by_sig(self, sig: str) -> str | None:
        return self.all_sigs().get(sig)

    def pdf_paths(self) -> list[Path]:
        return sorted(
            p for p in self.cfg.cv_root.rglob("*.pdf")
            if "_Not-a-CV" not in p.parts and "_Duplicates-auto" not in p.parts
        )


# ---------------------------------------------------------------- AI layer --
class AIError(RuntimeError):
    pass


# -- backend A: the Claude Code CLI (uses your Claude subscription, no API key) --

# Variables that mark "we are inside a Claude Code session". A nested run must
# not inherit them, or it tries to attach to this session instead of starting
# its own.
_STRIP_ENV = (
    "CLAUDECODE", "CLAUDE_CODE_SESSION_ID", "CLAUDE_CODE_ENTRYPOINT",
    "CLAUDE_CODE_MESSAGING_SOCKET", "CLAUDE_CODE_MESSAGING_TOKEN",
    "CLAUDE_CODE_CHILD_SESSION", "CLAUDE_CODE_HOST_SESSION_ID",
    "ANTHROPIC_BASE_URL",
)


def _vkey(p: Path) -> tuple:
    return tuple(int(n) for n in re.findall(r"\d+", str(p))) or (0,)


def find_claude_bin() -> Path | None:
    """Newest Claude Code binary on this machine, or None."""
    cands: list[Path] = []
    base = Path.home() / ".config/Claude/claude-code"
    if base.is_dir():
        cands += [d / "claude" for d in base.iterdir()
                  if (d / "claude").is_file() and os.access(d / "claude", os.X_OK)]
    ext = Path.home() / ".vscode/extensions"
    if ext.is_dir():
        cands += [p for p in ext.glob(
            "anthropic.claude-code-*/resources/native-binary/claude")
            if os.access(p, os.X_OK)]
    import shutil as _sh
    w = _sh.which("claude")
    if w:
        cands.append(Path(w))
    return sorted(cands, key=_vkey)[-1] if cands else None


def _ask_cli(cfg: Config, system: str, user: str, timeout: int | None = None,
             model: str | None = None) -> str:
    binp = Path(cfg.claude_bin) if cfg.claude_bin else find_claude_bin()
    if not binp or not binp.is_file():
        raise AIError(
            "Claude Code CLI not found. Install it, or set ai.claude_bin in "
            "config.toml, or switch ai.backend to \"api\"."
        )
    import tempfile
    env = {k: v for k, v in os.environ.items() if k not in _STRIP_ENV}
    prompt = f"{system}\n\n{user}\n\nRespond with the JSON object only."
    # --restricted disables every built-in tool, so untrusted CV text read from
    # a PDF cannot cause any action — this is a pure text-in/text-out call.
    cmd = [str(binp), "-p", "--restricted", "--strict-mcp-config",
           "--model", model or cfg.cli_model]
    try:
        r = subprocess.run(
            cmd, input=prompt, capture_output=True, text=True, env=env,
            cwd=tempfile.gettempdir(), timeout=timeout or cfg.timeout,
        )
    except subprocess.TimeoutExpired as e:
        raise AIError(f"claude CLI timed out after {timeout or cfg.timeout}s") from e
    if r.returncode != 0:
        raise AIError(f"claude CLI failed ({r.returncode}): "
                      f"{(r.stderr or r.stdout or '').strip()[:300]}")
    if not r.stdout.strip():
        raise AIError("claude CLI returned nothing — usage limit reached? "
                      "Retry later, or lower ai.cli_model.")
    return r.stdout


# Any provider with an OpenAI-compatible /chat/completions endpoint works, which
# is nearly all of them. base_url is what distinguishes them; the request body
# is the same everywhere. Model names move faster than this table, so they are
# a suggestion the settings page lets you overwrite, and the test button is what
# confirms one exists.
#
# A smaller or cheaper model sorts CVs measurably worse: haiku was tried here
# and kept the student/graduate distinction on 3 CVs out of 4 where sonnet kept
# 4 of 4. The saving is real and so is the cost in accuracy.
PROVIDERS: dict[str, dict] = {
    "anthropic": {"label": "Anthropic (Claude)", "base": "",
                  "model": "claude-sonnet-5", "prefix": "sk-ant-",
                  "keys_at": "console.anthropic.com"},
    "openai": {"label": "OpenAI", "base": "https://api.openai.com/v1",
               "model": "gpt-4o-mini", "prefix": "sk-",
               "keys_at": "platform.openai.com/api-keys"},
    "google": {"label": "Google Gemini",
               "base": "https://generativelanguage.googleapis.com/v1beta/openai",
               "model": "gemini-2.0-flash", "prefix": "",
               "keys_at": "aistudio.google.com/apikey"},
    "mistral": {"label": "Mistral", "base": "https://api.mistral.ai/v1",
                "model": "mistral-small-latest", "prefix": "",
                "keys_at": "console.mistral.ai"},
    "groq": {"label": "Groq", "base": "https://api.groq.com/openai/v1",
             "model": "llama-3.3-70b-versatile", "prefix": "gsk_",
             "keys_at": "console.groq.com/keys"},
    "deepseek": {"label": "DeepSeek", "base": "https://api.deepseek.com/v1",
                 "model": "deepseek-chat", "prefix": "sk-",
                 "keys_at": "platform.deepseek.com"},
    "openrouter": {"label": "OpenRouter (plusieurs modèles, une seule clé)",
                   "base": "https://openrouter.ai/api/v1",
                   "model": "openai/gpt-4o-mini", "prefix": "sk-or-",
                   "keys_at": "openrouter.ai/keys"},
    "ollama": {"label": "Ollama, sur ta machine", "base": "http://localhost:11434/v1",
               "model": "llama3.1", "prefix": "", "no_key": True,
               "keys_at": "aucune clé : le modèle tourne chez toi"},
    "custom": {"label": "Autre (compatible OpenAI)", "base": "",
               "model": "", "prefix": "", "keys_at": ""},
}


def provider_base(cfg: "Config") -> str:
    return (cfg.base_url or PROVIDERS.get(cfg.provider, {}).get("base", "")).rstrip("/")


# -- backend C: anything speaking the OpenAI chat-completions shape ----------
def _ask_compatible(cfg: "Config", system: str, user: str, max_tokens: int | None,
                    model: str | None = None) -> str:
    """One chat completion over plain HTTP.

    httpx rather than a provider SDK on purpose: the endpoint is the same for
    every provider here, and one shared shape is what makes "any key" possible
    without a dependency per vendor.

    No response_format is sent. Several of these providers reject it, and
    ask_json already pulls the object out of whatever prose comes back.
    """
    import httpx
    base = provider_base(cfg)
    if not base:
        raise AIError("aucune adresse d'API : choisis un fournisseur, ou donne "
                      "l'adresse de base de celui que tu utilises")
    info = PROVIDERS.get(cfg.provider, {})
    key = cfg.api_key
    if not key and not info.get("no_key"):
        raise AIError(f"aucune clé enregistrée pour {info.get('label', cfg.provider)}")
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    payload = {
        "model": model or cfg.model,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content":
                      f"{user}\n\nRespond with the JSON object only."}],
        "max_tokens": max_tokens or cfg.max_tokens,
        "temperature": 0,
    }
    try:
        r = httpx.post(f"{base}/chat/completions", headers=headers, json=payload,
                       timeout=cfg.timeout)
    except httpx.RequestError as e:
        raise AIError(f"{base} injoignable : {e}") from e
    if r.status_code == 401 or r.status_code == 403:
        raise AIError("clé refusée par le fournisseur (401) : vérifie-la, et "
                      "qu'elle appartient bien au fournisseur sélectionné")
    if r.status_code == 404:
        raise AIError(f"modèle « {payload['model']} » inconnu chez ce fournisseur, "
                      f"ou adresse de base incorrecte ({base})")
    if r.status_code == 429:
        raise AIError("quota ou limite de débit atteinte chez le fournisseur")
    if r.status_code >= 400:
        raise AIError(f"HTTP {r.status_code} : {r.text[:200]}")
    try:
        return r.json()["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, ValueError) as e:
        raise AIError(f"réponse illisible du fournisseur : {r.text[:200]}") from e


# -- backend B: the Anthropic API (needs a paid API key, separate from Pro) --
def _ask_api(cfg: Config, system: str, user: str, max_tokens: int | None,
             model: str | None = None) -> str:
    key = cfg.api_key
    if not key:
        raise AIError("No Anthropic API key. Set $ANTHROPIC_API_KEY or write it "
                      f"to {cfg.key_file} — or use ai.backend = \"claude_cli\".")
    try:
        import anthropic
    except ImportError as e:  # pragma: no cover
        raise AIError("anthropic package missing — pip install anthropic") from e
    msg = anthropic.Anthropic(api_key=key).messages.create(
        model=model or cfg.model,
        max_tokens=max_tokens or cfg.max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(b.text for b in msg.content if b.type == "text")


def ask_json(cfg: Config, system: str, user: str, max_tokens: int | None = None,
             model: str | None = None) -> dict:
    """One-shot call that must come back as a JSON object.

    `model` overrides the configured one — indexing uses a cheaper model than
    filing, because summarising is easier than classifying.
    """
    if cfg.backend == "claude_cli":
        body = _ask_cli(cfg, system, user, model=model)
    elif cfg.provider == "anthropic":
        body = _ask_api(cfg, system, user, max_tokens, model=model)
    else:
        body = _ask_compatible(cfg, system, user, max_tokens, model=model)
    for obj in json_objects(body):
        try:
            return json.loads(obj)
        except json.JSONDecodeError:
            continue
    raise AIError(f"model did not return JSON: {body.strip()[:300]}")


def json_objects(text: str) -> list[str]:
    """Every balanced {...} in the text, biggest first.

    A greedy match from the first brace to the last one is wrong whenever the
    model writes anything else: a sentence containing a brace, or an example
    object before the answer, and the span covers both and parses as neither.
    Measured on a real run, that lost 2 evaluations out of 8.

    Braces inside strings are not structure, so the scan tracks quoting and
    escapes rather than counting characters.
    """
    text = re.sub(r"^\s*```(?:json)?|```\s*$", "", text.strip(), flags=re.M)
    spans, stack, in_str, esc = [], [], False, False
    for i, ch in enumerate(text):
        if esc:
            esc = False
        elif in_str:
            if ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch == "{":
            stack.append(i)
        elif ch == "}" and stack:
            start = stack.pop()
            if not stack:                       # a complete top-level object
                spans.append((start, i + 1))
    out = [text[a:b] for a, b in spans]
    if stack:                                   # truncated: try what there is
        out.append(text[stack[0]:])
    return sorted(out, key=len, reverse=True)


# --------------------------------------------------------- classify one PDF --
CLASSIFY_SYSTEM = """You sort a job-seeker's CV/résumé PDFs into a filing system.

The owner of the collection is {owner}. Read the document text and
answer ONLY with a JSON object, no prose.

Fields:
  is_cv        true if the document is a CV/résumé (not a cover letter, diploma,
               project brief, invoice, or article).
  is_owner     true only if the CV belongs to {owner}. Someone else's
               CV must be false.
  branch       one of the branch keys given below.
  specialty    one of the specialty folders given below, whichever best matches
               the TARGET ROLE the CV is written for. Judge from the whole
               document — profile paragraph, skills, projects — not the title
               alone, which is often stale or misleading.
  new_specialty  if none of the folders fit, a new PascalCase-with-hyphens folder
               name, else "".
  qualifier    up to 3 hyphen-joined technologies or sectors that distinguish
               this CV from others aiming at the same role (e.g. "RAG-LangGraph",
               "Azure-Cloud", "Automobile"). "" if nothing stands out.
  lang         "FR" or "EN" — the language the CV is written in.
  headline     the tagline under the name, verbatim; "" if absent.
  summary      one sentence, max 22 words, describing what this CV is pitching.
  skills       up to 20 concrete technologies named in the CV.
  confidence   0.0-1.0, how sure you are of branch + specialty.
  reason       one short sentence justifying branch and specialty.
"""


def classify_pdf(cfg: Config, path: Path, text: str | None = None) -> dict:
    """Ask the model to place one PDF. Pass `text` if you already extracted it,
    so a caller that pre-screened the document does not pay for it twice."""
    if text is None:
        text = pdf_text(path)
    if len(text.strip()) < 120:
        return {"is_cv": False, "reason": "no extractable text (scan or empty)",
                "confidence": 1.0}

    from datetime import date
    branches = "\n".join(f"  {k}: {v}" for k, v in cfg.branches.items())
    specialties = "\n".join(f"  {k}" for k in cfg.roles)
    user = (
        f"TODAY IS {date.today().isoformat()} — a degree period ending before "
        f"today is finished.\n\nBRANCHES:\n{branches}\n\n{BRANCH_RULE}\n\n"
        f"SPECIALTY FOLDERS:\n{specialties}\n\n"
        f"--- DOCUMENT TEXT (truncated) ---\n{text[:14000]}"
    )
    owner = f"{cfg.owner_name} {cfg.owner_surname}".strip() or "the collection owner"
    out = ask_json(cfg, CLASSIFY_SYSTEM.format(owner=owner), user)
    out["_text"] = text
    out["_sig"] = content_sig(text)
    return out


def destination(cfg: Config, res: dict) -> tuple[Path, str]:
    """Where a classified CV belongs, and what it should be called."""
    specialty = (res.get("specialty") or res.get("new_specialty")
                 or next(iter(cfg.roles)))
    branch = res.get("branch") or list(cfg.branches)[-1]
    lang = (res.get("lang") or "FR").upper()
    role = cfg.roles.get(specialty) or slug(specialty, 30)

    folder = cfg.cv_root / branch / specialty
    split = cfg.lang_split.get(specialty)
    if split:
        folder = folder / split.get(lang, next(iter(split.values())))

    qual = slug(res.get("qualifier") or "", 28)
    base = f"{cfg.file_prefix}_{role}" + (f"_{qual}" if qual else "") + f"_{lang}"
    return folder, unique_name(folder, base)


def unique_name(folder: Path, base: str) -> str:
    name, i = f"{base}.pdf", 2
    while (folder / name).exists():
        name = f"{base}_{i}.pdf"
        i += 1
    return name
