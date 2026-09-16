"""Test helpers: a throwaway config and a real-enough PDF.

The tests must not depend on anyone's actual CV collection, so they build their
own PDF. It has to be a genuine PDF because pdftotext runs on it for real.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import cvrouter as cr

SAMPLE_TEXT = [
    "Ada LOVELACE",
    "AI/ML Engineer | LLM, RAG & MLOps",
    "ada@example.org  +00 000000000",
    "PROFILE  Engineering graduate with production experience building and",
    "industrialising ML and LLM systems: retrieval-augmented generation,",
    "model evaluation, drift monitoring and containerised deployment.",
    "EXPERIENCE  AI Engineer, Example Corp, 2024-2026.",
    "Built an anomaly-detection pipeline and an LLM confirmation layer.",
    "SKILLS  Python, PyTorch, TensorFlow, scikit-learn, LangChain, Docker.",
]


def make_pdf(path: Path, lines: list[str] | None = None) -> Path:
    """Write a minimal one-page PDF whose text pdftotext can extract."""
    lines = lines or SAMPLE_TEXT
    body = "BT /F1 11 Tf 40 750 Td 14 TL\n" + "".join(
        "(" + l.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
        + ") Tj T*\n" for l in lines
    ) + "ET"

    objs = [
        "<</Type/Catalog/Pages 2 0 R>>",
        "<</Type/Pages/Kids[3 0 R]/Count 1>>",
        "<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]"
        "/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>",
        f"<</Length {len(body)}>>stream\n{body}\nendstream",
        "<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>",
    ]

    out, offsets = "%PDF-1.4\n", []
    for i, o in enumerate(objs, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj{o}endobj\n"

    xref_at = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n"
    out += "".join(f"{off:010d} 00000 n \n" for off in offsets)
    out += (f"trailer<</Size {len(objs) + 1}/Root 1 0 R>>\n"
            f"startxref\n{xref_at}\n%%EOF\n")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(out.encode("latin-1"))
    return path


def temp_config(**overrides) -> tuple[cr.Config, Path]:
    """A Config pointing at fresh temp dirs. Caller removes the returned dir."""
    tmp = Path(tempfile.mkdtemp(prefix="cvrouter-test-"))
    cfg = cr.load_config()
    cfg.cv_root = tmp / "CVs"
    cfg.watch_dir = tmp / "Downloads"
    cfg.dupe_dir = tmp / "dupes"
    cfg.index_file = tmp / "index.json"
    cfg.log_file = tmp / "log.txt"
    cfg.seen_file = tmp / "seen.json"          # never touch the real store
    cfg.text_cache_dir = tmp / "textcache"
    cfg.settle_seconds = 0.01
    cfg.notify = {"enabled": False}
    for d in (cfg.cv_root, cfg.watch_dir, cfg.dupe_dir):
        d.mkdir(parents=True, exist_ok=True)
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg, tmp
