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
  - This module sets field values. It never activates a control: no clicks and
    no key presses. It cannot submit and cannot touch a CAPTCHA, and
    test_pipeline.py fails if either appears. Sending is pipeline/autoapply.py,
    and only through the gate there.
  - It fills identity, contact and link fields, the CV upload, and the replies
    you wrote yourself under [[answers]] in profile.toml. It invents nothing:
    a question with no reply of yours stays on the report for you to answer.
  - It refuses to run without an interactive terminal: a scheduled job cannot
    open forms nobody is watching.
  - Personal values from profile.toml are never logged; only field names are.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
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


class NoDisplay(RuntimeError):
    pass


# The portal runs as a systemd user service, started at login before the
# desktop publishes DISPLAY and XAUTHORITY to the user manager. The service
# process therefore never receives them, and a headed Chrome launched from it
# fails with "you launched a headed browser without having a XServer running"
# even though the session is perfectly fine. The manager has the values by the
# time a window is actually wanted, so ask it then rather than trusting the
# environment this process was started with.
DISPLAY_KEYS = ("DISPLAY", "WAYLAND_DISPLAY", "XAUTHORITY", "XDG_RUNTIME_DIR")


def display_env() -> dict:
    """The graphical session's display variables. Raises if there is none."""
    env = {k: os.environ[k] for k in DISPLAY_KEYS if os.environ.get(k)}
    if not (env.get("DISPLAY") or env.get("WAYLAND_DISPLAY")):
        try:
            out = subprocess.run(["systemctl", "--user", "show-environment"],
                                 capture_output=True, text=True, timeout=10).stdout
        except Exception:
            out = ""
        for line in out.splitlines():
            k, _, v = line.partition("=")
            if k in DISPLAY_KEYS and v:
                env.setdefault(k, v)
    if not (env.get("DISPLAY") or env.get("WAYLAND_DISPLAY")):
        raise NoDisplay(
            "aucun affichage graphique : la fenêtre du formulaire ne peut pas "
            "s'ouvrir. Ce mode a besoin d'une session graphique ouverte, parce "
            "que la fenêtre est là pour que tu la lises. Sur une machine sans "
            "écran, ouvre l'annonce toi-même et postule à la main.")
    os.environ.update(env)          # the next launch finds it without asking
    return env


def tier(url: str, allowed: list[str]) -> int:
    host = (urlparse(url).hostname or "").lower()
    return 1 if any(host == h or host.endswith("." + h) for h in allowed) else 2


def _identity(profile: dict, lang: str) -> dict:
    p = dict(profile.get(lang) or profile.get("base") or {})
    if "full_name" not in p and (p.get("first_name") or p.get("last_name")):
        p["full_name"] = f"{p.get('first_name', '')} {p.get('last_name', '')}".strip()
    return {k: v for k, v in p.items() if isinstance(v, str) and v.strip()}


def fill_form(page, ident: dict, cv: Path, answers=()) -> dict:
    """Fill what is safe to fill. Returns a report — names only, no values.

    Three sources, in order: your identity from profile.toml, the tailored CV,
    then the replies you wrote yourself under [[answers]]. Nothing is guessed:
    a question you have not answered stays in required_left.
    """
    rep = {"filled": [], "not_found": [], "resume": False, "captcha": False,
           "answered": [], "questions": [], "required_left": []}

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

    for f in required_fields(page):
        val = answer_for(f["label"], answers)
        if val is None or not set_field(page, f, val):
            continue
        rep["answered"].append(f["label"])

    rep["captcha"] = any(page.locator(s).count() for s in CAPTCHA)
    rep["questions"] = required_fields(page)          # what is still open
    rep["required_left"] = [f["label"] for f in rep["questions"]]
    return rep


# Every control the form itself marks as required and that is still empty,
# with enough about it to fill it: its kind, its options, and a selector that
# finds it again. Anything left in this list is a question nobody has answered.
JS_REQUIRED = """() => {
  const sel = el => el.id ? '#' + CSS.escape(el.id)
             : el.name ? `${el.tagName.toLowerCase()}[name="${CSS.escape(el.name)}"]` : '';
  const label = el => ((el.labels && el.labels[0] && el.labels[0].innerText)
                    || el.getAttribute('aria-label')
                    || (el.closest('label') && el.closest('label').innerText)
                    || el.name || el.id || el.type || '')
                    .trim().replace(/\\s+/g, ' ').replace(/\\s*\\*$/, '').slice(0, 120);
  const out = [], seen = new Set();
  for (const el of document.querySelectorAll(
         'input[required], textarea[required], select[required], [aria-required="true"]')) {
    if (el.type === 'hidden' || el.type === 'file' || el.disabled) continue;
    if (!(el.offsetParent || el.getClientRects().length)) continue;   // hidden branch
    const radio = el.type === 'radio';
    const empty = (el.type === 'checkbox' || radio)
      ? !(el.name && document.querySelector(`[name="${CSS.escape(el.name)}"]:checked`))
      : !String(el.value || '').trim();
    if (!empty) continue;
    const kind = radio ? 'radio'
               : el.type === 'checkbox' ? 'checkbox'
               : el.tagName === 'SELECT' ? 'select'
               : el.tagName === 'TEXTAREA' ? 'textarea' : 'text';
    const key = (kind === 'radio' ? 'r:' + el.name : sel(el) || label(el));
    if (seen.has(key)) continue;
    seen.add(key);
    let options = [], s = '';
    if (kind === 'select') {
      options = [...el.options].map(o => o.label || o.text).filter(t => t && t.trim());
      s = sel(el);
    } else if (kind === 'radio') {
      s = `input[type="radio"][name="${CSS.escape(el.name)}"]`;
      options = [...document.querySelectorAll(s)].map(label);
    } else {
      s = sel(el);
    }
    if (!s) continue;
    out.push({label: label(el), kind, sel: s, options});
  }
  return out;
}"""


