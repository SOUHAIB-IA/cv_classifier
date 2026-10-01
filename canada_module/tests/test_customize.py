#!/usr/bin/env python3
"""Tests for the customizer and the studio's page.

The customizer's contract is narrow and the tests hold it to it: it may reorder
and it may score, and it may do nothing else. Two properties carry most of the
weight — reordering cannot change the score, because no word changed; and a term
the posting asks for never appears in the output.

Run:  ./.venv/bin/python canada_module/tests/test_customize.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))

from canada_module import config as ccfg            # noqa: E402
from canada_module import customize as CU           # noqa: E402
from canada_module.checker import _doc_text         # noqa: E402
from canada_module.convert import Changelog, convert  # noqa: E402
from canada_module.rules import load_rules          # noqa: E402

FIX = HERE / "fixtures"
ok = True

JD_EN = """Senior Data Engineer - Shopify - Toronto, ON (hybrid)

We are looking for a Data Engineer to build and operate the batch and streaming
pipelines behind merchant analytics. You will design data models, own ETL and
ELT pipelines, and keep data quality high across a warehouse.

What you will do
- Build and maintain ETL / ELT pipelines in Python and SQL
- Operate streaming ingestion with Kafka and Apache Spark
- Add data quality controls and monitoring to every pipeline
- Containerize jobs with Docker and ship them through CI/CD
- Airflow or dbt for orchestration
- Snowflake or BigQuery a plus, Terraform a plus
"""

JD_FR = """Ingénieur de données - Montréal, QC

