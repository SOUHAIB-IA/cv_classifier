"""Tailor a Canadian resume to one posting, without writing a word of it.

Everything here is selection and ordering. The posting decides which of your own
sentences go first and which of your own skills lead the list; it never decides
what they say. A term the posting wants and your CV does not have is reported as
a gap, never inserted — a resume that claims Kubernetes because the ad asked for
it is a resume that fails the interview.

The match score is a heuristic and says so: the share of the posting's technical
vocabulary your document already contains, weighted by how often the posting
repeats each term. It predicts keyword overlap, which is what a parser ranks on.
It does not predict whether you get the job.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from .checker import _doc_text, strip_links
from .convert import Changelog
from .rules import Rules

HERE = Path(__file__).resolve().parent

# Quebec and the French track. A posting in French, or anywhere in Quebec, gets
# the French CV unless you say otherwise.
QC_PLACES = ("quebec", "montreal", "laval", "gatineau", "sherbrooke",
             "trois-rivieres", "levis", "longueuil", "saguenay", "qc")
FR_WORDS = ("et", "les", "des", "une", "nous", "vous", "poste", "experience",
            "competences", "entreprise", "equipe", "developpement", "chez",
            "sein", "notre", "pour", "avec", "sera", "doit", "sont")

TOKEN = re.compile(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ0-9+#/_-]*(?:\.[A-Za-zÀ-ÿ0-9+#]+)*")

# A gram never crosses a clause: "Airflow or dbt for orchestration" produced the
# gram "airflow or dbt", and "analytics. Build" produced "analytics build",
# neither of which anyone wrote.
SPLIT = re.compile(r"[.;:!?\n•‣·]+|\s[-–—]\s|,")

# Structural words. A gram containing one is two fragments the ad's own
# punctuation glued together.
GLUE = frozenset("""
a an and or the of to in on at for with without by from as is are be been being
was were do does did have has had will would can could may might must shall
should this that these those it its their our your my his her them us we you
not no nor so than then there here when where which who whom whose what how why
all more most other some such own any both each few own very just about into
le la les un une des du de au aux et ou mais donc ni car que qui quoi dont
pour par avec sans sous sur dans chez vers est sont sera etre avoir nous vous
ils elles on ce cet cette ces son sa ses leur leurs plus moins tres tout tous
toute toutes comme afin ainsi
""".split())


def fold(s: str) -> str:
    """Casefold and strip accents, so 'Modélisation' matches 'modelisation'."""
    s = unicodedata.normalize("NFKD", s.lower())
    return "".join(c for c in s if not unicodedata.combining(c))


_vocab_cache: tuple[frozenset[str], frozenset[str]] | None = None


def vocab() -> tuple[frozenset[str], frozenset[str]]:
    """The glossary from keywords.yaml: (generic, technical)."""
    global _vocab_cache
    if _vocab_cache is None:
        import yaml
        d = yaml.safe_load((HERE / "keywords.yaml").read_text(
            encoding="utf-8")) or {}
        generic = {fold(w.strip()) for line in (d.get("generic") or [])
                   for w in str(line).split(",") if w.strip()}
        tech = {fold(t.strip()) for group in (d.get("technical") or {}).values()
                for t in group if str(t).strip()}
        _vocab_cache = (frozenset(generic), frozenset(tech))
    return _vocab_cache


def technical_shape(raw: str) -> bool:
    """A token that looks like tooling even when the glossary has not met it.

    Three shapes carry the signal: a symbol or digit inside the word (ci/cd, s3,
    c++, node.js), an all-caps acronym (ETL, SRE), and a CamelCase name
    (BigQuery, PySpark). Anything else has to earn its place in keywords.yaml.
    """
    core = raw.strip(".,;:()[]")
    if any(c in core for c in "+#/_") or any(c.isdigit() for c in core):
        return True
    if len(core) >= 2 and core.isupper() and core.isalpha():
        return True
    return bool(re.match(r"^[A-Z][a-z]+[A-Z][a-zA-Z]*$", core))


def terms(text: str, max_n: int = 3) -> dict[str, int]:
    """Every gram worth counting, folded, with its frequency."""
    out: dict[str, int] = {}
    for clause in SPLIT.split(strip_links(text)):
        words = [fold(w) for w in TOKEN.findall(clause)]
        for n in range(1, max_n + 1):
            for i in range(len(words) - n + 1):
                gram = words[i:i + n]
                if any(w in GLUE for w in gram):
                    continue
                if n == 1 and len(gram[0]) < 2:
                    continue
                key = " ".join(gram)
                out[key] = out.get(key, 0) + 1
    return out


def keywords(text: str) -> dict[str, int]:
    """The terms in `text` that could plausibly be an ATS keyword.

    A term qualifies when the glossary knows it, or when a single token looks
    technical by shape. Everything else is a word the ad happens to repeat.
    """
    generic, tech = vocab()
    raws: dict[str, str] = {}
    for clause in SPLIT.split(strip_links(text)):
        for w in TOKEN.findall(clause):
            raws.setdefault(fold(w), w)
    out: dict[str, int] = {}
    for term, n in terms(text).items():
        if term in generic:
            continue
        if term in tech:
            out[term] = n
        elif " " not in term and term in raws and technical_shape(raws[term]):
            out[term] = n
    return out


@dataclass
class Match:
    """What the posting asked for, and what your document already answers."""
    score: int
    matched: list[tuple[str, int]] = field(default_factory=list)
    gaps: list[tuple[str, int]] = field(default_factory=list)
    lang: str = "en"
    reason: str = ""

    def to_dict(self) -> dict:
        return {"score": self.score, "lang": self.lang, "reason": self.reason,
                "matched": self.matched[:40], "gaps": self.gaps[:40]}

    def text(self) -> str:
        out = [f"ATS keyword match {self.score}/100  [{self.lang}]",
               f"  {self.reason}"]
        if self.matched:
            out.append("  in the CV already: "
                       + ", ".join(t for t, _ in self.matched[:20]))
        if self.gaps:
            out.append("  asked for, not in the CV: "
                       + ", ".join(f"{t} (x{n})" for t, n in self.gaps[:20]))
            out.append("  (reported, never inserted: a term you cannot defend "
                       "in an interview costs more than it gains)")
        return "\n".join(out)


def pick_lang(jd: str, location: str = "", override: str | None = None
              ) -> tuple[str, str]:
    """EN or Quebec French, and the reason for it."""
    if override:
        return override, "you chose it"
    place = fold(location or "")
    if any(re.search(rf"\b{p}\b", place) for p in QC_PLACES):
        return "fr_qc", f"the posting is in Quebec ({location})"
    words = [fold(w) for w in TOKEN.findall(jd)]
    if not words:
        return "en", "nothing to go on, defaulting to English"
    hits = sum(1 for w in words if w in FR_WORDS)
    if hits / max(1, len(words)) > 0.04:
        return "fr_qc", "the posting itself is written in French"
    return "en", "the posting is written in English"


def match(doc: dict, jd: str, rules: Rules, lang: str) -> Match:
    """Score the document against the posting, over the technical vocabulary.

    Denominator: the posting's keywords, weighted by how often it repeats each
    one, since an ad that says "Kafka" five times is telling you something. The
    first version scored over every repeated word and produced a number built on
    "looking" and "build and maintain" — a word-frequency score wearing a
    keyword score's name.
    """
    jd_terms = keywords(jd)
    cv_terms = set(keywords(_doc_text(doc)))

    matched = sorted(((t, n) for t, n in jd_terms.items() if t in cv_terms),
                     key=lambda x: (-x[1], x[0]))
    gaps = sorted(((t, n) for t, n in jd_terms.items() if t not in cv_terms),
                  key=lambda x: (-x[1], x[0]))
    total = sum(jd_terms.values())
    got = sum(n for _, n in matched)
    return Match(score=round(100 * got / total) if total else 0,
                 matched=matched, gaps=gaps, lang=lang,
                 reason=f"{len(matched)} of {len(jd_terms)} posting keyword(s) "
                        f"present, weighted by how often the ad repeats each")


# --------------------------------------------------------------- re-ordering
# A bullet that opens by referring back to the one above it cannot be promoted:
# "Built the delivery chain around it" reads as nonsense in first position, and
# reordering produced exactly that on the first posting this was tried on.
BACKREF = re.compile(
    r"(?i)^\W*(?:\w+\s+){0,7}?\b(?:it|them|this|that|these|those|the latter|"
    r"the same|the above|il|elle|le|la|les|celui-ci|celle-ci|ceux-ci|"
    r"cette derni[eè]re|ce dernier|y)\b")


def pinned(bullet: str) -> bool:
    """True when the bullet leans on the one before it and must not move up."""
    head = " ".join(str(bullet).split()[:9])
    return bool(BACKREF.search(head))


def _density(text: str, wanted: set[str]) -> int:
    """How many of the posting's keywords this piece of text already contains."""
    return len(set(keywords(text)) & wanted)


