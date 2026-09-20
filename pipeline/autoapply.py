#!/usr/bin/env python3
"""Send an application on its own — the one place in this project that clicks.

  python -m pipeline.autoapply --list        what is eligible right now
  python -m pipeline.autoapply <job_id>      send that one
  python -m pipeline.autoapply --next        the best-scoring eligible one
  python -m pipeline.autoapply --rehearse    go all the way, stop before the click

The rule this module exists to enforce: it sends only when nothing had to be
invented. Every required field on the form must have been filled from your CV,
your identity, or a reply you wrote yourself in profile.toml. One unanswered
question, one CAPTCHA, one missing CV, and it stops and hands you the open
window instead.

gate() is that rule, split in two so the expensive half never runs needlessly:

  pre_gate   before the browser opens  — feature on, host allowed, scores high
                                          enough, CV validated, daily cap left
  post_gate  after the form is filled  — CV attached, no CAPTCHA, no required
                                          field left empty, exactly one
                                          unambiguous submit button

submit_button() refuses anything it cannot identify with certainty: if two
buttons could plausibly be "send", that is not a form this can be trusted with.

Off unless [autoapply] enabled = true in pipeline.toml.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from . import config as pc
from . import submit as SUB
from .db import DB

ROOT = Path(__file__).resolve().parent.parent

SEND_RX = re.compile(r"^\s*(submit|submit application|send application|send|apply"
                     r"|postuler|envoyer|soumettre|candidater)\b", re.I)
# A job page usually carries a generic "Apply" above the form as well as the
# form's own "Submit application". Both match SEND_RX, and refusing on that
# ambiguity would block almost every real Greenhouse page — so an explicit
# submit wins over a generic apply. Ambiguity *within* a tier still refuses.
EXPLICIT_RX = re.compile(r"^\s*(submit|send|soumettre|envoyer)\b", re.I)
NOT_SEND_RX = re.compile(r"save|draft|cancel|back|previous|autofill|linkedin|indeed"
                         r"|sign\s*in|log\s*in|annuler|retour|enregistrer", re.I)
# Seen after a successful send on Greenhouse, Lever and Ashby.
OK_RX = re.compile(r"thank you|thanks for applying|application (was )?(received|submitted|sent)"
                   r"|we(?:'ve| have) received|submitted successfully|merci"
                   r"|candidature (a bien été )?(reçue|envoyée|enregistrée)", re.I)


def sent_today(db: DB) -> int:
    row = db.one("SELECT COUNT(*) FROM events WHERE kind='autoapply' "
                 "AND detail LIKE '%\"stage\": \"sent\"%' "
                 "AND date(ts, 'localtime') = date('now', 'localtime')")
    return row[0] if row else 0


def pre_gate(pcfg: pc.PipelineConfig, db: DB, job, app, match) -> list[str]:
    """Reasons this application must not be sent without you. Empty means go."""
    out = []
    if not pcfg.auto_apply:
        out.append("l'envoi automatique est désactivé (pipeline.toml, [autoapply])")
    if not job or not app:
        return out + ["offre inconnue"]
    if SUB.tier(job["apply_url"] or "", pcfg.submit_hosts) != 1:
        out.append("plateforme non automatisable : à faire à la main")
    if app["status"] in ("applied", "interview", "offer", "rejected"):
        out.append(f"déjà envoyée (statut {app['status']})")
    if pcfg.auto_require_validated and app["status"] not in ("staged", "draft"):
        out.append("le CV n'est pas prêt : relis-le et valide-le d'abord")
    fit = app["fit_score"]
    if fit is None or fit < pcfg.auto_min_fit:
        out.append(f"fit {fit if fit is not None else '–'} < {pcfg.auto_min_fit} requis")
    ats = match["ats_score"] if match else None
    if ats is None or ats < pcfg.auto_min_ats:
        out.append(f"ATS {ats if ats is not None else '–'} < {pcfg.auto_min_ats} requis")
    n = sent_today(db)
    if n >= pcfg.auto_max_per_day:
        out.append(f"plafond du jour atteint ({n}/{pcfg.auto_max_per_day})")
    return out


def post_gate(rep: dict, button_state: str) -> list[str]:
    """Reasons the filled form must not be submitted. Empty means go."""
    out = []
    if not rep.get("resume"):
        out.append("le CV n'a pas pu être joint")
    if rep.get("captcha"):
        out.append("un CAPTCHA est sur la page")
    for q in rep.get("questions") or []:
        out.append(f"question sans réponse de toi : {q['label']}")
    if button_state != "ok":
        out.append({"none": "aucun bouton d'envoi identifié",
                    "many": "plusieurs boutons pourraient être « Envoyer »",
                    "disabled": "le bouton d'envoi est désactivé"}[button_state])
    return out


def submit_button(page):
    """The send button, or (None, why). Ambiguity counts as a refusal."""
    cands = []
    for el in page.locator(
            "button, input[type=submit], [role=button]").all():
        try:
            if not el.is_visible():
                continue
            txt = (el.inner_text() or el.get_attribute("value") or "").strip()
        except Exception:
            continue
        if not txt or NOT_SEND_RX.search(txt) or not SEND_RX.search(txt):
            continue
        cands.append((el, txt))
    if not cands:
        return None, "none"
    explicit = [c for c in cands if EXPLICIT_RX.search(c[1])]
    cands = explicit or cands
    if len(cands) > 1:
        return None, "many"
    el, _ = cands[0]
    try:
        if not el.is_enabled():
            return None, "disabled"
    except Exception:
        pass
    return el, "ok"


def confirmed(page, before_url: str) -> bool:
    """Did the employer actually acknowledge it? Unconfirmed is not applied."""
    for _ in range(30):                       # up to ~30s
        page.wait_for_timeout(1000)
        try:
            if OK_RX.search(page.inner_text("body") or ""):
                return True
            if page.url != before_url and "confirm" in page.url.lower():
                return True
        except Exception:
            continue
    return False


def run(pcfg: pc.PipelineConfig, db: DB, job_id: str, *, rehearse: bool = False,
        log=print, on_state=None) -> dict:
    """Open, fill, check, and only then send. Returns what happened and why."""
    def say(state, **kw):
        res = {"state": state, "job_id": job_id, **kw}
        log(f"  {state}: {kw.get('blockers') or kw.get('note', '')}")
        if on_state:
            on_state(res)
        return res

    job = db.one("SELECT * FROM jobs WHERE id=?", job_id)
    app = db.one("SELECT * FROM applications WHERE job_id=?", job_id)
    match = db.one("SELECT * FROM matches WHERE job_id=?", job_id)
    blockers = pre_gate(pcfg, db, job, app, match)
    if blockers:
        db.event("autoapply", job_id, stage="refused", blockers=blockers)
        return say("refused", blockers=blockers)

    cv = SUB.cv_file(pcfg, app)
    profile = pc.load_profile()
    ident = SUB._identity(profile, (app["account"] or job["language"] or "en").lower())
    answers = profile.get("answers", [])
    rehearse = rehearse or pcfg.auto_rehearse

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(ROOT / "data" / "browser-profile"), channel=pcfg.submit_channel,
            headless=False, viewport={"width": 1280, "height": 900})
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        try:
            page.goto(job["apply_url"], wait_until="domcontentloaded", timeout=60_000)
            page.wait_for_timeout(2500)
            rep = SUB.fill_form(page, ident, cv, answers)
            btn, why = submit_button(page)
            blockers = post_gate(rep, why)
            db.event("autoapply", job_id, stage="filled", filled=rep["filled"],
                     answered=rep["answered"], blockers=blockers)
            say("filled", note=f"{len(rep['filled'])} champs, "
                               f"{len(rep['answered'])} réponses")

            if blockers:
                # The window stays open: everything is filled but the last mile
                # is yours. Closing it here would throw that work away.
                db.event("autoapply", job_id, stage="handed_over", blockers=blockers)
                res = say("handed_over", blockers=blockers, report=rep)
                page.wait_for_event("close", timeout=0)
                return res

            if rehearse:
                db.event("autoapply", job_id, stage="rehearsed")
                res = say("rehearsed", note="tout est vert, rien n'a été envoyé",
                          report=rep)
                page.wait_for_event("close", timeout=0)
                return res

            before = page.url
            btn.click()                                    # the only click
            ok = confirmed(page, before)
            with db.tx():
                db.upsert_application(job_id, status="applied" if ok else "staged",
                                      notes="envoyée automatiquement" if ok else
                                            "envoi non confirmé : vérifie la page")
                db.event("autoapply", job_id, stage="sent" if ok else "unconfirmed")
            return say("sent" if ok else "unconfirmed", report=rep,
                       note="confirmée par l'employeur" if ok else
                            "pas de confirmation lue sur la page : vérifie")
        except Exception as e:
            db.event("autoapply", job_id, stage="error", reason=str(e)[:300])
            return say("error", note=str(e)[:300])
        finally:
            try:
                ctx.close()
            except Exception:
                pass


def eligible(pcfg: pc.PipelineConfig, db: DB) -> list[dict]:
    """Everything that would pass pre_gate, best first."""
    out = []
    for r in db.q("SELECT a.*, j.apply_url FROM applications a "
                  "JOIN jobs j ON j.id=a.job_id "
                  "WHERE a.status IN ('staged','draft') ORDER BY a.fit_score DESC"):
        m = db.one("SELECT * FROM matches WHERE job_id=?", r["job_id"])
        j = db.one("SELECT * FROM jobs WHERE id=?", r["job_id"])
        b = pre_gate(pcfg, db, j, r, m)
        out.append({"job_id": r["job_id"], "company": r["company"], "role": r["role"],
                    "fit_score": r["fit_score"],
                    "ats_score": m["ats_score"] if m else None,
                    "blockers": b, "eligible": not b})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("job_id", nargs="?")
    ap.add_argument("--next", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--rehearse", action="store_true",
                    help="run every check and stop before sending")
    args = ap.parse_args()
    pcfg = pc.load()
    db = DB(pcfg.db)

    if args.list:
        rows = eligible(pcfg, db)
        for r in rows:
            mark = "OK " if r["eligible"] else "no "
            print(f"  {mark} fit {r['fit_score'] or 0:3d}  {r['company'][:16]:16s} "
                  f"{(r['role'] or '')[:40]:40s} {'; '.join(r['blockers'])}")
        print(f"{sum(r['eligible'] for r in rows)} eligible of {len(rows)}")
        return 0

    jid = args.job_id
    if args.next:
        ok = [r for r in eligible(pcfg, db) if r["eligible"]]
        if not ok:
            print("nothing eligible")
            return 0
        jid = ok[0]["job_id"]
    if not jid:
        ap.print_help()
        return 2
    res = run(pcfg, db, jid, rehearse=args.rehearse)
    return 0 if res["state"] in ("sent", "rehearsed", "handed_over") else 1


if __name__ == "__main__":
    sys.exit(main())
