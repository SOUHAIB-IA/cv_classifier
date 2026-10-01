"""Loading and validating canada_rules.yaml.

Two things matter here beyond parsing. First, a typo in the YAML must be an
error and not silence: a `checks:` entry naming a check the linter does not
implement would otherwise look like a rule that passes. Second, every detection
regex is compiled at load time, so a bad pattern fails on startup instead of
halfway through a report.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

HERE = Path(__file__).resolve().parent
DEFAULT_RULES = HERE / "canada_rules.yaml"

LANGS = ("en", "fr_qc")

# Severities, loosest first. `info` is reported and never fails a document.
SEVERITIES = ("info", "warn", "fail")

# Every check the linter knows how to run. canada_rules.yaml may set the
# severity of these and only these; anything else is a typo.
KNOWN_CHECKS = frozenset({
    "page_count", "paper_size", "column_count", "tables_present",
    "header_footer_present", "images_present", "text_not_selectable",
    "font_not_allowed", "font_size_out_of_range", "multiple_font_families",
    "margins_out_of_range", "forbidden_content", "missing_required_contact",
    "spelling_not_canadian", "date_format", "banned_opener",
    "pronoun_first_person", "bullets_over_max", "metric_placeholder_present",
    "summary_length", "section_order",
})


class RulesError(ValueError):
    """The rules file is wrong. Raised at load time, never mid-report."""


@dataclass
class Forbidden:
    """One entry of `forbidden_content`, with its patterns pre-compiled."""
    id: str
    severity: str
    why: str = ""
    source: str = ""
    patterns: list[re.Pattern] = field(default_factory=list)
    pdf_has_image: bool = False


@dataclass
class Rules:
    d: dict[str, Any]
    path: Path
    forbidden: list[Forbidden]

    # -- accessors the linter uses, so it never indexes the raw dict ---------
    def severity(self, check: str) -> str:
        """The severity for a check, or 'warn' if the file is silent on it."""
        return self.d["checks"].get(check, "warn")

    def enabled(self, check: str) -> bool:
        return self.d["checks"].get(check) != "off"

    def lang(self, lang: str) -> dict:
        key = "en_ca" if lang == "en" else "fr_qc"
        return self.d["language"][key]

    def headings(self, lang: str) -> dict:
        return self.d["sections"]["headings"]["en" if lang == "en" else "fr_qc"]

    def order(self, lang: str) -> list[str]:
        return self.d["sections"]["order"]["en" if lang == "en" else "fr_qc"]

    @property
    def max_pages(self) -> int:
        return int(self.d["document"]["pages"]["max"])

    @property
    def paper(self) -> str:
        return str(self.d["document"]["paper"]).lower()


# Required shape. A missing key here is a RulesError, because the linter would
# otherwise crash on a KeyError deep inside a check.
_REQUIRED = [
    ("document", "pages", "max"),
    ("document", "paper"),
    ("document", "font", "size_pt", "min"),
    ("document", "font", "size_pt", "max"),
    ("document", "font", "allowed"),
    ("document", "layout", "columns"),
    ("contact", "required"),
    ("sections", "order", "en"),
    ("sections", "order", "fr_qc"),
    ("sections", "headings", "en"),
    ("sections", "headings", "fr_qc"),
    ("sections", "bullets_per_section", "max"),
    ("language", "en_ca", "substitute"),
    ("language", "fr_qc", "substitute"),
    ("dates", "format"),
    ("bullets", "banned_openers"),
    ("bullets", "banned_pronouns"),
    ("checks",),
]


def _dig(d: dict, path: tuple[str, ...]):
    cur: Any = d
    for k in path:
        if not isinstance(cur, dict) or k not in cur:
            raise RulesError(f"missing key: {'.'.join(path)}")
        cur = cur[k]
    return cur


def load_rules(path: Path | str | None = None) -> Rules:
    p = Path(path) if path else DEFAULT_RULES
    if not p.is_file():
        raise RulesError(f"no rules file at {p}")
    try:
        d = yaml.safe_load(p.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise RulesError(f"{p}: {e}") from e
    if not isinstance(d, dict):
        raise RulesError(f"{p}: expected a mapping at the top level")

    for req in _REQUIRED:
        _dig(d, req)

    unknown = sorted(set(d["checks"]) - KNOWN_CHECKS)
    if unknown:
        raise RulesError(
            f"{p}: checks the linter does not implement: {', '.join(unknown)}. "
            "A check named here but not implemented would look like a rule that "
            "passes.")
    bad_sev = {k: v for k, v in d["checks"].items()
               if v not in SEVERITIES and v != "off"}
    if bad_sev:
        raise RulesError(f"{p}: severity must be one of "
                         f"{SEVERITIES + ('off',)}: {bad_sev}")

    forbidden = []
    for item in d.get("forbidden_content", []):
        if "id" not in item:
            raise RulesError(f"{p}: a forbidden_content entry has no id")
        det = item.get("detect", {}) or {}
        pats = []
        for raw in det.get("patterns", []):
            try:
                pats.append(re.compile(raw, re.MULTILINE))
            except re.error as e:
                raise RulesError(
                    f"{p}: forbidden_content[{item['id']}]: bad regex "
                    f"{raw!r}: {e}") from e
        sev = item.get("severity", "warn")
        if sev not in SEVERITIES:
            raise RulesError(f"{p}: forbidden_content[{item['id']}]: "
                             f"severity {sev!r} not in {SEVERITIES}")
        forbidden.append(Forbidden(
            id=item["id"], severity=sev, why=item.get("why", ""),
            source=item.get("source", ""), patterns=pats,
            pdf_has_image=bool(det.get("pdf_has_image", False))))

    return Rules(d=d, path=p, forbidden=forbidden)