def emphasise(doc: dict, m: Match, log: Changelog, *, bullets: bool = True,
              skills: bool = True, summary: bool = True) -> dict:
    """Reorder what the posting cares about to the front. Rewrite nothing.

    Every sort is stable, so two pieces the posting treats alike keep the order
    you gave them: an experience's bullets are a problem, a solution and a result
    in that order, and shuffling equals would break the reading.
    """
    import copy
    d = copy.deepcopy(doc)
    wanted = {t for t, _ in m.matched}
    if not wanted:
        log.add("emphasis", "document",
                why="the posting matched none of your terms, so nothing moved")
        return d

    if summary and d.get("summary"):
        parts = re.split(r"(?<=[.!?])\s+", str(d["summary"]).strip())
        if len(parts) > 1:
            new = sorted(parts, key=lambda s: -_density(s, wanted))
            if new != parts:
                d["summary"] = " ".join(new)
                log.add("summary order", "summary", parts[0][:50], new[0][:50],
                        why="the sentence the posting matches most goes first; "
                            "the wording is untouched")

    for sec in d.get("sections", []):
        where = sec.get("title", "")
        if skills and sec.get("kind") == "skills":
            groups = sec.get("groups") or []
            new = sorted(groups, key=lambda g: -_density(
                f"{g.get('label', '')} {' '.join(g.get('items') or [])}", wanted))
            if [g.get("label") for g in new] != [g.get("label") for g in groups]:
                sec["groups"] = new
                log.add("skills order", where,
                        " / ".join(str(g.get("label")) for g in groups),
                        " / ".join(str(g.get("label")) for g in new),
                        why="the group the posting asks about leads")
            for g in sec["groups"]:
                items = g.get("items") or []
                if len(items) == 1 and "," in items[0]:
                    bits = [b.strip() for b in items[0].split(",") if b.strip()]
                    ordered = sorted(bits, key=lambda b: -_density(b, wanted))
                    if ordered != bits:
                        g["items"] = [", ".join(ordered)]
                        moved = sum(1 for a, b in zip(bits, ordered) if a != b)
                        log.add("skill order", f"{where}/{g.get('label')}",
                                f"{moved} of {len(bits)} items moved",
                                ordered[0],
                                why="matched tools first inside the group")

        if bullets:
            for item in sec.get("items") or []:
                bs = [b for b in (item.get("bullets") or []) if b]
                if len(bs) < 2:
                    continue
                # A pinned bullet keeps its index; the rest reorder around it.
                free = [i for i, b in enumerate(bs) if not pinned(b)]
                ordered = sorted((bs[i] for i in free),
                                 key=lambda b: -_density(str(b), wanted))
                new = list(bs)
                for slot, text in zip(free, ordered):
                    new[slot] = text
                held = [b for b in bs if pinned(b)]
                if held and new != bs:
                    log.add("bullet held", f"{where}/{item.get('heading')}",
                            str(held[0])[:50],
                            why="it opens by referring back to the bullet above "
                                "it, so promoting it would strand the reference")
                if new != bs:
                    item["bullets"] = new
                    log.add("bullet order", f"{where}/{item.get('heading')}",
                            str(bs[0])[:50], str(new[0])[:50],
                            why="the bullet the posting matches most goes "
                                "first; no bullet was rewritten")
    return d


