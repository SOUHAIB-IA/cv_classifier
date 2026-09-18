"""Free first-pass screening: decides which jobs deserve a model evaluation.

A model evaluation costs two calls through cv-router. At a few thousand
postings across the configured boards and a Claude plan's usage limits, only a
small fraction can be evaluated per day — so every posting is screened here
first, with no model call at all.

Two stages:
  hard filters   wrong title family, location, language or age -> not a
                 candidate at all (no tracker row, it was never in the running)
  soft score     how much of YOUR skill vocabulary the ad uses, in [0, 1].
                 The vocabulary is read from cv-router's index — the skills the
                 model extracted from your own CVs, weighted by how many CVs
                 carry them — so the screen tracks what you actually offer.
"""
from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from datetime import date

import cvrouter as cr

from .config import PipelineConfig

# Places are separated by any of these. Commas matter: Ashby lists
# "France, Europe, Munich, Paris (remote)".
_SPLIT = re.compile(r"\s*(?:\||;|/|,| or | ou |\n)\s*")
# Work modes, not places. "Riyadh (remote)" is remote *in Riyadh*.
_MODE = re.compile(r"\b(remote|hybrid|hybride|on[- ]?site|teletravail|full[- ]remote)\b")
_SYNONYMS = {
    "scikit-learn": ["sklearn", "scikit learn"],
    "large language models": ["llm", "llms"],
    "llms": ["llm", "large language model"],
    "machine learning": ["ml"],
    "retrieval-augmented generation": ["rag"],
    "ci/cd": ["cicd", "continuous integration"],
    "kubernetes": ["k8s"],
}


# "3+ years", "3-5 years", "at least 3 years", "5 ans d'expérience", "3 ans minimum"
_YEARS = re.compile(
    r"(?:at least|minimum|min\.?|over|more than|plus de|au moins)?\s*"
    r"(\d{1,2})\s*\+?\s*(?:-|to|a|à)?\s*(?:\d{1,2})?\s*\+?\s*"
    r"(?:years?|yrs?|ans|annees)\b")
_EXP_CONTEXT = re.compile(r"experien|exp\b|track record|building|in (?:a|an|the) ", re.I)

# The ad requires the right to work somewhere...
_AUTH_REQ = re.compile(
    r"eligib\w* to work|right to work|(?:authori[sz]ed|legally (?:allowed|able|authori[sz]ed))"
    r" to work|work (?:authori[sz]ation|permit)|must (?:be (?:based|located|residing)|reside) in|"
    r"autorisation de travail|titre de sejour|permis de travail|autorise a travailler|"
    r"eligible a travailler")
# ...and whether it helps you get it. Negations are checked first, because
# "without visa sponsorship" contains "visa sponsorship".
_NO_SPONSOR = re.compile(
    r"(?:without|no|not|unable to|cannot|can't|do not|don't|does not)\s+(?:\w+\s+){0,3}"
    r"(?:visa\s+)?sponsor|pas de (?:sponsoring|parrainage)|sans (?:sponsoring|parrainage)")
_SPONSOR = re.compile(
    r"visa sponsorship|sponsor (?:your |a )?visa|we (?:can |will |do )?sponsor|"
    r"sponsorship (?:is )?(?:available|offered|provided)|relocation (?:support|package|"
    r"assistance|help)|help (?:with|you) relocat|parrainage de visa|prise en charge du visa|"
    r"accompagnement (?:a la )?relocalisation")


def required_years(text: str) -> int | None:
    """The smallest number of years of experience the ad asks for, if any.
    Smallest, not largest: "5 years of software, 2 of ML" should not be read
    as a 5-year bar."""
    t = _fold(text)
    found = []
    for m in _YEARS.finditer(t):
        n = int(m.group(1))
        window = t[max(0, m.start() - 80):m.end() + 80]
        if 1 <= n <= 20 and _EXP_CONTEXT.search(window):
            found.append(n)
    return min(found) if found else None


def work_permit_blocked(text: str, allowed: list[str]) -> str | None:
    """Why the ad's work-authorisation requirement rules you out, or None.

    Blocked only when the ad explicitly requires the right to work, offers no
    sponsorship or relocation help, and does not name a country you are
    already allowed to work in.
    """
    t = _fold(text)
    m = _AUTH_REQ.search(t)
    if not m:
        return None
    if _SPONSOR.search(t) and not _NO_SPONSOR.search(t):
        return None
    window = t[max(0, m.start() - 160):m.end() + 200]
    if any(re.search(rf"\b{re.escape(_fold(c))}\b", window) for c in allowed):
        return None
    snippet = re.sub(r"\s+", " ", t[m.start():m.end() + 40]).strip()[:60]
    return f"requires the right to work ('{snippet}')"


def _fold(s: str) -> str:
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()


