"""Headless job matching: a job description in, the best CV and its edits out.

This is the logic that used to live inside portal.py, lifted out so that the
portal UI, the CLI (match.py) and the job pipeline's orchestrator all run the
exact same thing.

Two model calls per job, whatever the size of the collection:
  1. the compact index (one line per CV) -> shortlist of 5
  2. the full text of those 5 -> the pick, the scores, the edits
"""
from __future__ import annotations

import re

import cvrouter as cr

SHORTLIST_SYSTEM = """You match a job ad against a library of CVs belonging to one
person. Each library line is: [path] stage=... role=... lang=... title=... skills=... summary.

Pick the 5 lines whose CV is most likely the best to send for this job.

Weigh, in order:
 (1) career stage — a permanent job (CDI / full-time / permanent) needs a
     graduate CV, an internship (stage / PFE / intern) needs the student one;
 (2) language — a job ad written in French should get a French CV and one in
     English an English CV, unless the ad asks otherwise;
 (3) how much of the ad's required stack the CV actually evidences;
 (4) how close the CV's target role is to the advertised role.

Return ONLY JSON: {"shortlist": ["path1", ...], "stage_wanted": "...",
"job_language": "fr|en", "reason": "one sentence"}"""

ANALYSE_SYSTEM = """You are an expert technical recruiter and ATS specialist
helping one candidate choose and adapt a CV.

You get a job ad and the FULL text of several of the candidate's CVs. Judge each
on its whole content — profile, skills, experience, projects — never on its title
alone, which is often stale.

Return ONLY a JSON object:
{
 "best": {"path": "...", "why": "2-3 sentences citing concrete evidence from that CV"},
 "runner_up": {"path": "...", "why": "1-2 sentences"},
 "ats_score": 0-100,
 "score_reason": "one sentence on what the ATS score reflects",
 "fit_score": 0-100,
 "fit_reason": "one or two sentences naming what drives the fit score up or down",
 "job_language": "fr|en",
 "matched_keywords":  ["terms the ad requires that this CV already contains"],
 "missing_keywords":  ["terms the ad requires that are absent or too weak"],
 "key_changes": [
   {"section": "e.g. Titre / Profil / Compétences / Expérience",
    "current": "what the CV says now, quoted EXACTLY, or '(absent)'",
    "suggested": "the exact replacement text to paste in",
    "why": "which line of the ad this satisfies",
    "priority": "high|medium|low"}
 ],
 "red_flags": ["things that could get it filtered out or hurt in review"],
 "cover_letter_hook": "2 sentences the candidate can open a cover letter with"
}

ats_score and fit_score measure different things — keep them independent:
- ats_score: how much of the ad's vocabulary the best CV already covers. Keyword
  coverage, nothing else.
- fit_score: how likely a recruiter is to shortlist this candidate for this job,
  once the edits are applied. Judge role match, required stack evidenced in the
  CV, seniority, contract type against career stage, location and remote
  policy, and required languages. Apply these caps, which override everything:
    * the ad requires clearly more years of experience than the CV shows -> <= 35
    * the role is on-site in a country the CV gives no path to (no remote,
      no relocation mentioned in the ad) -> <= 35
    * a language the ad requires is not in the CV -> <= 30
    * the role is a different profession (sales, legal, clinical...) -> <= 15
  A CV that covers every keyword can still fit badly; say so.

Rules for key_changes: give 4-8 of them, each concretely actionable with text the
candidate can copy. "current" must be quoted verbatim from the CV so it can be
found and replaced mechanically. Never invent experience the CVs do not support —
rephrase, surface, and reorder what is already there. Write them in the CV's own
language."""


def _clamp(v, lo=0, hi=100) -> int:
    try:
        return max(lo, min(hi, int(round(float(v)))))
    except (TypeError, ValueError):
        return 0


def match_job(cfg: cr.Config, jd_text: str, *, title: str = "", company: str = "",
              location: str = "", idx: cr.Index | None = None,
              text_of=None) -> dict:
    """Pick the best CV for one job and describe the edits it needs.

    Returns the full analysis plus the two keys the pipeline contract names:
      best_variant     path of the chosen CV, relative to cv_root
      suggested_edits  the key_changes list
    Raises cr.AIError when the model backend is unavailable.
    """
    idx = idx or cr.Index(cfg)
    if not idx.records:
        raise cr.AIError("Index is empty — run: python indexer.py")
    text_of = text_of or (lambda rel: cr.pdf_text_cached(cfg, cfg.cv_root / rel))

    header = "\n".join(x for x in (
        f"Title: {title}" if title else "",
        f"Company: {company}" if company else "",
        f"Location: {location}" if location else "",
    ) if x)
    job = (header + "\n\n" if header else "") + jd_text[:9000]

    lines = [r.compact() for r in idx.records.values()]
    short = cr.ask_json(
        cfg, SHORTLIST_SYSTEM,
        f"=== JOB AD ===\n{job}\n\n=== CV LIBRARY ===\n" + "\n".join(lines),
        max_tokens=1200,
    )
    picks = [p for p in short.get("shortlist", []) if p in idx.records][:5]
    if not picks:
        picks = list(idx.records)[:5]

    blocks = [f"=== CV [{rel}] ===\n{text_of(rel)[:9000]}" for rel in picks]
    result = cr.ask_json(
        cfg, ANALYSE_SYSTEM,
        f"=== JOB AD ===\n{job}\n\n" + "\n\n".join(blocks),
        max_tokens=6000,
    )

    # The model occasionally names a CV that was not in the shortlist, or
    # mangles the path. Anything it picks must be a CV we actually have.
    best = (result.get("best") or {}).get("path", "")
    if best not in idx.records:
        best = picks[0]
        result.setdefault("best", {})["path"] = best
        result["best"].setdefault("why", "")
    ru = result.get("runner_up") or {}
    if ru.get("path") and ru["path"] not in idx.records:
        result["runner_up"] = {"path": "", "why": ""}

    result["ats_score"] = _clamp(result.get("ats_score"))
    result["fit_score"] = _clamp(result.get("fit_score", result["ats_score"]))
    lang = (result.get("job_language") or short.get("job_language") or "").lower()
    result["job_language"] = lang if lang in ("fr", "en") else guess_language(jd_text)
    result["key_changes"] = [c for c in (result.get("key_changes") or [])
                             if isinstance(c, dict) and c.get("suggested")]

    result["best_variant"] = best
    result["suggested_edits"] = result["key_changes"]
    result["_shortlist"] = picks
    result["_stage_wanted"] = short.get("stage_wanted", "")
    result["_shortlist_reason"] = short.get("reason", "")
    return result


_FR = re.compile(r"\b(le|la|les|des|du|une|et|pour|avec|vous|nous|dans|sur|est|sont|"
                 r"votre|notre|poste|profil|expérience|compétences|missions)\b", re.I)
_EN = re.compile(r"\b(the|and|for|with|you|we|our|your|are|is|this|will|role|team|"
                 r"experience|skills|requirements|responsibilities)\b", re.I)


def guess_language(text: str) -> str:
    """fr or en from function-word frequency. No dependency, good enough to
    route an ad to the French or English CV track."""
    sample = text[:6000]
    return "fr" if len(_FR.findall(sample)) > len(_EN.findall(sample)) else "en"