# ------------------------------------------------------------- role selection
ROLE_HINTS = {
    "ai": ("llm", "rag", "langchain", "langgraph", "generative", "agent",
           "prompt engineering", "fine-tuning", "embeddings", "agentic"),
    "mlops": ("mlops", "mlflow", "model registry", "drift", "retraining",
              "model serving", "feature store", "model monitoring"),
    "devops": ("devops", "kubernetes", "terraform", "ci/cd", "sre", "helm",
               "ansible", "observability", "infrastructure as code"),
    "ds": ("data scientist", "experimentation", "a/b test", "forecasting",
           "scikit-learn", "feature engineering", "classification", "regression"),
    "de": ("data engineer", "etl", "elt", "data pipeline", "data warehouse",
           "airflow", "dbt", "spark", "kafka", "snowflake", "data modeling",
           "ingestion", "data quality"),
    "swe": ("software engineer", "backend", "microservices", "spring boot",
            "react", "nodejs", "typescript", "rest api", "graphql"),
}


def pick_role(jd: str) -> tuple[str, str]:
    """Which of the six CVs the posting is closest to, with no model call.

    Keyword overlap against each role's own vocabulary. It is a cheap guess and
    the CLI always lets you override it, because a posting titled "Data Engineer"
    that is really a platform job should go to the CV you choose.
    """
    t = keywords(jd)
    scored = sorted(((sum(t.get(fold(h), 0) for h in hints), role)
                     for role, hints in ROLE_HINTS.items()), reverse=True)
    best, second = scored[0], scored[1]
    if best[0] == 0:
        return "swe", ("nothing in the posting pointed to a role; "
                       "choose one with --role")
    close = f", close to {second[1]}" if second[0] >= best[0] * 0.8 else ""
    return best[1], f"{best[0]} role keyword hit(s){close}"
