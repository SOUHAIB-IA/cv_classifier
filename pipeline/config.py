"""Pipeline configuration: pipeline.toml (behaviour) and profile.toml (you).

profile.toml holds personal data used to pre-fill application forms. It is
gitignored and never logged.
"""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _abs(v: str) -> Path:
    q = Path(os.path.expanduser(v))
    return q if q.is_absolute() else ROOT / q


@dataclass
class PipelineConfig:
    db: Path
    lock_file: Path
    applications_dir: Path
    tracker_xlsx: Path
    structured_dir: Path

    daily_match_budget: int
    max_matches_per_run: int
    threshold_auto: int
    threshold_review: int

    prefilter_min: float
    title_include: list[str]
    title_exclude: list[str]
    location_include: list[str]
    location_exclude: list[str]
    languages: list[str]
    max_age_days: int
    max_years_required: int
    work_authorization: list[str] | None

    request_delay: float
    boards_per_run: int
    board_min_interval_min: int
    http_timeout: float
    boards: dict[str, list[str]] = field(default_factory=dict)

    tailor_enabled: bool = True
    chrome_bin: str = ""
    register_tailored: bool = False
    max_pages: int = 1
    photo: Path | None = None
    photo_langs: list[str] = field(default_factory=list)
    cv_style: str = "calibri"

    submit_channel: str = "chrome"
    submit_hosts: list[str] = field(default_factory=list)


def load(path: Path | None = None) -> PipelineConfig:
    path = path or ROOT / "pipeline.toml"
    if not path.is_file():
        raise FileNotFoundError(
            f"{path} not found — copy pipeline.example.toml to pipeline.toml")
    raw = tomllib.loads(path.read_text())
    p, b = raw.get("pipeline", {}), raw.get("budget", {})
    t, f = raw.get("thresholds", {}), raw.get("prefilter", {})
    s, tl = raw.get("sourcing", {}), raw.get("tailor", {})
    sm = raw.get("submit", {})
    srcs = raw.get("sources", {})

    return PipelineConfig(
        db=_abs(p.get("db", "data/pipeline.db")),
        lock_file=_abs(p.get("lock_file", "data/pipeline.lock")),
        applications_dir=_abs(p.get("applications_dir", "applications")),
        tracker_xlsx=_abs(p.get("tracker_xlsx", "data/job_tracker.xlsx")),
        structured_dir=_abs(p.get("structured_dir", "data/structured")),
        daily_match_budget=int(b.get("daily_match_budget", 20)),
        max_matches_per_run=int(b.get("max_matches_per_run", 5)),
        threshold_auto=int(t.get("auto", 70)),
        threshold_review=int(t.get("review", 40)),
        prefilter_min=float(f.get("min_score", 0.25)),
        title_include=[x.lower() for x in f.get("title_include", [])],
        title_exclude=[x.lower() for x in f.get("title_exclude", [])],
        location_include=[x.lower() for x in f.get("location_include", [])],
        location_exclude=[x.lower() for x in f.get("location_exclude", [])],
        languages=[x.lower() for x in f.get("languages", ["fr", "en"])],
        max_age_days=int(f.get("max_age_days", 45)),
        max_years_required=int(f.get("max_years_required", 0)),
        work_authorization=([x.lower() for x in f["work_authorization"]]
                            if "work_authorization" in f else None),
        request_delay=float(s.get("request_delay_seconds", 2.0)),
        boards_per_run=int(s.get("boards_per_run", 10)),
        board_min_interval_min=int(s.get("board_min_interval_minutes", 180)),
        http_timeout=float(s.get("timeout_seconds", 20)),
        boards={k: list(v.get("boards", [])) for k, v in srcs.items()},
        tailor_enabled=bool(tl.get("enabled", True)),
        chrome_bin=tl.get("chrome_bin", ""),
        register_tailored=bool(tl.get("register_in_cv_library", False)),
        max_pages=int(tl.get("max_pages", 1)),
        photo=_abs(tl["photo"]) if tl.get("photo") else None,
        photo_langs=[x.lower() for x in tl.get("photo_langs", ["fr", "en"])],
        cv_style=tl.get("style", "calibri"),
        submit_channel=sm.get("browser_channel", "chrome"),
        submit_hosts=[h.lower() for h in sm.get("allowed_hosts", [
            "boards.greenhouse.io", "job-boards.greenhouse.io",
            "jobs.lever.co", "jobs.ashbyhq.com"])],
    )


def load_profile(path: Path | None = None) -> dict:
    """Your identity for form pre-fill, merged with the per-track account.

    Returns {"base": {...}, "fr": {...}, "en": {...}} where fr/en already have
    base merged in, so callers just pick the track.
    """
    path = path or ROOT / "profile.toml"
    if not path.is_file():
        return {"base": {}, "fr": {}, "en": {}}
    raw = tomllib.loads(path.read_text())
    base = raw.get("identity", {})
    acc = raw.get("accounts", {})
    return {"base": base,
            "fr": {**base, **acc.get("fr", {})},
            "en": {**base, **acc.get("en", {})}}