class Screener:
    def __init__(self, pcfg: PipelineConfig, cfg: cr.Config, idx: cr.Index | None = None):
        self.p = pcfg
        idx = idx or cr.Index(cfg)
        counts: Counter[str] = Counter()
        for rec in idx.records.values():
            for sk in {_fold(s).strip() for s in rec.skills if s and len(s) > 1}:
                counts[sk] += 1
        # log-damped: a skill on 60 CVs is core, but should not drown out the
        # rest of the stack
        self.weights = {k: math.log1p(v) for k, v in counts.most_common(80)}
        top = sorted(self.weights.values(), reverse=True)[:25]
        self.norm = sum(top) or 1.0
        self.patterns = {k: self._pattern(k) for k in self.weights}
        self._cache: dict[str, re.Pattern] = {}

    @staticmethod
    def _pattern(term: str) -> re.Pattern:
        alts = [term] + _SYNONYMS.get(term, [])
        body = "|".join(re.escape(a) for a in alts)
        return re.compile(rf"(?<![a-z0-9])(?:{body})(?![a-z0-9])")

    # -- hard filters ---------------------------------------------------------
    @staticmethod
    def term_re(term: str) -> re.Pattern:
        """Whole-word match; a trailing * makes it a prefix.

        Plain substrings are useless on short tokens: "ia" is inside "Arabia",
        "intern" inside "Internal" and "International".
        """
        t = _fold(term).strip()
        prefix = t.endswith("*")
        body = re.escape(t.rstrip("*").strip())
        return re.compile(rf"(?<![a-z0-9]){body}" + (r"[a-z0-9]*" if prefix else r"(?![a-z0-9])"))

    def _any(self, terms: list[str], text: str) -> str | None:
        for t in terms:
            if t not in self._cache:
                self._cache[t] = self.term_re(t)
            if self._cache[t].search(text):
                return t
        return None

    def _title_ok(self, title: str) -> tuple[bool, str]:
        t = _fold(title)
        hit = self._any(self.p.title_exclude, t)
        if hit:
            return False, f"title excludes '{hit}'"
        if self.p.title_include and not self._any(self.p.title_include, t):
            return False, "title outside target roles"
        return True, ""

    @staticmethod
    def places(loc: str) -> tuple[list[str], bool]:
        """Split a location into places, and whether it is remote at all.

        The work mode is stripped from each place, so "Riyadh (remote)" is the
        place "riyadh", remote — a remote job restricted to somewhere is only as
        good as that somewhere.
        """
        segs = [x for x in _SPLIT.split(_fold(loc)) if x.strip()]
        remote = any(re.search(r"\b(remote|teletravail|full[- ]remote)\b", x) for x in segs)
        out = []
        for x in segs:
            x = _MODE.sub(" ", re.sub(r"[()\[\]]", " ", x))
            x = re.sub(r"^[\s\-:]+|[\s\-:]+$", "", re.sub(r"\s+", " ", x))
            if x:
                out.append(x)
        return out, remote

    def _location_ok(self, loc: str) -> tuple[bool, str]:
        if not loc.strip():
            return True, "no location given"
        places, remote = self.places(loc)
        if not places:                      # just "Remote"
            return True, "unrestricted remote"
        # "San Francisco | Paris" is fine if any one place is fine.
        for place in places:
            if self._any(self.p.location_exclude, place):
                continue
            if not self.p.location_include or self._any(self.p.location_include, place):
                return True, ""
        return False, f"location '{loc[:60]}'"

    def hard_filter(self, job: dict) -> tuple[bool, str]:
        ok, why = self._title_ok(job["title"])
        if not ok:
            return False, why
        ok, why = self._location_ok(job.get("location") or "")
        if not ok:
            return False, why
        if self.p.languages and job.get("language") and job["language"] not in self.p.languages:
            return False, f"language {job['language']}"
        jd = job.get("jd_text") or ""
        if self.p.max_years_required:
            yrs = required_years(jd)
            if yrs is not None and yrs > self.p.max_years_required:
                return False, f"asks for {yrs}+ years of experience"
        if self.p.work_authorization is not None:
            why = work_permit_blocked(jd, self.p.work_authorization)
            if why:
                return False, why
        posted = job.get("posted_date") or ""
        if posted and self.p.max_age_days:
            try:
                age = (date.today() - date.fromisoformat(posted[:10])).days
                if age > self.p.max_age_days:
                    return False, f"posted {age} days ago"
            except ValueError:
                pass
        return True, ""

    # -- soft score -----------------------------------------------------------
    def score(self, job: dict) -> tuple[float, list[str]]:
        text = _fold(f"{job['title']}\n{job['jd_text']}")
        hit = [k for k, pat in self.patterns.items() if pat.search(text)]
        skill = min(1.0, sum(self.weights[k] for k in hit) / self.norm)
        title = 1.0 if self._any(self.p.title_include, _fold(job["title"])) else 0.0
        return round(0.75 * skill + 0.25 * title, 3), sorted(hit, key=lambda k: -self.weights[k])
