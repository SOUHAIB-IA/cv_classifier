#!/usr/bin/env python3
"""Tests for the job pipeline. Self-contained: temp database, no network, the
model stubbed. Chrome-dependent checks are skipped when Chrome is absent.

Run:  ./.venv/bin/python test_pipeline.py
"""
from __future__ import annotations

import json
import re
import shutil
import sys
import tempfile
import tomllib
from dataclasses import replace
from pathlib import Path

import httpx

import cvrouter as cr
import matcher
import testkit
from pipeline import calibrate as CAL
from pipeline import config as pc
from pipeline import orchestrate as O
from pipeline import sources as S
from pipeline import submit as SUB
from pipeline import autoapply as AA
from pipeline import tailor as T
from pipeline import tracker as TR
from pipeline.db import DB, dedupe_key
from pipeline.prefilter import Screener
from pipeline.textutil import html_to_text

HERE = Path(__file__).resolve().parent
ok = True


def _refuses(ST, field, value, word) -> bool:
    """A bad value is refused, and the refusal says something a person can act on."""
    try:
        ST.coerce(field, value)
        return False
    except ST.SettingsError as e:
        return word in str(e)


def _refuses_key(ST, cfg, key, word) -> bool:
    try:
        ST.save_key(cfg, key)
        return False
    except ST.SettingsError as e:
        return word in str(e)


def check(label, cond, detail=""):
    global ok
    print(("  PASS  " if cond else "  FAIL  ") + label + (f"   ({detail})" if detail and not cond else ""))
    ok = ok and bool(cond)


def setup():
    cfg, tmp = testkit.temp_config()
    pcfg = pc.load(HERE / "pipeline.example.toml")
    pcfg.db = tmp / "p.db"
    pcfg.lock_file = tmp / "p.lock"
    pcfg.applications_dir = tmp / "applications"
    pcfg.tracker_xlsx = tmp / "tracker.xlsx"
    pcfg.structured_dir = tmp / "structured"
    # a tiny CV collection so the screener has a skill vocabulary to read
    idx = cr.Index(cfg)
    recs = {}
    for i, skills in enumerate([["Python", "PyTorch", "LangChain", "RAG", "Docker"],
                                ["Python", "SQL", "Docker", "FastAPI", "MLflow"],
                                ["Python", "TensorFlow", "Kubernetes", "LLM"]]):
        rel = f"2-Graduate/AI-ML-Engineering/cv-{i}.pdf"
        testkit.make_pdf(cfg.cv_root / rel, [f"Ada {i}", "AI Engineer"] + testkit.SAMPLE_TEXT[3:])
        recs[rel] = cr.CVRecord(path=rel, branch="2-Graduate", specialty="AI-ML-Engineering",
                                role="AI-ML-Engineer", lang="EN", headline="AI Engineer",
                                summary="AI engineer", skills=skills, sig=f"s{i}")
    idx.commit(upserts=recs)
    return cfg, pcfg, tmp


def job(i, company="Acme", title="Machine Learning Engineer", location="Paris, France",
        jd=None, lang="en", source="ashby"):
    return {"id": f"{source}:{i}", "source": source, "board": company.lower(),
            "company": company, "title": title, "location": location,
            "jd_text": jd or "We build LLM and RAG systems in Python with PyTorch and Docker. "
                             "You will ship machine learning to production.",
            "apply_url": f"https://jobs.ashbyhq.com/{company.lower()}/{i}/application",
            "jd_url": f"https://jobs.ashbyhq.com/{company.lower()}/{i}",
            "language": lang, "posted_date": "2026-09-10"}


def fake_match(fit, variant="2-Graduate/AI-ML-Engineering/cv-0.pdf"):
    def fn(cfg, jd, **kw):
        return {"best_variant": variant, "fit_score": fit, "ats_score": fit,
                "fit_reason": "stub", "job_language": "en",
                "suggested_edits": [], "key_changes": [], "best": {"path": variant}}
    return fn


