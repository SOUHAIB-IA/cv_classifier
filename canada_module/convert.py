"""Turn an indexed resume into a Canadian one.

The converter only rephrases, reorders and reformats. It never adds a fact: the
one thing it may introduce is a `[METRIC?]` placeholder, and only where the
source already made a claim with no figure behind it.

Every change is recorded in a Changelog, with what moved, what it became, and
which rule asked for it. A conversion you cannot audit is a conversion you
cannot trust: the whole point is that a recruiter is reading your words, not the
module's.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from .checker import EMAIL_RX, URL_RX
from .config import CanadaConfig
from .rules import Rules

# Source section titles, in both languages and in the shapes the twelve role
# CVs and the model extractor produce, mapped to the canonical keys the rules
# order by.
SECTION_KEYS = {
    "summary": ("professional summary", "summary", "profile", "profil",
                "sommaire", "sommaire professionnel"),
    "skills": ("technical skills", "skills", "compétences techniques",
               "compétences", "competences"),
    "experience": ("professional experience", "experience", "work experience",
                   "expérience professionnelle", "expérience", "experiences",
                   "expériences professionnelles"),
    "projects": ("projects", "projets", "projets techniques", "key projects"),
    "education": ("education", "formation", "études", "etudes"),
    "certifications": ("certifications", "certification"),
    "languages": ("languages", "langues"),
    "volunteer": ("volunteer", "volunteer experience", "bénévolat", "benevolat"),
}
KEY_OF_TITLE = {t: k for k, ts in SECTION_KEYS.items() for t in ts}

# "LANGUAGES & CERTIFICATIONS" is one section on the role CVs and two in the
# Canada rules, so it is split rather than dropped into one of the two.
COMBINED = re.compile(r"(?i)^\s*(langues?|languages?)\s*[&et]+\s*certifications?\s*$")

FR_MONTH_TO_NUM = {m: i for i, m in enumerate(
    ["janv", "févr", "mars", "avr", "mai", "juin", "juill", "août", "sept",
     "oct", "nov", "déc"], 1)}
EN_MONTH_TO_NUM = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct",
     "nov", "dec"], 1)}

NUM_RANGE = re.compile(r"\b(0?[1-9]|1[0-2])/((?:19|20)\d{2})\b")
ISO = re.compile(r"\b((?:19|20)\d{2})-(0[1-9]|1[0-2])-\d{2}\b")
YEAR_ONLY = re.compile(r"^\s*((?:19|20)\d{2})\s*$")
PRESENT = re.compile(r"(?i)\b(present|présent|à ce jour|current|now|aujourd'hui)\b")

COUNTRY_EN = {"maroc": "Morocco", "morocco": "Morocco", "france": "France",
              "canada": "Canada"}
COUNTRY_FR = {"morocco": "Maroc", "maroc": "Maroc", "france": "France",
              "canada": "Canada"}


@dataclass
class Change:
    what: str                 # the rule or transformation
    where: str                # which part of the document
    before: str = ""
    after: str = ""
    why: str = ""

    def line(self) -> str:
        s = f"  {self.what:<22} {self.where}"
        if self.before or self.after:
            s += f"\n      {self.before!r} -> {self.after!r}"
        if self.why:
            s += f"\n      why: {self.why}"
        return s


@dataclass
class Changelog:
    changes: list[Change] = field(default_factory=list)
    unresolved: list[str] = field(default_factory=list)

    def add(self, what, where, before="", after="", why="") -> None:
        self.changes.append(Change(what, where, str(before), str(after), why))

    def text(self) -> str:
        out = [f"{len(self.changes)} change(s)"]
        out += [c.line() for c in self.changes]
        if self.unresolved:
            out.append(f"\n{len(self.unresolved)} thing(s) only you can settle:")
            out += [f"  - {u}" for u in self.unresolved]
        return "\n".join(out)

    def to_dict(self) -> dict:
        return {"changes": [vars(c) for c in self.changes],
                "unresolved": self.unresolved}


# --------------------------------------------------------------------- text
def _protected(s: str) -> list[tuple[str, str]]:
    """URLs and emails, swapped out so no text rule can touch them."""
    held: list[tuple[str, str]] = []

    def hold(m):
        tok = f"\x00{len(held)}\x00"
        held.append((tok, m.group(0)))
        return tok

    s = EMAIL_RX.sub(hold, s)
    s = URL_RX.sub(hold, s)
    return s, held


def _restore(s: str, held) -> str:
    for tok, orig in held:
        s = s.replace(tok, orig)
    return s


def respell(s: str, rules: Rules, lang: str, log: Changelog, where: str) -> str:
    """Apply the language's substitutions, reporting each one.

    Case is preserved on the first letter, so "Modeling & storage" becomes
    "Modelling & storage" and not "modelling & storage".
    """
    L = rules.lang(lang)
    keep = {k.lower() for k in L.get("keep", [])}
    held_s, held = _protected(s)
    for wrong, right in (L.get("substitute") or {}).items():
        if wrong.lower() in keep:
            continue
        rx = re.compile(rf"\b{re.escape(wrong)}\b", re.IGNORECASE)

        def repl(m):
            got = m.group(0)
            return right.capitalize() if got[:1].isupper() else right

        new = rx.sub(repl, held_s)
        if new != held_s:
            log.add("spelling", where, wrong, right,
                    why="Canadian English" if lang == "en"
                        else "Quebec French usage")
            held_s = new
    return _restore(held_s, held)


# -------------------------------------------------------------------- dates
def _month_name(n: int, rules: Rules, lang: str) -> str:
    key = "en" if lang == "en" else "fr_qc"
    return rules.d["dates"]["months"][key][n - 1]


def reformat_dates(s: str, rules: Rules, lang: str, log: Changelog,
                   where: str) -> str:
    """MM/YYYY and YYYY-MM-DD become the configured 'Mon YYYY'.

    A bare year is left alone: "2023" is already unambiguous and inventing a
    month for it would be inventing a fact.
    """
    orig = s
    sep = rules.d["dates"]["range_separator"]

    def num(m):
        return f"{_month_name(int(m.group(1)), rules, lang)} {m.group(2)}"

    def iso(m):
        return f"{_month_name(int(m.group(2)), rules, lang)} {m.group(1)}"

    s = NUM_RANGE.sub(num, s)
    s = ISO.sub(iso, s)
    s = PRESENT.sub(rules.d["dates"]["present"]["en" if lang == "en"
                                                 else "fr_qc"], s)
    # normalise whatever dash the source used to the configured separator
    s = re.sub(r"\s*[–—-]\s*", sep, s) if re.search(r"\d\s*[–—-]\s*\w", s) else s
    s = re.sub(r"\s{2,}", " ", s).strip()
    if s != orig:
        log.add("date format", where, orig, s,
                why=f"{rules.d['dates']['format']!r}; no source supports ISO")
    return s


# ----------------------------------------------------------------- locations
def normalise_place(s: str, lang: str, log: Changelog, where: str) -> str:
    """A past employer's city stays where it is.

    The City, Province convention describes where the CANDIDATE is, not where a
    foreign employer sits. Rewriting "Rabat, Maroc" as "Rabat, ON" would be a
    lie, so only the country name is translated into the CV's language.
    """
    s = (s or "").strip()
    if not s:
        return s
    parts = [p.strip() for p in s.split(",") if p.strip()]
    table = COUNTRY_EN if lang == "en" else COUNTRY_FR
    out = list(parts)
    if parts and parts[-1].lower() in table:
        want = table[parts[-1].lower()]
        if want != parts[-1]:
            out[-1] = want
    new = ", ".join(out)
    if new != s:
        log.add("place name", where, s, new,
                why="country written in the CV's own language")
    return new


def contact_location(cfg: CanadaConfig, lang: str,
                     rules: Rules | None = None) -> str:
    """The candidate's own location, per config, in the CV's own language.

    This is the real scope of the City, Province convention. The country name and
    the relocation note are both translated: a French CV that reads "Casablanca,
    Morocco - open to relocation to Canada" is a French CV with an English line
    on it, which is how this first came out.
    """
    if cfg.location_mode == "omit":
        return ""
    table = COUNTRY_EN if lang == "en" else COUNTRY_FR
    country = table.get((cfg.country or "").lower(), cfg.country)

    if cfg.location_mode == "city_province":
        city = cfg.city_default or cfg.city
        return f"{city}, {cfg.province}" if cfg.province else city
    if cfg.location_mode == "full_address":
        # Government templates still ask for one; the module will not invent it.
        return ", ".join(x for x in (cfg.city, country) if x)

    base = ", ".join(x for x in (cfg.city, country) if x)
    suffix = cfg.overseas_suffix
    if rules is not None:
        key = "en" if lang == "en" else "fr_qc"
        from_rules = (rules.d.get("contact", {}).get("location", {})
                      .get("overseas_suffix", {}).get(key))
        # The config's value is the English default; the rules file carries the
        # wording for each language, so it wins when the CV is not in English.
        if from_rules and (lang != "en" or not suffix):
            suffix = from_rules
    return f"{base} - {suffix}" if suffix else base


# ------------------------------------------------------------------ sections
def _key_of(title: str) -> str | None:
    return KEY_OF_TITLE.get((title or "").strip().lower())


def split_combined(doc: dict, rules: Rules, lang: str,
                   log: Changelog) -> list[dict]:
    """Split a 'LANGUAGES & CERTIFICATIONS' section into the two the rules name."""
    out = []
    for sec in doc.get("sections", []):
        title = sec.get("title", "")
        if not COMBINED.match(title):
            out.append(sec)
            continue
        langs, certs = [], []
        for line in sec.get("lines", []) or []:
            label = str(line).split(":", 1)[0].strip().lower()
            (certs if "certif" in label else langs).append(line)
        H = rules.headings(lang)
        for key, lines in (("languages", langs), ("certifications", certs)):
            k = key if lang == "en" else {"languages": "langues",
                                          "certifications": "certifications"}[key]
            if lines:
                out.append({"title": H[k], "kind": "list", "lines": lines})
        log.add("section split", title,
                after=" + ".join(H[k] for k in
                                 (("languages", "certifications") if lang == "en"
                                  else ("langues", "certifications"))),
                why="the rules list languages and certifications separately")
    return out


def fold_summary(doc: dict, log: Changelog) -> None:
    """Fold a summary SECTION into doc["summary"].

    The two are the same thing: the template prints one heading from
    doc["summary"], so a document carrying both would show it twice. An empty
    top-level field takes the section's text; a full one keeps what it has, and
    the dropped text goes in the log rather than disappearing.
    """
    keep = []
    for sec in doc.get("sections", []):
        if _key_of(sec.get("title", "")) != "summary":
            keep.append(sec)
            continue
        text = " ".join(str(x).strip() for x in (sec.get("lines") or []) if x)
        if not doc.get("summary") and text:
            doc["summary"] = text
            log.add("summary folded", sec.get("title", ""), after=text[:70],
                    why="the summary is one field, rendered under one heading")
        else:
            log.add("removed section", sec.get("title", ""), before=text[:90],
                    why="duplicates the summary already on the document; the "
                        "text is kept here so nothing is lost silently")
    doc["sections"] = keep


def reorder(sections: list[dict], rules: Rules, lang: str,
            log: Changelog) -> list[dict]:
    """Put the sections in the configured order.

    `summary` is in the order list but is rendered from doc["summary"], not as a
    section, so it takes no slot here.
    """
    want = [k for k in rules.order(lang) if k != "summary"]
    H = rules.headings(lang)
    by_title = {v.strip().lower(): k for k, v in H.items()}

    def rank(sec) -> int:
        t = (sec.get("title") or "").strip().lower()
        key = by_title.get(t) or _key_of(t)
        return want.index(key) if key in want else len(want)

    before = [s.get("title", "") for s in sections]
    out = sorted(sections, key=rank)
    after = [s.get("title", "") for s in out]
    if before != after:
        log.add("section order", "document", " / ".join(before),
                " / ".join(after),
                why="EN follows market practice (skills high for keyword "
                    "extraction); FR-QC follows the OQLF's own order")
    return out


def retitle(sections: list[dict], rules: Rules, lang: str,
            log: Changelog) -> list[dict]:
    H = rules.headings(lang)
    for sec in sections:
        key = _key_of(sec.get("title", ""))
        if key:
            k = key if lang == "en" else {
                "summary": "sommaire", "skills": "competences",
                "experience": "experience", "projects": "projets",
                "education": "formation", "certifications": "certifications",
                "languages": "langues", "volunteer": "benevolat"}[key]
            want = H.get(k)
            if want and want != sec["title"]:
                log.add("section heading", sec["title"], sec["title"], want,
                        why="standard heading an ATS recognises")
                sec["title"] = want
    return sections


def strip_forbidden(doc: dict, rules: Rules, log: Changelog) -> dict:
    """Remove what the Canadian rules exclude, and say what went."""
    if doc.pop("photo", None):
        log.add("removed", "photo", why="Job Bank: not the norm in Canada and "
                                        "can lower your chances; Greenhouse "
                                        "lists it as a parse failure")

    kept = []
    for sec in doc.get("sections", []):
        title = sec.get("title", "")
        hit = next((i for i in rules.forbidden
                    if any(p.search(title) for p in i.patterns)), None)
        if hit:
            log.add("removed section", title, why=hit.why or hit.id)
            continue
        lines = sec.get("lines")
        if lines:
            out = []
            for line in lines:
                bad = next((i for i in rules.forbidden
                            if any(p.search(str(line)) for p in i.patterns)),
                           None)
                if bad:
                    log.add("removed line", title, before=line,
                            why=bad.why or bad.id)
                else:
                    out.append(line)
            sec["lines"] = out
            if not out:
                log.add("removed section", title,
                        why="empty once the excluded lines were removed")
                continue
        kept.append(sec)
    doc["sections"] = kept
    return doc


def flag_openers(doc: dict, rules: Rules, log: Changelog) -> None:
    """Report a weak bullet opener. Do not rewrite it.

    Rewriting "Responsible for the pipeline" into an achievement needs a fact
    the bullet does not contain. Naming it and leaving it is the honest move.
    """
    for sec in doc.get("sections", []):
        for item in sec.get("items", []) or []:
            for b in item.get("bullets") or []:
                for opener in rules.d["bullets"]["banned_openers"]:
                    if str(b).lower().startswith(opener.lower()):
                        log.unresolved.append(
                            f"a bullet opens with {opener!r} and has no result "
                            f"in it: {str(b)[:70]!r}. Rewriting it needs a fact "
                            f"the bullet does not carry.")
                        break


def apply_work_authorization(doc: dict, cfg: CanadaConfig, rules: Rules,
                             lang: str, log: Changelog) -> None:
    if cfg.auth_mode == "omit":
        return
    key = "en" if lang == "en" else "fr_qc"
    if cfg.auth_mode == "one_line":
        line = rules.d["work_authorization"]["templates"]["one_line"][key]
        doc.setdefault("contact", {})["work_authorization"] = line
        log.add("work authorization", "contact", after=line,
                why="config mode one_line, with authorized_to_work = true")
    # relocation_note is already folded into the contact location


def apply_credential(doc: dict, cfg: CanadaConfig, log: Changelog) -> None:
    if cfg.credential_mode == "none":
        return
    if cfg.credential_mode == "equivalence_line" and not cfg.equivalence_text:
        log.unresolved.append(
            "foreign_credential_mode is 'equivalence_line' but "
            "equivalence_text is empty. Only an assessing body can say what a "
            "Moroccan Diplôme d'Ingénieur equals in Canada, so nothing was "
            "written. Fill it in canada.toml, or set the mode to 'none'.")
        return
    for sec in doc.get("sections", []):
        for item in sec.get("items", []) or []:
            if "ENSIASD" in str(item.get("org", "")) or \
               "Supérieure d'IA" in str(item.get("org", "")):
                if cfg.credential_mode == "equivalence_line":
                    add = f" ({cfg.equivalence_text})"
                else:
                    add = f" (ECA: {cfg.eca_body} ref. {cfg.eca_reference})"
                if add.strip() not in item["heading"]:
                    log.add("credential", item.get("heading", ""),
                            item["heading"], item["heading"] + add,
                            why=f"config mode {cfg.credential_mode}")
                    item["heading"] += add
            return


# --------------------------------------------------------------------- entry
def convert(doc: dict, rules: Rules, cfg: CanadaConfig, lang: str,
            ) -> tuple[dict, Changelog]:
    """A Canadian version of `doc`, plus the log of everything that changed."""
    import copy
    d = copy.deepcopy(doc)
    log = Changelog()

    d.pop("_source", None)
    d.pop("density", None)              # the Canada template fits for itself

    strip_forbidden(d, rules, log)

    c = d.setdefault("contact", {})
    loc = contact_location(cfg, lang, rules)
    if c.get("location") != loc:
        log.add("contact location", "contact", c.get("location", ""), loc,
                why=f"config location_mode = {cfg.location_mode}; government "
                    f"templates still ask for an address, career centres do not")
    if loc:
        c["location"] = loc
    else:
        c.pop("location", None)
    apply_work_authorization(d, cfg, rules, lang, log)

    fold_summary(d, log)
    d["sections"] = split_combined(d, rules, lang, log)
    d["sections"] = retitle(d["sections"], rules, lang, log)
    d["sections"] = reorder(d["sections"], rules, lang, log)
    apply_credential(d, cfg, log)

    for key in ("headline", "summary"):
        if d.get(key):
            d[key] = respell(str(d[key]), rules, lang, log, key)
    for sec in d["sections"]:
        where = sec.get("title", "")
        for item in sec.get("items", []) or []:
            for f in ("heading", "org"):
                if item.get(f):
                    item[f] = respell(str(item[f]), rules, lang, log,
                                      f"{where}/{f}")
            if item.get("dates"):
                item["dates"] = reformat_dates(str(item["dates"]), rules, lang,
                                               log, f"{where}/dates")
            if item.get("location"):
                item["location"] = normalise_place(
                    str(item["location"]), lang, log, f"{where}/location")
            item["bullets"] = [respell(str(b), rules, lang, log,
                                       f"{where}/bullet")
                               for b in (item.get("bullets") or [])]
        for grp in sec.get("groups", []) or []:
            if grp.get("label"):
                grp["label"] = respell(str(grp["label"]), rules, lang, log,
                                       f"{where}/label")
            grp["items"] = [respell(str(x), rules, lang, log, f"{where}/skill")
                            for x in (grp.get("items") or [])]
        if sec.get("lines"):
            sec["lines"] = [respell(str(x), rules, lang, log, f"{where}/line")
                            for x in sec["lines"]]

    flag_openers(d, rules, log)

    cap = int(rules.d["sections"]["bullets_per_section"]["max"])
    for sec in d["sections"]:
        for item in sec.get("items", []) or []:
            n = len(item.get("bullets") or [])
            if n > cap:
                log.unresolved.append(
                    f"{sec.get('title')} / {item.get('heading')} has {n} "
                    f"bullets and the cap is {cap}. Which to cut is your call, "
                    f"not the module's.")
    d["canada"] = {"lang": lang, "paper": rules.paper,
                   "built": date.today().isoformat()}
    return d, log
