#!/usr/bin/env python3
"""Application Submission Assistant — stage an application; you submit it.

  python -m pipeline.submit --next         the best-scoring staged application
  python -m pipeline.submit <job_id>       a specific one
  python -m pipeline.submit --list         what is staged

Tier 1 (Greenhouse, Lever, Ashby): opens the application form in a visible
Chrome window, fills your identity and links, attaches the tailored CV, and
stops. You read it, answer what is left, and click submit yourself.

Tier 2 (LinkedIn, Indeed, anything else): nothing is automated. You get the
tailored CV, the edit list and a cover-letter opening, and apply by hand.

Hard rules, enforced in code rather than promised:
  - This module never calls click(). It cannot submit, cannot tick a consent
    box, cannot touch a CAPTCHA. test_pipeline.py fails if a click appears.
  - It fills identity, contact and link fields and the CV upload only. Work
    authorisation, salary, demographic and custom questions are left for you —
    answering those on your behalf could misrepresent you.
  - It refuses to run without an interactive terminal: a scheduled job cannot
    open forms nobody is watching.
  - Personal values from profile.toml are never logged; only field names are.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

from . import config as pc
from .db import DB

ROOT = Path(__file__).resolve().parent.parent

# (profile key, label patterns, attribute selectors) — label matching is
# primary because it survives form redesigns; the selectors are the known
# field names on each platform as a fallback.
FIELDS = [
    ("first_name", r"^\s*(first|given)\s*name|^\s*pr[ée]nom",
     ["#first_name", "input[name='first_name']", "input[autocomplete='given-name']"]),
    ("last_name", r"^\s*(last|family)\s*name|^\s*nom(\s+de\s+famille)?\s*\*?\s*$|surname",
     ["#last_name", "input[name='last_name']", "input[autocomplete='family-name']"]),
    ("full_name", r"^\s*(full\s*)?name\s*\*?\s*$|^\s*nom\s+complet",
     ["input[name='name']", "#_systemfield_name"]),
    ("email", r"e-?mail",
     ["#email", "input[name='email']", "#_systemfield_email", "input[type='email']"]),
    ("phone", r"phone|t[ée]l[ée]phone|mobile",
     ["#phone", "input[name='phone']", "#_systemfield_phone", "input[type='tel']"]),
    ("location", r"^\s*(current\s+)?(location|city)|^\s*ville|^\s*localisation",
     ["input[name='location']", "#candidate-location"]),
    ("linkedin", r"linked\s*in",
     ["input[name='urls[LinkedIn]']", "input[name*='linkedin' i]"]),
    ("github", r"git\s*hub",
     ["input[name='urls[GitHub]']", "input[name*='github' i]"]),
    ("portfolio", r"portfolio|personal\s+(web)?site|^\s*website",
     ["input[name='urls[Portfolio]']", "input[name='urls[Other]']"]),
]
RESUME = ["#resume", "input[type='file'][name='resume']", "#_systemfield_resume",
          "input[type='file'][id*='resume' i]", "input[type='file']"]
CAPTCHA = ["iframe[src*='recaptcha']", "iframe[src*='hcaptcha']",
           "iframe[src*='challenges.cloudflare.com']", ".g-recaptcha", ".h-captcha",
           ".cf-turnstile"]


def tier(url: str, allowed: list[str]) -> int:
    host = (urlparse(url).hostname or "").lower()
    return 1 if any(host == h or host.endswith("." + h) for h in allowed) else 2


def _identity(profile: dict, lang: str) -> dict:
    p = dict(profile.get(lang) or profile.get("base") or {})
    if "full_name" not in p and (p.get("first_name") or p.get("last_name")):
        p["full_name"] = f"{p.get('first_name', '')} {p.get('last_name', '')}".strip()
    return {k: v for k, v in p.items() if isinstance(v, str) and v.strip()}


def fill_form(page, ident: dict, cv: Path) -> dict:
    """Fill what is safe to fill. Returns a report — names only, no values."""
    rep = {"filled": [], "not_found": [], "resume": False, "captcha": False,
           "required_left": []}

    for key, label_rx, selectors in FIELDS:
        val = ident.get(key)
        if not val:
            continue
        target = None
        loc = page.get_by_label(re.compile(label_rx, re.I))
        try:
            for i in range(min(loc.count(), 3)):
                el = loc.nth(i)
                tag = el.evaluate("e => e.tagName.toLowerCase() + ':' + (e.type || '')")
                if tag.startswith(("input:text", "input:email", "input:tel", "input:url",
                                   "input:", "textarea")) and "file" not in tag \
                        and "checkbox" not in tag and "radio" not in tag:
                    target = el
                    break
        except Exception:
            target = None
        if target is None:
            for sel in selectors:
                cand = page.locator(sel)
                if cand.count():
                    target = cand.first
                    break
        if target is None:
            rep["not_found"].append(key)
            continue
        try:
            if (target.input_value() or "").strip():
                continue                   # never overwrite what is already there
            target.fill(val)
            rep["filled"].append(key)
        except Exception:
            rep["not_found"].append(key)

    for sel in RESUME:
        f = page.locator(sel)
        if f.count():
            try:
                f.first.set_input_files(str(cv))
                rep["resume"] = True
                break
            except Exception:
                continue

    rep["captcha"] = any(page.locator(s).count() for s in CAPTCHA)
    try:
        rep["required_left"] = page.evaluate("""() => {
          const out = [];
          for (const el of document.querySelectorAll(
                 'input[required], textarea[required], select[required], [aria-required="true"]')) {
            if (el.type === 'hidden' || el.type === 'file') continue;
            const empty = (el.type === 'checkbox' || el.type === 'radio')
              ? !document.querySelector(`[name="${CSS.escape(el.name)}"]:checked`)
              : !String(el.value || '').trim();
            if (!empty) continue;
            const lab = (el.labels && el.labels[0] && el.labels[0].innerText)
                     || el.getAttribute('aria-label') || el.name || el.id || el.type;
            out.push(lab.trim().replace(/\\s+/g, ' ').slice(0, 80));
          }
          return [...new Set(out)];
        }""")
    except Exception:
        pass
    return rep


def staged(db: DB) -> list:
    return db.q("SELECT a.*, j.apply_url, j.title FROM applications a "
                "JOIN jobs j ON j.id=a.job_id WHERE a.status='staged' "
                "ORDER BY a.fit_score DESC, a.date ASC")


def submit(db: DB, pcfg: pc.PipelineConfig, job_id: str, *, ask=input) -> str:
    job = db.one("SELECT * FROM jobs WHERE id=?", job_id)
    app = db.one("SELECT * FROM applications WHERE job_id=?", job_id)
    m = db.one("SELECT * FROM matches WHERE job_id=?", job_id)
    if not job or not app:
        raise SystemExit(f"unknown job {job_id}")
    cv = pcfg.applications_dir / (app["date"] or "") / (app["cv_filename"] or "")
    if not cv.is_file():
        found = list(pcfg.applications_dir.rglob(app["cv_filename"] or "__none__"))
        cv = found[0] if found else cv
    if not cv.is_file():
        raise SystemExit(f"no tailored CV on file for {job_id} — run pipeline.tailor")

    print(f"\n{job['company']} — {job['title']}")
    print(f"  fit {app['fit_score']}   CV {cv.name}")
    raw = json.loads(m["raw"]) if m and m["raw"] else {}

    if tier(job["apply_url"], pcfg.submit_hosts) == 2:
        print("\n  Tier 2: this platform is not automated. Apply by hand at:")
        print(f"    {job['apply_url']}")
        print(f"  with {cv}")
        if raw.get("cover_letter_hook"):
            print(f"\n  Cover letter opening:\n    {raw['cover_letter_hook']}")
        return _record(db, job_id, ask)

    profile = pc.load_profile()
    ident = _identity(profile, (app["account"] or job["language"] or "en").lower())
    if not ident:
        print("  profile.toml is missing or empty — only the CV will be attached.")

    from playwright.sync_api import sync_playwright
    user_dir = ROOT / "data" / "browser-profile"      # separate from your own Chrome
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(user_dir), channel=pcfg.submit_channel, headless=False,
            viewport={"width": 1280, "height": 900})
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(job["apply_url"], wait_until="domcontentloaded", timeout=60_000)
        page.wait_for_timeout(2500)                  # let the form render
        rep = fill_form(page, ident, cv)
        db.event("submit", job_id, stage="prefilled", filled=rep["filled"],
                 resume=rep["resume"], captcha=rep["captcha"],
                 required_left=len(rep["required_left"]))

        print(f"\n  filled   : {', '.join(rep['filled']) or 'nothing'}")
        print(f"  CV       : {'attached' if rep['resume'] else 'NOT attached — attach it yourself'}")
        if rep["required_left"]:
            print("  still required, for you to answer:")
            for r in rep["required_left"]:
                print(f"    - {r}")
        if rep["captcha"]:
            print("  a CAPTCHA is on the page — solve it yourself; nothing here touches it.")
        print("\n  Review everything, then click submit in the browser yourself.")
        print("  Close the browser window when you are done.")
        try:
            page.wait_for_event("close", timeout=0)
        except Exception:
            pass
        try:
            ctx.close()
        except Exception:
            pass
    return _record(db, job_id, ask)


def _record(db: DB, job_id: str, ask) -> str:
    ans = (ask("\n  Did you submit it?  [y]es / [n]o, keep it staged / [s]kip it for good: ")
           or "n").strip().lower()[:1]
    status = {"y": "applied", "s": "withdrawn"}.get(ans, "staged")
    with db.tx():
        db.upsert_application(job_id, status=status)
        db.event("submit", job_id, stage="result", status=status)
    print(f"  recorded: {status}")
    return status


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("job_id", nargs="?")
    ap.add_argument("--next", action="store_true")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()
    pcfg = pc.load()
    db = DB(pcfg.db)

    if args.list:
        rows = staged(db)
        for r in rows:
            t = "T1" if tier(r["apply_url"], pcfg.submit_hosts) == 1 else "T2"
            print(f"  {t}  fit {r['fit_score']:3d}  {r['company'][:16]:16s} "
                  f"{r['title'][:44]:44s} {r['job_id']}")
        print(f"{len(rows)} staged")
        return 0

    if not sys.stdin.isatty():
        print("refusing to run without an interactive terminal: submission always "
              "needs you watching", file=sys.stderr)
        return 2

    jid = args.job_id
    if args.next:
        rows = staged(db)
        if not rows:
            print("nothing staged")
            return 0
        jid = rows[0]["job_id"]
    if not jid:
        ap.print_help()
        return 2
    submit(db, pcfg, jid)
    return 0


if __name__ == "__main__":
    sys.exit(main())