def main():
    # ------------------------------------------------------------ text/sources
    print("\n1. job-board parsing")
    gh = "&lt;div&gt;&lt;h2&gt;About&lt;/h2&gt;&lt;ul&gt;&lt;li&gt;Python&lt;/li&gt;&lt;/ul&gt;&lt;/div&gt;"
    t = html_to_text(gh)
    check("Greenhouse double-encoded HTML becomes text", "About" in t and "- Python" in t
          and "<" not in t, t)

    def handler(req: httpx.Request):
        if "lever" in req.url.host:
            return httpx.Response(200, json=[{
                "id": "L1", "text": "ML Engineer", "descriptionPlain": "Intro",
                "lists": [{"text": "Requirements", "content": "<li>PyTorch</li>"}],
                "additionalPlain": "Benefits", "categories": {"location": "Paris"},
                "workplaceType": "hybrid", "hostedUrl": "https://jobs.lever.co/x/L1",
                "applyUrl": "https://jobs.lever.co/x/L1/apply", "createdAt": 1757500000000}])
        return httpx.Response(200, json={"jobs": [{
            "id": "A1", "title": "AI Engineer", "location": "Paris", "isRemote": True,
            "descriptionPlain": "Build agents", "jobUrl": "u", "applyUrl": "u/application",
            "publishedAt": "2026-09-01T10:00:00+00:00", "isListed": True},
            {"id": "A2", "title": "Hidden", "isListed": False}]})

    with httpx.Client(transport=httpx.MockTransport(handler)) as c:
        lv = S.lever(c, "x")[0]
        ab = S.ashby(c, "y")
    check("Lever joins intro, requirement lists and closing",
          all(x in lv["jd_text"] for x in ("Intro", "Requirements", "PyTorch", "Benefits")))
    check("Lever keeps the work mode with the place", lv["location"] == "Paris (hybrid)", lv["location"])
    check("Lever epoch-millis date parsed", lv["posted_date"].startswith("2025-09"), lv["posted_date"])
    check("Ashby unlisted postings dropped", len(ab) == 1)
    check("Ashby remote flag kept", "remote" in ab[0]["location"])

    # -------------------------------------------------------------- prefilter
    cfg, pcfg, tmp = setup()
    scr = Screener(pcfg, cfg)
    print("\n2. pre-screen")
    for title, want in [("Marketing Generalist - Saudi Arabia", False),
                        ("Internal AI Tools Engineer", True), ("Machine Learning Engineer", True),
                        ("Senior ML Engineer", False), ("Stage Data Science", False),
                        ("Ingénieur IA", True)]:
        check(f"title '{title}' -> {'kept' if want else 'dropped'}",
              scr._title_ok(title)[0] == want)
    for loc, want in [("Middle East, Dubai, Riyadh (remote)", False),
                      ("France, Europe, Paris (remote)", True), ("Remote", True),
                      ("Remote - US", False), ("San Francisco, CA | Paris", True)]:
        check(f"location '{loc}' -> {'kept' if want else 'dropped'}",
              scr._location_ok(loc)[0] == want)
    hi, _ = scr.score(job(1))
    lo, _ = scr.score(job(2, title="Software Engineer", jd="Ruby on Rails and PHP."))
    check("score follows the skills in YOUR CVs", hi > lo, f"{hi} vs {lo}")

    # ------------------------------------------------------------ orchestrate
    print("\n3. routing")
    db = DB(pcfg.db)
    with db.tx():
        for i, fit_title in enumerate(["ML Engineer A", "ML Engineer B", "ML Engineer C"]):
            db.upsert_job(job(i, company=f"Co{i}", title=fit_title))
    fits = iter([85, 55, 20])
    O.route(db, pcfg, cfg, match_fn=lambda *a, **k: fake_match(next(fits))(*a, **k),
            max_matches=5, log=lambda *a: None)
    got = {r["company"]: (r["decision"], r["status"]) for r in db.q("SELECT * FROM applications")}
    check("fit 85 -> auto / pending", got.get("Co0") == ("auto", "pending"), got.get("Co0"))
    check("fit 55 -> review", got.get("Co1") == ("review", "review"), got.get("Co1"))
    check("fit 20 -> skip", got.get("Co2") == ("skip", "skipped"), got.get("Co2"))

    with db.tx():
        db.upsert_job(job(9, company="Co0", title="ML Engineer A (H/F)"))
    calls = {"n": 0}

    def counted(*a, **k):
        calls["n"] += 1
        return fake_match(90)(*a, **k)

    O.route(db, pcfg, cfg, match_fn=counted, max_matches=5, log=lambda *a: None)
    check("duplicate guard: same company+title never evaluated again", calls["n"] == 0)

    # Loosening a filter used to change nothing: a posting already dropped was
    # never looked at again, so widening a location list stranded every earlier
    # posting it would now accept.
    far = job(77, company="Faraway", title="Machine Learning Engineer",
              location="Reykjavik, Iceland")
    with db.tx():
        db.upsert_job(far)
    O.screen(db, pcfg, Screener(pcfg, cfg), log=lambda *a: None)
    check("a posting outside your places is dropped",
          db.one("SELECT stage FROM jobs WHERE id=?", far["id"])["stage"] == "filtered")
    st = O.screen(db, pcfg, Screener(pcfg, cfg), log=lambda *a: None)
    check("…and an unchanged filter does not re-examine it", st["reconsidered"] == 0)
    wider = replace(pcfg, location_include=pcfg.location_include + ["iceland"])
    st = O.screen(db, wider, Screener(wider, cfg), log=lambda *a: None)
    check("widening the filter reconsiders what it had dropped",
          st["reconsidered"] > 0 and
          db.one("SELECT stage FROM jobs WHERE id=?", far["id"])["stage"] == "candidate")
    check("the filters are remembered, so it happens once and not every run",
          O.prefilter_sig(wider) == db.get_meta("prefilter_sig")
          and O.screen(db, wider, Screener(wider, cfg),
                       log=lambda *a: None)["reconsidered"] == 0)
    with db.tx():
        db.set_stage(far["id"], "filtered", status="processed")
    check("dedupe key ignores (H/F) and case",
          dedupe_key("Co0", "ML Engineer A (H/F)") == dedupe_key("co0", "ml engineer a"))

    print("\n4. regional twins")
    with db.tx():
        for i, loc in enumerate(["Dubai, UAE (remote)", "France, Paris (remote)",
                                 "Singapore (remote)"]):
            db.upsert_job(job(20 + i, company="Cohere", title="Forward Deployed Engineer",
                              location=loc))
    seen = []
    O.route(db, pcfg, cfg, max_matches=5, log=lambda *a: None,
            match_fn=lambda c, jd, **k: (seen.append(k["location"]), fake_match(60)(c, jd, **k))[1])
    check("one role posted three times is evaluated once", len(seen) == 1, seen)
    check("the posting kept is the best-placed one", seen and "France" in seen[0], seen)

    print("\n5. budget and crash safety")
    pcfg.daily_match_budget = db.matches_today() + 1
    with db.tx():
        for i in range(3):
            db.upsert_job(job(40 + i, company=f"Budget{i}", title="ML Engineer"))
    calls["n"] = 0
    O.route(db, pcfg, cfg, match_fn=counted, max_matches=5, log=lambda *a: None)
    check("daily budget caps evaluations", calls["n"] == 1, calls["n"])

    pcfg.daily_match_budget = 1000
    with db.tx():
        db.upsert_job(job(60, company="Crashy", title="ML Engineer"))

    def boom(*a, **k):
        raise ValueError("model returned garbage")

    for _ in range(3):
        O.route(db, pcfg, cfg, match_fn=boom, max_matches=10, log=lambda *a: None)
    st = db.one("SELECT stage FROM jobs WHERE id='ashby:60'")["stage"]
    charged = db.one("SELECT COUNT(*) FROM events WHERE kind='match' AND job_id='ashby:60'")[0]
    check("a crashing evaluation is parked after 2 attempts, not retried forever",
          st == "error" and charged == 2, f"stage={st} charged={charged}")

    with db.tx():
        db.upsert_job(job(70, company="Dry", title="ML Engineer"))
    before = db.one("SELECT COUNT(*) FROM events")[0]
    O.route(db, pcfg, cfg, dry=True, match_fn=counted, max_matches=5, log=lambda *a: None)
    check("dry run writes nothing", db.one("SELECT COUNT(*) FROM events")[0] == before)

    # ------------------------------------------------------------------ tailor
    print("\n6. tailoring")
    base = {"name": "Ada Lovelace", "headline": "AI Engineer",
            "summary": "Engineer integrating LLMs with external APIs.",
            "contact": {}, "sections": [
                {"title": "Experience", "kind": "experience", "items": [
                    {"heading": "AI Engineer", "org": "Acme", "dates": "2025",
                     "bullets": ["Built a RAG pipeline with LangChain."]}]},
                {"title": "Skills", "kind": "skills", "groups": [
                    {"label": "Pipeline tools", "items": ["Airflow"]},
                    {"label": "Cloud", "items": ["Docker", "Azure"]}]}]}
    edits = [
        {"section": "Profile", "current": "integrating LLMs with external APIs",
         "suggested": "integrating LLMs through REST APIs"},
        {"section": "Skills — Cloud", "current": "Docker | Azure", "suggested": "Docker | REST API | Azure"},
        {"section": "Experience", "current": "Led a team of 40 engineers", "suggested": "CTO of 40"},
        {"section": "Profile", "current": "(absent)", "suggested": "Blockchain expert"},
        {"section": "Experience", "current": "Built a RAG pipeline",
         "suggested": "Built a RAG pipeline " + "x" * 400},
    ]
    out, rep = T.apply_edits(base, edits)
    st = [r["status"] for r in rep]
    check("anchored rewording applied", "through REST APIs" in out["summary"])
    check("skills group with a 'line'-like label handled as skills",
          out["sections"][1]["groups"][1]["items"] == ["Docker", "REST API", "Azure"])
    check("invented experience refused", st[2] == "skipped")
    check("blind addition to the profile refused", st[3] == "skipped")
    check("a rewrite disguised as an edit refused", st[4] == "skipped")
    check("the cached base CV is never mutated", "external APIs" in base["summary"])
    _, prot = T.apply_edits(base, [{"section": "Experience", "current": "Acme 2025",
                                    "suggested": "Google 2020"}])
    check("dates and employers are protected, and said so",
          prot[0]["status"] == "skipped" and "protected" in prot[0]["reason"], prot[0]["reason"])

    reordered = T.reorder(json.loads(json.dumps(base)), "graduate")
    check("graduate CVs lead with experience", reordered["sections"][0]["kind"] == "experience")

    pdf_text = "Ada Lovelace AI Engineer Engineer integrating LLMs with external APIs " \
               "AI Engineer Acme 2025 Built a RAG pipeline with LangChain Airflow Docker Azure"
    check("full extraction passes the coverage check", T.coverage(pdf_text, base) >= 0.85)
    check("lossy extraction fails it", T.coverage(pdf_text, {"name": "Ada Lovelace"}) < 0.85)

    try:
        chrome = T.find_chrome(pcfg)
    except T.TailorError:
        chrome = None
    if chrome:
        big = json.loads(json.dumps(base))
        big["sections"][0]["items"] = [
            {"heading": f"Role {i}", "org": "Org", "dates": "2020", "location": "Paris",
             "bullets": [f"Delivered outcome number {j} for project {i} with measurable impact."
                         for j in range(5)]} for i in range(7)]
        pdf = tmp / "fit.pdf"
        pages, step = T.render_fitted(big, "en", pdf, chrome, max_pages=1)
        check("a dense CV is tightened onto one page", pages == 1, f"{pages} pages")
        rep_ok = [{"status": "applied", "suggested": "Delivered outcome number 3"}]
        check("the PDF is read back and verified", T.verify(pdf, big, rep_ok, max_pages=1) == [])
        rep_bad = [{"status": "applied", "suggested": "Quantum gravity specialist"}]
        check("verification catches an edit missing from the PDF",
              T.verify(pdf, big, rep_bad, max_pages=1) != [])
    else:
        print("  skip  render checks (no Chrome)")

    # ------------------------------------------------------------------ submit
    print("\n7. submission guard rails")
    src = (HERE / "pipeline" / "submit.py").read_text()
    code = "\n".join(l for l in src.splitlines() if not l.lstrip().startswith(("#", '"', "-")))
    check("the assisted path sets values but never activates a control",
          ".click(" not in code and ".dblclick(" not in code and ".tap(" not in code)
    check("it never presses Enter (which submits forms)", "press(" not in code)
    for url, want in [("https://jobs.lever.co/x/1/apply", 1),
                      ("https://job-boards.greenhouse.io/x/jobs/1", 1),
                      ("https://jobs.ashbyhq.com/x/1/application", 1),
                      ("https://www.linkedin.com/jobs/view/1", 2),
                      ("https://fr.indeed.com/viewjob?jk=1", 2),
                      ("https://evil.jobs.lever.co.attacker.com/x", 2)]:
        check(f"tier {want}: {url[:44]}", SUB.tier(url, pcfg.submit_hosts) == want)

    # the window needs a display, and the service is started without one
    import os as _os
    keep = {k: _os.environ.get(k) for k in SUB.DISPLAY_KEYS}
    real_run = SUB.subprocess.run
    try:
        _os.environ["DISPLAY"] = ":9"
        check("a display in the environment is used as is",
              SUB.display_env().get("DISPLAY") == ":9")
        # what the portal actually looks like: started before the desktop
        # published DISPLAY, so its own environment has none
        for k in SUB.DISPLAY_KEYS:
            _os.environ.pop(k, None)
        SUB.subprocess.run = lambda *a, **k: type(
            "R", (), {"stdout": "LANG=C\nDISPLAY=:7\nXAUTHORITY=/run/x\n"})()
        got = SUB.display_env()
        check("with none, the session's display is read from systemd",
              got.get("DISPLAY") == ":7" and got.get("XAUTHORITY") == "/run/x", got)
        check("…and kept, so the next window costs no second lookup",
              _os.environ.get("DISPLAY") == ":7")
        for k in SUB.DISPLAY_KEYS:
            _os.environ.pop(k, None)
        SUB.subprocess.run = lambda *a, **k: type("R", (), {"stdout": "LANG=C\n"})()
        try:
            SUB.display_env()
            check("a machine with no display says so in plain words", False)
        except SUB.NoDisplay as e:
            check("a machine with no display says so in plain words",
                  "affichage graphique" in str(e))
    finally:
        SUB.subprocess.run = real_run
        for k, v in keep.items():
            if v is None:
                _os.environ.pop(k, None)
            else:
                _os.environ[k] = v

    # answers come from you and only from you
    prof = pc.load_profile(HERE / "profile.example.toml")
    ans = prof["answers"]
    check("a question you answered is answered",
          SUB.answer_for("Are you legally authorized to work in Morocco? *", ans) == "Yes")
    check("the French wording of the same question matches too",
          SUB.answer_for("Avez-vous l'autorisation de travail ?", ans) == "Yes")
    check("a question you did not answer stays unanswered",
          SUB.answer_for("What are your salary expectations?", ans) is None)
    check("a dropdown option is matched, not invented",
          SUB._pick(["Yes", "No", "Prefer not to say"], "yes") == "Yes")
    check("an option that is not on offer is refused",
          SUB._pick(["Under 1 year", "1-3 years"], "Immediately") is None)

    # ------------------------------------------------------------- auto-apply
    print("\n7b. sending without you: the gate")
    asrc = (HERE / "pipeline" / "autoapply.py").read_text()
    check("exactly one click in the whole project's sending path",
          asrc.count(".click(") == 1)
    check("that click comes after the gate, in the same function",
          asrc.index("post_gate(rep,") < asrc.index("btn.click()"))
    run_src = asrc[asrc.index("def run("):]
    check("it is unreachable while blockers remain, or while rehearsing",
          run_src.index("if blockers:") < run_src.index("btn.click()")
          and run_src.index("if rehearse:") < run_src.index("btn.click()"))

    aj = db.one("SELECT * FROM jobs WHERE id='ashby:0'")
    aa = dict(db.one("SELECT * FROM applications WHERE job_id='ashby:0'") or {})
    am = db.one("SELECT * FROM matches WHERE job_id='ashby:0'")
    check("off by default, nothing is eligible",
          any("désactiv" in b for b in AA.pre_gate(pcfg, db, aj, aa, am)))
    # The shipped default must stay off. Enabling it for a screenshot once and
    # leaving it on is exactly the mistake this catches.
    shipped = tomllib.loads((HERE / "pipeline.example.toml").read_text())
    check("the shipped config ships with sending switched off",
          shipped["autoapply"]["enabled"] is False)
    check("…and requires a CV you have read", shipped["autoapply"]["require_validated_cv"])
    # a copy, never the shared pcfg: the web-interface checks below read the
    # same object and would see auto-apply switched on
    g = replace(pcfg, auto_apply=True, auto_min_fit=0, auto_min_ats=0,
                auto_require_validated=False)
    linkedin = {**dict(aj), "apply_url": "https://www.linkedin.com/jobs/view/1"}
    check("a platform that is not automatable is refused",
          any("plateforme" in b for b in AA.pre_gate(g, db, linkedin, aa, am)))
    check("a fit below your floor is refused",
          any("fit" in b for b in AA.pre_gate(
              replace(g, auto_min_fit=200), db, aj, aa, am)))
    check("the daily cap is a real cap",
          any("plafond" in b for b in AA.pre_gate(
              replace(g, auto_max_per_day=0), db, aj, aa, am)))
    check("an application already sent is never sent twice",
          any("déjà envoyée" in b for b in AA.pre_gate(
              g, db, aj, {**aa, "status": "applied"}, am)))
    check("an unread CV is never sent",
          any("relis" in b for b in AA.pre_gate(
              replace(g, auto_require_validated=True), db, aj,
              {**aa, "status": "pending"}, am)))

    full = {"resume": True, "captcha": False, "questions": []}
    check("a fully filled form with no CAPTCHA passes", AA.post_gate(full, "ok") == [])
    check("one unanswered question stops it", AA.post_gate(
        {**full, "questions": [{"label": "Desired salary"}]}, "ok") ==
        ["question sans réponse de toi : Desired salary"])
    check("a CAPTCHA stops it", AA.post_gate({**full, "captcha": True}, "ok") != [])
    check("a CV that failed to attach stops it", AA.post_gate({**full, "resume": False}, "ok") != [])
    for state, word in [("none", "aucun bouton"), ("many", "plusieurs"), ("disabled", "désactivé")]:
        check(f"an unusable submit button stops it ({state})",
              any(word in b for b in AA.post_gate(full, state)))
    check("'Save draft' is never read as 'Send'",
          AA.NOT_SEND_RX.search("Save draft") is not None)
    check("'Submit application' is read as 'Send'",
          AA.SEND_RX.search("Submit application") is not None
          and AA.NOT_SEND_RX.search("Submit application") is None)
    check("a confirmation page is recognised",
          AA.OK_RX.search("Thank you for applying to Acme") is not None)
    # a real job page carries a generic Apply above the form as well
    check("an explicit Submit wins over a generic Apply",
          AA.EXPLICIT_RX.search("Submit application") is not None
          and AA.EXPLICIT_RX.search("Apply for this job") is None)
    check("two explicit send buttons are still an ambiguity",
          len([t for t in ["Submit application", "Send application"]
               if AA.EXPLICIT_RX.search(t)]) == 2)

    # ----------------------------------------------------------------- settings
    # patch() and coerce() only: write() edits the real config files, and a
    # test suite must never touch those.
    print("\n7c. settings written back into the TOML files")
    import settings as ST
    for name, path in ST.FILES.items():
        txt = path.read_text()
        check(f"{name}.toml survives an empty patch untouched",
              ST.patch(txt, {}).strip() == txt.strip())
    txt = (HERE / "pipeline.example.toml").read_text()
    out = ST.patch(txt, {"autoapply.enabled": True, "autoapply.min_fit": 75,
                         "prefilter.title_exclude": ["senior", "lead"],
                         "submit.allowed_hosts": ["only.example"]})
    d = tomllib.loads(out)
    check("a boolean is written as TOML, not Python",
          "enabled = true" in out and d["autoapply"]["enabled"] is True)
    check("a number keeps its trailing comment",
          [l for l in out.splitlines() if l.startswith("min_fit")][0].endswith("you decide"))
    check("a list is replaced wholesale", d["prefilter"]["title_exclude"] == ["senior", "lead"])
    check("a list spread over several lines is replaced whole",
          d["submit"]["allowed_hosts"] == ["only.example"])
    check("the comments that document the file are still there",
          out.count("#") == txt.count("#"))
    check("a key the section does not have yet is added",
          tomllib.loads(ST.patch(txt, {"tailor.brand_new": 3}))["tailor"]["brand_new"] == 3)
    check("a number out of range is refused with a readable reason",
          _refuses(ST, ST.BY_ID["autoapply.min_fit"], 999, "entre"))
    check("a choice that is not on the list is refused",
          _refuses(ST, ST.BY_ID["ai.backend"], "gpt", "choix"))
    check("text typed into a number field is refused",
          _refuses(ST, ST.BY_ID["ai.timeout"], "vite", "nombre"))
    check("a tag list accepts commas as well as a real list",
          ST.coerce(ST.BY_ID["prefilter.title_include"], "ai, ml ,  data") == ["ai", "ml", "data"])
    check("every field the page can show has a label and a kind",
          all(x.label and x.kind in ("choice", "toggle", "number", "text", "tags", "model")
              for x in ST.BY_ID.values()))
    check("every choice field offers options", all(
        x.options for x in ST.BY_ID.values() if x.kind == "choice"))
    check("a dotted section is read and written like any other",
          isinstance(ST.current()["sources.ashby.boards"], list)
          and tomllib.loads(ST.patch(txt, {"sources.ashby.boards": ["x=X"]})
                            )["sources"]["ashby"]["boards"] == ["x=X"])

    # any provider's key, not only Anthropic's
    check("every provider offers a label and somewhere to get a key",
          all(p["label"] and ("keys_at" in p) for p in cr.PROVIDERS.values()))
    check("every provider but Anthropic and custom has a base address",
          all(p["base"] for k, p in cr.PROVIDERS.items()
              if k not in ("anthropic", "custom")))
    check("the provider list is what the page offers",
          [o[0] for o in ST.BY_ID["ai.provider"].options] == list(cr.PROVIDERS))
    probe_cfg = replace(cfg, backend="api", provider="groq", base_url="")
    check("a provider's own address is used when none is given",
          cr.provider_base(probe_cfg) == "https://api.groq.com/openai/v1")
    check("a base address you set wins over the provider's",
          cr.provider_base(replace(probe_cfg, base_url="http://x/v1/")) == "http://x/v1")
    try:
        cr._ask_compatible(replace(cfg, provider="custom", base_url=""), "s", "u", 10)
        check("a custom provider with no address says so", False)
    except cr.AIError as e:
        check("a custom provider with no address says so", "adresse" in str(e))
    ollama = replace(cfg, provider="ollama", key_file=tmp / "nokey")
    check("a local model needs no key", cr.PROVIDERS["ollama"]["no_key"] is True
          and ollama.api_key is None)
    check("a key for the wrong provider is caught",
          _refuses_key(ST, replace(cfg, provider="groq"), "sk-ant-xyz", "gsk_"))
    check("…and the right one is accepted",
          ST.save_key(replace(cfg, provider="groq", key_file=tmp / "k"),
                      "gsk_abcdef1234")["hint"] == "…1234")
    check("the key file is readable by you alone",
          oct((tmp / "k").stat().st_mode)[-3:] == "600")
    check("every 'depends' points at a field that exists",
        all(x.depends.split("=")[0] in ST.BY_ID for x in ST.BY_ID.values() if x.depends))

    # ------------------------------------------------------------------ tracker
    print("\n8. tracker")
    TR.export(db, pcfg.tracker_xlsx)
    from openpyxl import load_workbook
    wb = load_workbook(pcfg.tracker_xlsx)
    check("xlsx has the four sheets", wb.sheetnames ==
          ["Applications", "Weekly", "Review queue", "Funnel"], wb.sheetnames)
    check("xlsx columns follow the ApplicationRecord",
          [c.value for c in wb["Applications"][1]][:13] == TR.COLUMNS[:13])
    try:
        TR.set_status(db, "ashby:0", "hired-maybe")
        check("unknown status rejected", False)
    except ValueError:
        check("unknown status rejected", True)
    TR.set_status(db, "ashby:0", "interview", "call with CTO")
    wk = [w for w in TR.weekly(db) if w["bucket"] == ">=70"]
    check("weekly rollup counts the interview in its fit bucket",
          wk and wk[-1]["interviews"] == 1 and wk[-1]["response_rate"] == 1.0, wk)

    # --------------------------------------------------------------- calibrate
    print("\n9. calibration")
    pairs = [(88, "apply"), (82, "apply"), (76, "apply"), (66, "maybe"), (58, "maybe"),
             (51, "maybe"), (35, "no"), (22, "no"), (73, "maybe"), (90, "apply")]
    agree, _, a, r = CAL.best_thresholds(pairs)[0]
    check("finds thresholds that reproduce the labels", agree >= 0.9, (agree, a, r))

    # ----------------------------------------------------------------- matcher
    print("\n10. matcher")
    check("French ad detected", matcher.guess_language(
        "Nous recherchons un ingénieur pour notre équipe, avec une expérience en IA.") == "fr")
    check("English ad detected", matcher.guess_language(
        "We are looking for an engineer to join our team with experience in AI.") == "en")
    real = cr.ask_json
    try:
        # Tell the two calls apart by what they are sent: only the shortlist
        # call carries the CV library (both system prompts say "shortlist").
        cr.ask_json = lambda c, s, u, **k: ({"shortlist": ["nope.pdf"]} if "=== CV LIBRARY ===" in u
                                            else {"best": {"path": "made-up.pdf"}, "fit_score": "71",
                                                  "ats_score": 140, "key_changes": [{"x": 1}]})
        idx = cr.Index(cfg)
        res = matcher.match_job(cfg, "We need Python.", idx=idx, text_of=lambda rel: "cv text")
        check("a CV the model invents is replaced by a real one", res["best_variant"] in idx.records)
        check("scores are clamped to 0-100 integers",
              res["fit_score"] == 71 and res["ats_score"] == 100)
        check("malformed edits are dropped", res["suggested_edits"] == [])
    finally:
        cr.ask_json = real

    # ------------------------------------------------------ photo and em dash
    print("\n12. photo, and never an em dash")
    check("the CV template has no em dash", "—" not in (HERE / "templates" / "cv.html").read_text())
    check("the model is told never to write one", "Never use the em dash" in matcher.ANALYSE_SYSTEM)
    for raw, want in [("Engineer — Acme", "Engineer, Acme"), ("LLM—RAG", "LLM-RAG"),
                      ("Essentials – Coursera", "Essentials, Coursera"),
                      ("09/2023 – 06/2026", "09/2023 – 06/2026")]:
        check(f"'{raw}' -> '{want}'", T.no_em_dash(raw) == want, T.no_em_dash(raw))
    dashy = {"name": "Ada", "headline": "AI Engineer — LLM", "summary": "x",
             "sections": [{"title": "Exp", "kind": "experience", "items": [
                 {"heading": "Engineer", "org": "Acme", "bullets": ["Built it — fast"]}]}]}
    html = T.render_html(dashy, "en", photo="data:image/png;base64,AAAA")
    body = html.split("</head>", 1)[1]
    check("nothing rendered contains an em dash, whatever the text says", "—" not in body)
    check("the photo is rendered when there is one", 'class="photo"' in html)
    check("…and left out when the CV turns it off",
          'class="photo"' not in T.render_html({**dashy, "show_photo": False}, "en",
                                              photo="data:image/png;base64,AAAA"))
    check("…and when there is no photo", 'class="photo"' not in T.render_html(dashy, "en"))
    pcfg_ph = pc.load(HERE / "pipeline.example.toml")
    pcfg_ph.photo = tmp / "me.png"
    (tmp / "me.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 32)
    pcfg_ph.photo_langs = ["fr"]
    check("photo limited to the languages chosen",
          T.photo_uri(pcfg_ph, "fr") is not None and T.photo_uri(pcfg_ph, "en") is None)

    # ----------------------------------------------------- a CV that looks right
    print("\n13. typography and contact line")
    if chrome:
        import subprocess as sp
        pro = {"name": "Ada Lovelace", "headline": "AI Engineer",
               "contact": {"email": "ada@example.org", "phone": "+33 6 00 00 00 00",
                           "links": [{"label": "LinkedIn",
                                      "url": "https://www.linkedin.com/in/ada-lovelace-853a011a5"},
                                     {"label": "Portfolio", "url": "https://ada-lovelace.vercel.app/"},
                                     {"label": "GitHub", "url": "https://github.com/ADA-LOVELACE"}]},
               "summary": "Engineer.", "sections": [
                   {"title": "Experience", "kind": "experience", "items": [
                       {"heading": "AI Engineer", "org": "Acme", "dates": "2025", "bullets": ["Built it."]}]}]}
        fonts_want = {"calibri": "Carlito", "cambria": "Caladea", "arial": "LiberationSans"}
        installed = sp.run(["fc-list", ":", "family"], capture_output=True, text=True).stdout
        for style, face in fonts_want.items():
            if face.replace("LiberationSans", "Liberation Sans") not in installed:
                print(f"  skip  {style} (font not installed)")
                continue
            out = tmp / f"font-{style}.pdf"
            T.html_to_pdf(T.render_html({**pro, "style": style}, "en"), out, chrome)
            emb = sp.run(["pdffonts", str(out)], capture_output=True, text=True).stdout
            check(f"{style}: the real typeface is embedded, not a fallback",
                  face in emb and "Tinos" not in emb, emb.splitlines()[2:4])
        # default: the word is the link, the address is behind it
        out = tmp / "contact.pdf"
        T.html_to_pdf(T.render_html(pro, "en"), out, chrome)
        txt = cr.pdf_text(out, layout=False)
        check("no markup leaks into the contact line", "<span" not in txt and "&" not in txt)
        check("the contact line shows the word, not the address",
              all(w in txt for w in ["LinkedIn", "GitHub", "Portfolio"])
              and "linkedin.com/in/" not in txt, txt[:200])
        urls3 = T.pdf_links(out)
        check("each word carries its real address, clickable in the PDF",
              sorted(urls3) == sorted(l["url"] for l in pro["contact"]["links"]), urls3)
        check("verification confirms every link made it into the PDF",
              T.verify(out, pro, [], max_pages=1) == [])
        # Chrome writes a bare host into the annotation with a trailing slash
        loose = {**pro, "contact": {**pro["contact"], "links": [
            {"label": "Portfolio", "url": "https://ada-lovelace.vercel.app"}]}}
        check("a trailing slash the renderer added is not a missing link",
              T.verify(out, loose, [], max_pages=1) == [])
        gone = {**pro, "contact": {**pro["contact"], "links": pro["contact"]["links"]
                                   + [{"label": "Blog", "url": "https://nowhere.example/"}]}}
        check("a link that never reached the PDF is reported",
              any("not clickable" in p for p in T.verify(out, gone, [], max_pages=1)))

        # link_style = "url" still prints the address, and the old hyphen bug
        # (pdftotext splitting a URL on its dash) must stay fixed there
        out_u = tmp / "contact-url.pdf"
        T.html_to_pdf(T.render_html({**pro, "link_style": "url"}, "en"), out_u, chrome)
        txt_u = cr.pdf_text(out_u, layout=False)
        check("addresses are read whole, never split on their hyphen",
              all(u in txt_u for u in ["linkedin.com/in/ada-lovelace-853a011a5",
                                       "ada-lovelace.vercel.app", "github.com/ADA-LOVELACE"]))
        check("links stay clickable in url mode too", len(T.pdf_links(out_u)) == 3)

    # every CV carries your links, whatever the base PDF had
    prof = {"base": {"linkedin": "linkedin.com/in/souhaib", "github": "https://github.com/s",
                     "portfolio": "souhaib.dev"}, "en": {}, "fr": {}, "answers": []}
    prof["en"] = prof["fr"] = prof["base"]
    pl = T.profile_links("en", prof)
    check("a bare host gets a scheme, or it makes no clickable annotation",
          [l["url"] for l in pl] == ["https://linkedin.com/in/souhaib",
                                     "https://github.com/s", "https://souhaib.dev"], pl)
    bare = T.ensure_links({}, pl)
    check("a CV with no links at all gets all three",
          [l["label"] for l in bare["contact"]["links"]] == ["LinkedIn", "GitHub", "Portfolio"])
    stale = T.ensure_links(
        {"contact": {"links": [{"label": "LinkedIn", "url": "https://linkedin.com/in/old"}]}}, pl)
    check("profile.toml wins over a stale address in the base CV",
          stale["contact"]["links"][0]["url"] == "https://linkedin.com/in/souhaib")
    check("…and the other two are added, not duplicated",
          len(stale["contact"]["links"]) == 3)
    kept = T.ensure_links(
        {"contact": {"links": [{"label": "Kaggle", "url": "https://kaggle.com/x"}]}}, [])
    check("a link only the base CV has is kept", len(kept["contact"]["links"]) == 1)
    unlabelled = T.ensure_links(
        {"contact": {"links": [{"url": "https://github.com/x"}]}}, [])
    check("an address with no word to click is given one",
          unlabelled["contact"]["links"][0]["label"] == "GitHub")
    doc_l = {"contact": {"links": [{"label": "LinkedIn"}, {"label": "Protfolio"}]}}
    real_links = T.pdf_links
    T.pdf_links = lambda p: ["https://www.linkedin.com/in/x", "https://x.vercel.app/",
                             "https://github.com/X"]
    try:
        T.attach_links(doc_l, Path("/dev/null"))
    finally:
        T.pdf_links = real_links
    urls = [l.get("url") for l in doc_l["contact"]["links"]]
    check("real addresses are attached to their labels, even a misspelt one",
          urls == ["https://www.linkedin.com/in/x", "https://x.vercel.app/", "https://github.com/X"], urls)

    # ------------------------------------------------------------ web interface
    print("\n11. web interface: read, edit, validate")
    from fastapi.testclient import TestClient
    import portal
    import webui
    # point the UI at the test database — a connection per request, as in production
    webui._ctx = lambda: (pcfg, cfg, DB(pcfg.db))
    client = TestClient(portal.app)
    H = {"X-CV-Router": "1"}

    check("dashboard state answers", client.get("/api/pipeline/state").status_code == 200)
    r = client.post("/api/jobs", json={"company": "UI Co", "title": "ML Engineer",
                                       "jd": "We build LLM systems in Python. " * 5})
    check("a change without the X-CV-Router header is refused", r.status_code == 403)
    r = client.post("/api/jobs", headers=H, json={"company": "UI Co", "title": "ML Engineer",
                                                  "jd": "We build LLM systems in Python. " * 5})
    jid = r.json().get("job_id", "")
    check("a job can be added by hand", r.status_code == 200 and jid.startswith("manual:"))

    variant = "2-Graduate/AI-ML-Engineering/cv-0.pdf"
    lines = ["Ada 0", "AI Engineer"] + testkit.SAMPLE_TEXT[3:]
    extracted = {"name": "Ada 0", "headline": "AI Engineer", "contact": {},
                 "summary": " ".join(lines[2:]), "sections": [
                     {"title": "Skills", "kind": "skills",
                      "groups": [{"label": "Stack", "items": ["Python", "Docker"]}]}]}
    real_ask = cr.ask_json
    cr.ask_json = lambda *a, **k: json.loads(json.dumps(extracted))
    try:
        O.evaluate_job(db, pcfg, cfg, dict(db.one("SELECT * FROM jobs WHERE id=?", jid)),
                       match_fn=lambda c, jd, **k: {
                           "best_variant": variant, "fit_score": 88, "ats_score": 80,
                           "job_language": "en", "fit_reason": "stub",
                           "suggested_edits": [{"section": "Title", "current": "AI Engineer",
                                                "suggested": "AI Engineer (LLM)"}]})
        if chrome:
            r = client.post(f"/api/job/{jid}/tailor", headers=H)
            check("the CV is tailored from the UI", r.status_code == 200, r.text[:120])
            st = db.one("SELECT status FROM applications WHERE job_id=?", jid)["status"]
            check("a tailored CV starts as a draft you must read", st == "draft", st)

            data = client.get(f"/api/job/{jid}").json()
            check("the editor gets the document, the original and the edit report",
                  data["cv"]["doc"]["headline"] == "AI Engineer (LLM)"
                  and data["cv"]["base"]["headline"] == "AI Engineer"
                  and data["cv"]["meta"]["edits"][0]["status"] == "applied")

            doc = data["cv"]["doc"]
            doc["headline"] = "Machine Learning Engineer — edited by hand"
            html = client.post(f"/api/job/{jid}/preview", json={"doc": doc}).text
            check("preview renders the edited document", "edited by hand" in html)
            r = client.post(f"/api/job/{jid}/cv", headers=H, json={"doc": doc})
            check("saving regenerates the PDF", r.status_code == 200 and r.json()["pages"] == 1,
                  r.text[:120])
            pdf = client.get(f"/job/{jid}/cv.pdf")
            check("the PDF served is the edited one", pdf.status_code == 200)
            p = tmp / "served.pdf"
            p.write_bytes(pdf.content)
            check("…and an ATS reads the hand edit in it", "edited by hand" in cr.pdf_text(p))

            r = client.post(f"/api/job/{jid}/status", headers=H, json={"action": "validate"})
            check("validating moves the draft to ready-to-submit",
                  r.status_code == 200 and r.json()["status"] == "staged")
            r = client.post(f"/api/job/{jid}/status", headers=H, json={"action": "applied"})
            check("outcomes can be recorded from the UI", r.json()["status"] == "applied")

            # a {path} converter swallows slashes, so a sub-route declared after
            # the catch-all would be read as a job id and answered 404
            r = client.get(f"/api/job/{jid}/prefill")
            check("the pre-fill state route resolves, not the catch-all",
                  r.status_code == 200 and r.json()["state"] == "idle", r.text[:80])
            check("the job page says which tier the employer's form is",
                  client.get(f"/api/job/{jid}").json()["tier"] in (1, 2))
            r = client.post(f"/api/job/{jid}/prefill", headers=H)
            check("pre-filling is refused where it is not automated (LinkedIn, Indeed)",
                  r.status_code == 400, r.text[:80])

            r = client.get(f"/api/job/{jid}/autoapply")
            check("the auto-apply state route resolves, not the catch-all",
                  r.status_code == 200 and r.json()["state"] == "idle", r.text[:80])
            r = client.post(f"/api/job/{jid}/autoapply", headers=H, json={})
            check("auto-apply is refused while it is switched off",
                  r.status_code == 400 and "désactiv" in r.text, r.text[:120])
            check("the job page carries the gate, so the panel can show it",
                  client.get(f"/api/job/{jid}").json()["autoapply"]["blockers"] != [])

            # the data browser: 5,000 postings need somewhere to be looked at
            d = client.get("/api/data?per=10").json()
            check("the data view answers with rows, a total and its facets",
                  d["total"] >= 1 and len(d["rows"]) >= 1
                  and {"stage", "source", "status"} <= set(d["facets"]))
            one = client.get(f"/api/data?q={jid.split(':')[-1][:8]}").json()
            filtered = client.get("/api/data?status=applied").json()
            check("a filter narrows the total",
                  filtered["total"] <= d["total"] and all(
                      r["status"] == "applied" for r in filtered["rows"]))
            asc = client.get("/api/data?sort=company&dir=asc&per=50").json()["rows"]
            got = [r["company"] for r in asc]
            check("sorting is applied, and only on known columns",
                  got == sorted(got), f"{got[:6]} vs {sorted(got)[:6]}")
            check("an unknown sort falls back instead of reaching the query",
                  client.get("/api/data?sort=1;DROP TABLE jobs--").status_code == 200
                  and client.get("/api/data").json()["total"] == d["total"])
            csv_r = client.get("/api/data.csv?status=applied")
            check("the rows you filtered come out as a file",
                  csv_r.status_code == 200
                  and "attachment" in csv_r.headers.get("content-disposition", "")
                  and csv_r.text.splitlines()[0].startswith("company,title"))
            check("search needs two letters before it answers",
                  client.get("/api/search?q=a").json()["rows"] == [])
            s_rows = client.get("/api/search?q=UI Co").json()["rows"]
            check("search finds a company by name", any(
                "ui co" in r["company"].lower() for r in s_rows),
                [r["company"] for r in s_rows][:4])
            nb = client.get(f"/api/job/{jid}/neighbours").json()
            check("the neighbours route resolves, not the catch-all",
                  set(nb) == {"prev", "next", "i", "n"}, nb)

            c = client.get("/api/pipeline/charts")
            body = c.json()
            check("the charts endpoint answers with 30 days of series",
                  c.status_code == 200 and len(body["days"]) == 30
                  and all(len(v) == 30 for v in body["series"].values()), c.text[:80])
            check("fit scores are bucketed into ten bands",
                  len(body["fit_hist"]) == 10 and sum(body["fit_hist"]) >= 1)
            a = client.get("/api/pipeline/autoapply").json()
            check("the auto-apply overview lists what is holding each one back",
                  a["enabled"] is False and all("blockers" in r for r in a["rows"]))
        else:
            print("  skip  UI tailoring checks (no Chrome)")
    finally:
        cr.ask_json = real_ask

    shutil.rmtree(tmp)
    print("\n" + ("ALL PASS" if ok else "FAILURES ABOVE"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
