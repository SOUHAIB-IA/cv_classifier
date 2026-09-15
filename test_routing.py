#!/usr/bin/env python3
"""End-to-end test of the filing logic with the model call stubbed out.

Self-contained: throwaway directories and a generated PDF. Touches nothing real.
Run:  ./.venv/bin/python test_routing.py
"""
import shutil
import sys
import tempfile
from pathlib import Path

import cvrouter as cr
import testkit
import watcher as W

FAKE = {
    "is_cv": True, "is_owner": True,
    "branch": "2-Graduate",
    "specialty": "AI-ML-Engineering", "new_specialty": "",
    "qualifier": "RAG-MLOps", "lang": "EN",
    "headline": "AI/ML Engineer | LLM, RAG & MLOps",
    "summary": "Graduate AI/ML engineer CV.", "skills": ["Python", "PyTorch"],
    "confidence": 0.93, "reason": "stub",
}

ok = True


def check(label, cond):
    global ok
    print(("  PASS  " if cond else "  FAIL  ") + label)
    ok = ok and cond


def main():
    cfg, tmp = testkit.temp_config()
    cfg.branches = {"1-Student-Internship": "student", "2-Graduate": "graduate"}
    cfg.roles = {"AI-ML-Engineering": "AI-ML-Engineer"}
    cfg.lang_split = {}
    root, watch, dupes = cfg.cv_root, cfg.watch_dir, cfg.dupe_dir
    REAL_CV = testkit.make_pdf(tmp / "sample.pdf")

    # stub the model
    cr.ask_json = lambda *a, **k: dict(FAKE)

    print("\n1. a downloaded CV gets filed")
    src = watch / "export-from-somewhere (3).pdf"
    shutil.copy(REAL_CV, src)
    r = W.Router(cfg)
    r.handle(src)
    landed = list(root.rglob("*.pdf"))
    check("original removed from Downloads", not src.exists())
    check("exactly one CV filed", len(landed) == 1)
    if landed:
        rel = landed[0].relative_to(root)
        print("        ->", rel)
        check("correct branch", rel.parts[0] == "2-Graduate")
        check("correct specialty", rel.parts[1] == "AI-ML-Engineering")
        check("role in filename", "AI-ML-Engineer" in rel.name)
        check("qualifier in filename", "RAG-MLOps" in rel.name)
        check("language in filename", rel.name.endswith("_EN.pdf"))
    check("indexed", len(cr.Index(cfg).records) == 1)

    print("\n2. the same content downloaded again is treated as a duplicate")
    src2 = watch / "export-from-somewhere (4).pdf"
    shutil.copy(REAL_CV, src2)
    r2 = W.Router(cfg)
    r2.handle(src2)
    check("not filed twice", len(list(root.rglob("*.pdf"))) == 1)
    check("moved to the duplicates folder", len(list(dupes.glob("*.pdf"))) == 1)

    print("\n3. a non-CV PDF is left alone")
    cr.ask_json = lambda *a, **k: {"is_cv": False, "reason": "invoice",
                                   "confidence": 0.99}
    other = watch / "facture.pdf"
    shutil.copy(REAL_CV, other)
    W.Router(cfg).handle(other)
    check("left in Downloads", other.exists())

    print("\n4. someone else's CV is left alone")
    cr.ask_json = lambda *a, **k: {"is_cv": True, "is_owner": False,
                                   "reason": "different person", "confidence": 0.95}
    mate = watch / "someone-else.pdf"
    shutil.copy(REAL_CV, mate)
    W.Router(cfg).handle(mate)
    check("left in Downloads", mate.exists())

    print("\n5. low confidence is left alone")
    cr.ask_json = lambda *a, **k: dict(FAKE, confidence=0.2)
    meh = watch / "incertain.pdf"
    shutil.copy(REAL_CV, meh)
    W.Router(cfg).handle(meh)
    check("left in Downloads", meh.exists())

    print("\n6. partial downloads are ignored")
    part = watch / "en-cours.pdf.crdownload"
    part.write_bytes(b"x")
    W.Router(cfg).handle(part)
    check("still there", part.exists())

    # Regression: `seen` used to be keyed on path alone and never expired, so a
    # second download reusing a filename was silently dropped. Browsers reuse
    # filenames constantly, so this is the common case, not an edge case.
    print("\n7. re-downloading a filename already handled still works")
    import time as _t
    cr.ask_json = lambda *a, **k: dict(FAKE, qualifier="Recur")
    r7 = W.Router(cfg)
    again = watch / "meme-nom.pdf"
    shutil.copy(REAL_CV, again)
    r7.handle(again)
    check("first one filed", not again.exists())
    _t.sleep(0.05)
    shutil.copy(REAL_CV, again)          # same name, new download
    r7.handle(again)
    check("second one not ignored", not again.exists())

    print("\n8. a file left in place is not re-classified on every event")
    calls = {"n": 0}

    def _counting(*a, **k):
        calls["n"] += 1
        return {"is_cv": False, "reason": "invoice", "confidence": 0.99}

    cr.ask_json = _counting
    r8 = W.Router(cfg)
    stays = watch / "facture2.pdf"
    shutil.copy(REAL_CV, stays)
    for _ in range(4):
        r8.handle(stays)
    check("classified once, not four times", calls["n"] == 1)

    shutil.rmtree(tmp)
    print("\n" + ("ALL PASS" if ok else "FAILURES ABOVE"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
