"""SQLite storage for the job pipeline — the single source of truth.

Tables mirror the spec's data contracts:
  jobs          JobRecord, plus pipeline bookkeeping (stage, prefilter score)
  matches       MatchResult
  applications  ApplicationRecord — one row per processed job, skips included.
                This IS the tracker; job_tracker.xlsx is exported from it.
  boards        per-board fetch times, so sourcing spreads load over the day
  events        run log and the model-call budget ledger

The xlsx is a view, not the store: spreadsheets are not safe to append to from
several processes, and they cannot be queried for the weekly rollup.
"""
from __future__ import annotations

import fcntl
import json
import re
import sqlite3
import unicodedata
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
  id              TEXT PRIMARY KEY,         -- "<source>:<source job id>"
  source          TEXT NOT NULL,            -- greenhouse|lever|ashby|workday|indeed|manual
  board           TEXT,                     -- company slug on that source
  company         TEXT NOT NULL,
  title           TEXT NOT NULL,
  location        TEXT,
  jd_text         TEXT NOT NULL,
  apply_url       TEXT,
  jd_url          TEXT,
  language        TEXT,                     -- fr|en
  posted_date     TEXT,
  status          TEXT NOT NULL DEFAULT 'new',      -- new|processed (spec)
  stage           TEXT NOT NULL DEFAULT 'sourced',  -- finer pipeline position
  dedupe_key      TEXT,
  prefilter_score REAL,
  first_seen      TEXT NOT NULL,
  updated_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS jobs_status ON jobs(status, stage);
CREATE INDEX IF NOT EXISTS jobs_dedupe ON jobs(dedupe_key);

CREATE TABLE IF NOT EXISTS matches (
  job_id              TEXT PRIMARY KEY REFERENCES jobs(id),
  fit_score           INTEGER,
  ats_score           INTEGER,
  recommended_variant TEXT,
  recommended_account TEXT,                 -- fr|en
  suggested_edits     TEXT,                 -- JSON list
  decision            TEXT,                 -- auto|review|skip
  reason              TEXT,
  raw                 TEXT,                 -- full matcher output, JSON
  created_at          TEXT
);

CREATE TABLE IF NOT EXISTS applications (
  job_id      TEXT PRIMARY KEY REFERENCES jobs(id),
  date        TEXT,
  company     TEXT,
  role        TEXT,
  source      TEXT,
  jd_url      TEXT,
  language    TEXT,
  account     TEXT,
  cv_variant  TEXT,
  cv_filename TEXT,
  fit_score   INTEGER,
  decision    TEXT,                         -- auto|review|skip
  status      TEXT,                         -- see STATUSES
  notes       TEXT,
  dedupe_key  TEXT,
  updated_at  TEXT
);
CREATE INDEX IF NOT EXISTS apps_dedupe ON applications(dedupe_key, status);

CREATE TABLE IF NOT EXISTS boards (
  source       TEXT NOT NULL,
  board        TEXT NOT NULL,
  last_fetched TEXT,
  last_error   TEXT,
  n_jobs       INTEGER,
  PRIMARY KEY (source, board)
);