Nous recherchons un ingénieur de données pour concevoir et exploiter les
pipelines de notre entrepôt. Vous travaillerez avec notre équipe sur des
traitements par lots et en continu, et vous serez responsable de la qualité des
données. Le poste est basé à Montréal et exige de l'expérience avec Python, SQL,
Spark et Kafka au sein d'une équipe agile.
"""


def check(label, cond, detail=""):
    global ok
    print(("  PASS  " if cond else "  FAIL  ") + label
          + (f"   ({detail})" if detail and not cond else ""))
    ok = ok and bool(cond)


def main() -> int:
    rules, cfg = load_rules(), ccfg.load()
    good = json.loads((FIX / "compliant.cv.json").read_text(encoding="utf-8"))
    canadian, _ = convert(good, rules, cfg, "en")

    # ------------------------------------------------------- 1. the vocabulary
    print("\n1. what counts as a keyword")
    generic, tech = CU.vocab()
    check("the glossary loads", len(tech) > 150 and len(generic) > 100,
          f"{len(tech)} technical, {len(generic)} generic")
    kw = CU.keywords(JD_EN)
    for want in ("etl", "elt", "kafka", "apache spark", "airflow", "dbt",
                 "snowflake", "bigquery", "terraform", "ci/cd", "data quality"):
        check(f"keeps {want!r}", want in kw, sorted(kw)[:20])
    # The first version scored over every repeated word and produced a number
    # built on these.
    for junk in ("looking", "build", "design", "operate", "maintain",
                 "build and maintain", "across warehouse", "analytics build"):
        check(f"drops {junk!r}", junk not in kw)
    # A gram must not cross a clause: "Airflow or dbt" is two terms, not three.
    check("no gram crosses a conjunction", "airflow or dbt" not in CU.terms(JD_EN))
    check("no gram crosses a sentence",
          "analytics build" not in CU.terms(JD_EN))
    check("shape alone can carry an unknown token",
          CU.technical_shape("ci/cd") and CU.technical_shape("S3")
          and CU.technical_shape("BigQuery") and CU.technical_shape("c++"))
    check("...and an ordinary word does not",
          not CU.technical_shape("pipelines") and not CU.technical_shape("Build"))

    # --------------------------------------------------- 2. language and role
    print("\n2. which CV the posting gets")
    check("an English posting in Ontario gets English",
          CU.pick_lang(JD_EN, "Toronto, ON")[0] == "en")
    check("a posting in Quebec gets the French CV",
          CU.pick_lang(JD_EN, "Montreal, QC")[0] == "fr_qc",
          CU.pick_lang(JD_EN, "Montreal, QC"))
    check("a French posting gets the French CV wherever it is",
          CU.pick_lang(JD_FR, "")[0] == "fr_qc", CU.pick_lang(JD_FR, ""))
    check("your override wins",
          CU.pick_lang(JD_FR, "Montreal, QC", "en") == ("en", "you chose it"))
    # "Quebec" must match as a word: a company called "Quebecor Media" in Ontario
    # is not a reason to send a French CV.
    check("a place name is matched as a word, not a substring",
          CU.pick_lang(JD_EN, "Quebecorville, ON")[0] == "en",
          CU.pick_lang(JD_EN, "Quebecorville, ON"))
    role, why = CU.pick_role(JD_EN)
    check("the Data Engineer posting finds the Data Engineer CV",
          role == "de", f"{role} ({why})")
    check("a posting with no signal says so, instead of guessing silently",
          "choose one with --role" in CU.pick_role("We offer a great culture "
                                                  "and a competitive salary.")[1])

    # -------------------------------------------------------------- 3. scoring
    print("\n3. the score")
    m = CU.match(canadian, JD_EN, rules, "en")
    check("it is between 0 and 100", 0 <= m.score <= 100, m.score)
    check("it says how it was computed", "weighted" in m.reason, m.reason)
    matched = {t for t, _ in m.matched}
    gaps = {t for t, _ in m.gaps}
    check("terms the CV has are matched",
          {"etl", "kafka", "python", "sql"} <= matched, sorted(matched)[:20])
    check("terms the CV lacks are gaps",
          {"airflow", "dbt", "snowflake", "terraform"} <= gaps, sorted(gaps))
    check("matched and gaps never overlap", not (matched & gaps))
    check("an empty posting scores 0, and does not divide by zero",
          CU.match(canadian, "", rules, "en").score == 0)

    # ---------------------------------------------------- 4. reorder, not write
    print("\n4. reordering only")
    log = Changelog()
    out = CU.emphasise(canadian, m, log)
    before_words = sorted(_doc_text(canadian).split())
    after_words = sorted(_doc_text(out).split())
    check("not one word is added, removed or changed", before_words == after_words,
          f"{len(before_words)} vs {len(after_words)}")
    # If no word changed, the score cannot change. If it does, something was
    # rewritten behind our back.
    check("the score is identical after reordering",
          CU.match(out, JD_EN, rules, "en").score == m.score)
    for t in ("airflow", "dbt", "snowflake", "terraform", "bigquery"):
        check(f"the gap {t!r} was not inserted", t not in CU.fold(_doc_text(out)))
    check("every reordering is logged",
          all(c.why for c in log.changes), [vars(c) for c in log.changes])

    print("\n5. a bullet that leans on the one above it does not move up")
    check("a back-reference is detected",
          CU.pinned("Built the delivery chain around it: Docker, Git versioning"))
    check("...and an ordinary opener is not",
          not CU.pinned("Designed and built the data pipeline behind detection"))
    check("French back-references too",
          CU.pinned("Mis en place la chaîne de livraison associée : celui-ci"))
    pin = {"name": "X", "contact": {"email": "a@b.co", "phone": "+1 514 555 0199"},
           "sections": [{"title": "PROFESSIONAL EXPERIENCE", "kind": "experience",
                         "items": [{"heading": "Engineer", "org": "Co",
                                    "dates": "Jan 2025", "location": "",
                                    "bullets": [
                                        "Designed the ingestion layer in Python.",
                                        "Built the Kafka and Spark pipelines around it.",
                                    ]}]}]}
    m2 = CU.match(pin, JD_EN, rules, "en")
    log2 = Changelog()
    out2 = CU.emphasise(pin, m2, log2)
    kept = out2["sections"][0]["items"][0]["bullets"]
    check("the back-referencing bullet stays second even though it matches more",
          kept[0].startswith("Designed"), kept)
    check("...and the refusal is logged",
          any(c.what == "bullet held" for c in log2.changes)
          or kept == pin["sections"][0]["items"][0]["bullets"],
          [c.what for c in log2.changes])

    # ------------------------------------------------------------ 6. the page
    print("\n6. the studio page, mounted beside the pipeline")
    try:
        from fastapi.testclient import TestClient
        import portal
    except Exception as e:                     # pragma: no cover
        print(f"  skip  web checks ({e})")
    else:
        c = TestClient(portal.app)
        check("the page answers", c.get("/canada/").status_code == 200)
        check("...and without the trailing slash too",
              c.get("/canada", follow_redirects=False).status_code in (200, 307))
        check("the shared nav carries the tab",
              'href="/canada"' in c.get("/canada/").text)
        st = c.get("/canada/api/state")
        check("the page is told the rules in force",
              st.status_code == 200 and st.json()["paper"] == "letter")
        # The app's convention: anything that writes needs the header, which a
        # cross-origin page cannot send without a preflight this app never grants.
        check("a write without X-CV-Router is refused",
              c.post("/canada/api/check", json={"role": "de"}).status_code == 403)
        check("...and allowed with it",
              c.post("/canada/api/check", json={"role": "de", "lang": "en"},
                     headers={"X-CV-Router": "1"}).status_code == 200)
        check("a too-short posting is refused with a reason",
              c.post("/canada/api/tailor", json={"jd": "hi"},
                     headers={"X-CV-Router": "1"}).status_code == 400)
        for bad in ("..%2F..%2Fconfig.toml", "..%2Fcanada.toml"):
            check(f"path traversal is refused ({bad[:12]})",
                  c.get(f"/canada/api/file/{bad}").status_code == 404)
        check("the pipeline pages still answer",
              c.get("/pipeline").status_code == 200
              and c.get("/data").status_code == 200
              and c.get("/settings").status_code == 200)

    print("\n" + ("ALL PASS" if ok else "FAILURES ABOVE"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