def required_fields(page) -> list[dict]:
    try:
        return page.evaluate(JS_REQUIRED) or []
    except Exception:
        return []


def answer_for(label: str, answers) -> str | None:
    """The reply you wrote for this question, or None. Never invents one."""
    for a in answers or ():
        try:
            if re.search(a["match"], label or "", re.I):
                return a["value"]
        except re.error:
            continue
    return None


def _pick(options: list[str], value: str) -> str | None:
    v = value.strip().lower()
    for o in options:
        if o.strip().lower() == v:
            return o
    for o in options:
        if v and v in o.strip().lower():
            return o
    return None


def set_field(page, f: dict, value: str) -> bool:
    """Put your answer into one control. Sets a value; activates no button."""
    try:
        if f["kind"] in ("text", "textarea"):
            page.locator(f["sel"]).first.fill(value)
            return True
        if f["kind"] == "select":
            opt = _pick(f.get("options") or [], value)
            if opt is None:
                return False
            page.select_option(f["sel"], label=opt)
            return True
        if f["kind"] == "radio":
            opts = f.get("options") or []
            opt = _pick(opts, value)
            if opt is None:
                return False
            page.locator(f["sel"]).nth(opts.index(opt)).check()
            return True
        if f["kind"] == "checkbox":
            if value.strip().lower() not in ("yes", "oui", "true", "1", "on", "i agree", "agree"):
                return False
            page.locator(f["sel"]).first.check()
            return True
    except Exception:
        return False
    return False


def staged(db: DB) -> list:
    return db.q("SELECT a.*, j.apply_url, j.title FROM applications a "
                "JOIN jobs j ON j.id=a.job_id WHERE a.status='staged' "
                "ORDER BY a.fit_score DESC, a.date ASC")


def cv_file(pcfg: pc.PipelineConfig, app) -> Path:
    """The tailored CV to attach."""
    cv = pcfg.applications_dir / (app["date"] or "") / (app["cv_filename"] or "")
    if not cv.is_file():
        found = list(pcfg.applications_dir.rglob(app["cv_filename"] or "__none__"))
        cv = found[0] if found else cv
    if not cv.is_file():
        raise FileNotFoundError(f"no tailored CV on file for {app['job_id']}")
    return cv


def open_and_fill(pcfg: pc.PipelineConfig, apply_url: str, ident: dict, cv: Path, *,
                  answers=(), on_filled=None) -> dict:
    """Open the form in a real window, fill what is safe to fill, and leave it
    open for you. Returns the report; on_filled gets it as soon as the fields
    are in, before the wait, so a caller can show it while you read the form.

    This function does not submit. There is no click anywhere in this module.
    """
    disp = display_env()                              # before Playwright starts
    from playwright.sync_api import sync_playwright
    user_dir = ROOT / "data" / "browser-profile"      # separate from your own Chrome
    rep: dict = {}
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(user_dir), channel=pcfg.submit_channel, headless=False,
            env={**os.environ, **disp},
            viewport={"width": 1280, "height": 900})
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(apply_url, wait_until="domcontentloaded", timeout=60_000)
        page.wait_for_timeout(2500)                  # let the form render
        rep = fill_form(page, ident, cv, answers)
        if on_filled:
            on_filled(rep)
        try:
            page.wait_for_event("close", timeout=0)  # you close it when done
        except Exception:
            pass
        try:
            ctx.close()
        except Exception:
            pass
    return rep


def submit(db: DB, pcfg: pc.PipelineConfig, job_id: str, *, ask=input) -> str:
    job = db.one("SELECT * FROM jobs WHERE id=?", job_id)
    app = db.one("SELECT * FROM applications WHERE job_id=?", job_id)
    m = db.one("SELECT * FROM matches WHERE job_id=?", job_id)
    if not job or not app:
        raise SystemExit(f"unknown job {job_id}")
    try:
        cv = cv_file(pcfg, app)
    except FileNotFoundError as e:
        raise SystemExit(f"{e}: run pipeline.tailor")

    print(f"\n{job['company']}, {job['title']}")
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
        print("  profile.toml is missing or empty: only the CV will be attached.")

    def show(rep):
        db.event("submit", job_id, stage="prefilled", filled=rep["filled"],
                 answered=rep["answered"], resume=rep["resume"],
                 captcha=rep["captcha"], required_left=len(rep["required_left"]))
        print(f"\n  filled   : {', '.join(rep['filled']) or 'nothing'}")
        if rep["answered"]:
            print(f"  answered : {', '.join(rep['answered'])} (from your profile.toml)")
        print(f"  CV       : {'attached' if rep['resume'] else 'NOT attached, attach it yourself'}")
        if rep["required_left"]:
            print("  still required, for you to answer:")
            for r in rep["required_left"]:
                print(f"    - {r}")
        if rep["captcha"]:
            print("  a CAPTCHA is on the page: solve it yourself, nothing here touches it.")
        print("\n  Review everything, then click submit in the browser yourself.")
        print("  Close the browser window when you are done.")

    open_and_fill(pcfg, job["apply_url"], ident, cv,
                  answers=profile.get("answers", []), on_filled=show)
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