CREATE TABLE IF NOT EXISTS events (
  ts     TEXT NOT NULL,
  kind   TEXT NOT NULL,                     -- source|prefilter|match|route|tailor|submit|error
  job_id TEXT,
  detail TEXT
);
CREATE INDEX IF NOT EXISTS events_kind_ts ON events(kind, ts);
"""

# skipped   decided not to apply (score, prefilter, duplicate)
# review    waiting for you in the review queue
# pending   approved / auto — CV being tailored
# draft     CV tailored automatically, waiting for you to read and validate it
# staged    CV validated by you, form waiting for your click
# applied   you clicked submit
# rejected / interview / offer / withdrawn   outcomes you record afterwards
STATUSES = ("skipped", "review", "pending", "draft", "staged", "applied",
            "rejected", "interview", "offer", "withdrawn")
ACTIVE = ("pending", "draft", "staged", "applied", "interview", "offer")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def today() -> str:
    return date.today().isoformat()


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    s = re.sub(r"\(.*?\)", " ", s.lower())
    s = re.sub(r"\b(h/f|f/h|m/f|m/w/d|w/m/d|remote|hybrid|full[- ]time|cdi)\b", " ", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def dedupe_key(company: str, title: str) -> str:
    """company + title, normalised so a re-post or a cross-post collides."""
    return f"{_norm(company)}|{_norm(title)}"


class DB:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.conn = sqlite3.connect(path, timeout=30, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.executescript(SCHEMA)

    def close(self) -> None:
        self.conn.close()

    def scratch_copy(self) -> "DB":
        """An in-memory copy to rehearse a run on: every stage really executes,
        so a dry run shows what would happen downstream, and nothing on disk
        changes."""
        mem = DB.__new__(DB)
        mem.path = Path(":memory:")
        mem.conn = sqlite3.connect(":memory:", isolation_level=None)
        mem.conn.row_factory = sqlite3.Row
        self.conn.backup(mem.conn)
        return mem

    @contextmanager
    def tx(self):
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            yield self.conn
            self.conn.execute("COMMIT")
        except Exception:
            self.conn.execute("ROLLBACK")
            raise

    def q(self, sql: str, *args) -> list[sqlite3.Row]:
        return self.conn.execute(sql, args).fetchall()

    def one(self, sql: str, *args) -> sqlite3.Row | None:
        return self.conn.execute(sql, args).fetchone()

    # -- events / budget ---------------------------------------------------
    def event(self, kind: str, job_id: str | None = None, **detail) -> None:
        self.conn.execute(
            "INSERT INTO events(ts, kind, job_id, detail) VALUES (?,?,?,?)",
            (now(), kind, job_id, json.dumps(detail, ensure_ascii=False)))

    def matches_today(self) -> int:
        """Jobs sent to the model today (local date) — the daily budget ledger."""
        row = self.one(
            "SELECT COUNT(*) FROM events WHERE kind='match' "
            "AND date(ts, 'localtime') = date('now', 'localtime')")
        return row[0] if row else 0

    # -- jobs ----------------------------------------------------------------
    def upsert_job(self, job: dict) -> bool:
        """Insert a newly sourced job. Returns True if it was new.

        Existing jobs keep their pipeline state; only the posting's own fields
        are refreshed, so a re-fetch never re-queues a job already decided on.
        """
        ts = now()
        cur = self.conn.execute("SELECT 1 FROM jobs WHERE id=?", (job["id"],))
        if cur.fetchone():
            self.conn.execute(
                "UPDATE jobs SET title=?, location=?, jd_text=?, apply_url=?, "
                "jd_url=?, updated_at=? WHERE id=?",
                (job["title"], job.get("location", ""), job["jd_text"],
                 job.get("apply_url", ""), job.get("jd_url", ""), ts, job["id"]))
            return False
        self.conn.execute(
            "INSERT INTO jobs(id, source, board, company, title, location, jd_text,"
            " apply_url, jd_url, language, posted_date, status, stage, dedupe_key,"
            " first_seen, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,'new','sourced',?,?,?)",
            (job["id"], job["source"], job.get("board", ""), job["company"],
             job["title"], job.get("location", ""), job["jd_text"],
             job.get("apply_url", ""), job.get("jd_url", ""),
             job.get("language", ""), job.get("posted_date", ""),
             dedupe_key(job["company"], job["title"]), ts, ts))
        return True

    def set_stage(self, job_id: str, stage: str, status: str | None = None,
                  **extra) -> None:
        cols = ["stage=?", "updated_at=?"]
        vals: list = [stage, now()]
        if status:
            cols.append("status=?")
            vals.append(status)
        for k, v in extra.items():
            cols.append(f"{k}=?")
            vals.append(v)
        vals.append(job_id)
        self.conn.execute(f"UPDATE jobs SET {', '.join(cols)} WHERE id=?", vals)

    # -- matches / applications -----------------------------------------------
    def save_match(self, job_id: str, m: dict) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO matches(job_id, fit_score, ats_score,"
            " recommended_variant, recommended_account, suggested_edits, decision,"
            " reason, raw, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (job_id, m.get("fit_score"), m.get("ats_score"),
             m.get("recommended_variant", ""), m.get("recommended_account", ""),
             json.dumps(m.get("suggested_edits", []), ensure_ascii=False),
             m.get("decision", ""), m.get("reason", ""),
             json.dumps(m.get("raw", {}), ensure_ascii=False), now()))

    def upsert_application(self, job_id: str, **fields) -> None:
        """Write the tracker row for a job. Unspecified fields keep their value."""
        job = self.one("SELECT * FROM jobs WHERE id=?", job_id)
        if not job:
            raise KeyError(job_id)
        existing = self.one("SELECT * FROM applications WHERE job_id=?", job_id)
        row = dict(existing) if existing else {
            "job_id": job_id, "date": today(), "company": job["company"],
            "role": job["title"], "source": job["source"],
            "jd_url": job["jd_url"] or job["apply_url"],
            "language": job["language"], "account": job["language"],
            "cv_variant": "", "cv_filename": "", "fit_score": None,
            "decision": "", "status": "", "notes": "",
            "dedupe_key": job["dedupe_key"],
        }
        if "status" in fields and fields["status"] not in STATUSES:
            raise ValueError(f"unknown status {fields['status']!r}; "
                             f"one of {', '.join(STATUSES)}")
        row.update(fields)
        row["updated_at"] = now()
        cols = list(row)
        self.conn.execute(
            f"INSERT OR REPLACE INTO applications({', '.join(cols)}) "
            f"VALUES ({', '.join('?' * len(cols))})", [row[c] for c in cols])

    def already_applied(self, dkey: str, exclude_job: str = "") -> sqlite3.Row | None:
        """The duplicate guard: an active application for the same company+title."""
        return self.one(
            f"SELECT * FROM applications WHERE dedupe_key=? AND job_id<>? "
            f"AND status IN ({', '.join('?' * len(ACTIVE))}) LIMIT 1",
            dkey, exclude_job, *ACTIVE)


@contextmanager
def run_lock(path: Path):
    """One pipeline run at a time. A second scheduled run exits instead of
    racing the first over the same jobs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fh = open(path, "w")
    try:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        fh.close()
        raise RuntimeError("another pipeline run is in progress")
    try:
        yield
    finally:
        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        fh.close()
