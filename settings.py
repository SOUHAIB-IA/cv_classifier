"""Every setting, described once, so the UI can render and write them all.

The two TOML files stay the source of truth: this edits them in place rather
than rewriting them, because their comments explain what each knob does and a
generated file would throw that away. A patch that does not parse is never
kept, so a wrong value cannot leave the app unable to start.

The API key never comes back out. It is written to its own file with owner-only
permissions and reported as "set" plus its last four characters.

One schema drives three things: the form, the validation, and the write. Adding
a setting is one entry here and nothing else.
"""
from __future__ import annotations

import json
import os
import re
import stat
import tomllib
from dataclasses import dataclass
from pathlib import Path

import cvrouter as cr
from pipeline import config as pc

ROOT = Path(__file__).resolve().parent
FILES = {"config": ROOT / "config.toml", "pipeline": ROOT / "pipeline.toml"}


# --------------------------------------------------------------- the schema --
@dataclass
class Field:
    id: str                 # "ai.backend"
    file: str               # config | pipeline
    label: str
    kind: str               # choice | toggle | number | text | tags
    help: str = ""
    options: list | None = None         # [(value, label, note), ...]
    min: float | None = None
    max: float | None = None
    step: float = 1
    unit: str = ""
    depends: str = ""       # "ai.backend=api": only shown when that holds

    @property
    def section(self) -> str:
        return self.id.rsplit(".", 1)[0]

    @property
    def key(self) -> str:
        return self.id.rsplit(".", 1)[1]


# Prices are per million tokens, Anthropic's own API rates. They are shown so
# the choice between models is an informed one rather than a guess.
API_MODELS = [
    ("claude-opus-5", "Opus 5 — le plus capable", "5 $ / 25 $ par million de mots-jetons"),
    ("claude-sonnet-5", "Sonnet 5 — équilibré", "2 $ / 10 $ (recommandé)"),
    ("claude-haiku-4-5", "Haiku 4.5 — le moins cher", "1 $ / 5 $, moins fiable sur le tri"),
]
CLI_MODELS = [
    ("opus", "Opus — le plus capable", "consomme ton quota plus vite"),
    ("sonnet", "Sonnet — équilibré", "recommandé"),
    ("haiku", "Haiku — le plus rapide", "mesuré plus lent ET moins juste ici"),
]

GROUPS: list[tuple[str, str, list[Field]]] = [
    # First, because these four are what a first run is missing. Until the name
    # and the brain are set, start.py does not launch the watcher at all and
    # opens this page instead.
    ("start", "Pour commencer", [
        Field("behaviour.owner_name", "config", "Ton prénom", "text",
              "Sert à deux choses : reconnaître TES CV parmi ceux que tu as pu "
              "télécharger pour quelqu'un d'autre, et nommer les fichiers "
              "rangés. Tant qu'il est vide, rien n'est classé."),
        Field("behaviour.owner_surname", "config", "Ton nom", "text",
              "En majuscules si tu veux le voir en majuscules dans les noms "
              "de fichiers."),
        Field("paths.watch_dir", "config", "Le dossier surveillé", "text",
              "Chaque PDF qui arrive ici est lu, puis rangé s'il s'agit de ton "
              "CV. Un dossier dédié est le choix sûr. Tu peux mettre "
              "~/Downloads, mais alors tous les PDF que tu télécharges y "
              "passent, factures comprises."),
        Field("paths.cv_root", "config", "Où ranger les CV", "text",
              "Le dossier qui reçoit la collection triée. Il est créé s'il "
              "n'existe pas."),
    ]),
    ("brain", "Le cerveau", [
        Field("ai.backend", "config", "Comment payer les appels au modèle", "choice",
              "Ton abonnement Claude n'a pas besoin de clé : le programme lance "
              "Claude Code sur ta machine. Une clé API est facturée à l'usage.",
              options=[("claude_cli", "Mon abonnement Claude", "aucune clé, aucun frais en plus"),
                       ("api", "Une clé API", "facturée au million de mots-jetons")]),
        Field("ai.cli_model", "config", "Modèle", "choice",
              "Sonnet suffit pour trier et adapter un CV.",
              options=CLI_MODELS, depends="ai.backend=claude_cli"),
        Field("ai.provider", "config", "Fournisseur de la clé", "choice",
              "N'importe quelle clé fait l'affaire. Claude est appelé directement ; "
              "tous les autres parlent le même dialecte, celui d'OpenAI. "
              "Un modèle plus petit coûte moins cher et trie moins bien : mesuré "
              "ici, le plus léger gardait la distinction étudiant / diplômé sur "
              "3 CV sur 4, contre 4 sur 4 pour le modèle intermédiaire.",
              options=[(k, v["label"], v["keys_at"]) for k, v in cr.PROVIDERS.items()],
              depends="ai.backend=api"),
        # One key in the file, two shapes on screen: Anthropic's models are a
        # known list with known prices, everyone else's move too fast to pin, so
        # there it is a text box with the provider's usual name suggested.
        Field("ai.model", "config", "Modèle", "model",
              "Le nom exact attendu par ton fournisseur. Les noms changent "
              "souvent : le bouton « Tester » confirme qu'il existe.",
              options=API_MODELS, depends="ai.backend=api"),
        Field("ai.base_url", "config", "Adresse de l'API", "text",
              "Celle de ton fournisseur, jusqu'à /v1 inclus. Laisse vide pour "
              "utiliser l'adresse habituelle du fournisseur choisi.",
              depends="ai.provider=custom"),
        Field("ai.timeout", "config", "Temps maximum par appel", "number",
              "Au-delà, l'appel est abandonné. Une évaluation prend une à deux minutes.",
              min=30, max=900, step=10, unit="secondes"),
    ]),
    ("apply", "Comment postuler", [
        Field("submit.allowed_hosts", "pipeline",
              "Sites dont le formulaire peut être rempli pour toi", "tags",
              "Sur ces sites, un navigateur piloté ouvre le formulaire et le "
              "remplit. Partout ailleurs tu postules à la main. "
              "Un site qui détecte les robots peut refuser cette candidature, et "
              "il a raison de le faire : ce navigateur s'annonce comme automatisé. "
              "Retire l'hôte de la liste et ce site repasse en manuel, avec le "
              "panneau « Remplir à la main » qui te donne tout à coller."),
    ]),
    ("auto", "Envoi automatique", [
        Field("autoapply.enabled", "pipeline", "Envoyer sans me demander", "toggle",
              "Même activé, une candidature ne part que si le système n'a rien eu "
              "à inventer : chaque champ obligatoire rempli depuis ton CV, ton "
              "identité, ou une réponse que tu as écrite. Sinon il s'arrête et "
              "te laisse le formulaire ouvert."),
        Field("autoapply.rehearse", "pipeline", "Mode répétition", "toggle",
              "Toutes les vérifications sont faites jusqu'au bout, puis le "
              "système s'arrête avant le clic. À laisser actif les premières fois.",
              depends="autoapply.enabled=true"),
        Field("autoapply.min_fit", "pipeline", "Score de fit minimum", "number",
              "En dessous, c'est toi qui décides.", min=0, max=100, step=5,
              depends="autoapply.enabled=true"),
        Field("autoapply.min_ats", "pipeline", "Score ATS minimum", "number",
              "", min=0, max=100, step=5, depends="autoapply.enabled=true"),
        Field("autoapply.max_per_day", "pipeline", "Maximum par jour", "number",
              "Un plafond ferme, compté sur le journal des envois.",
              min=1, max=50, depends="autoapply.enabled=true"),
        Field("autoapply.require_validated_cv", "pipeline", "Exiger que j'aie lu le CV",
              "toggle", "Fortement conseillé : sinon un CV part sans que personne "
              "ne l'ait relu.", depends="autoapply.enabled=true"),
    ]),
    ("decide", "Quand agir", [
        Field("thresholds.auto", "pipeline", "Adapter le CV automatiquement à partir de",
              "number", "Au-dessus de ce score de fit, le CV est préparé sans te "
              "demander, et t'attend en brouillon.", min=0, max=100, step=5),
        Field("thresholds.review", "pipeline", "Me demander à partir de", "number",
              "Entre les deux, l'offre va dans la file « à trancher ». En dessous, "
              "elle est écartée.", min=0, max=100, step=5),
        Field("budget.daily_match_budget", "pipeline", "Offres évaluées par jour",
              "number", "Une évaluation coûte deux appels au modèle. C'est la "
              "dépense principale du système.", min=1, max=200),
        Field("budget.max_matches_per_run", "pipeline", "Offres évaluées par cycle",
              "number", "Un cycle tourne toutes les 45 minutes.", min=1, max=50),
    ]),
    ("sources", "Où chercher", [
        Field("sourcing.enabled", "pipeline", "Collecter de nouvelles offres", "toggle",
              "Désactivé, le pipeline continue de tourner sur ce qui est déjà "
              "collecté : il évalue, prépare les CV et te les présente, mais ne "
              "demande plus rien aux tableaux d'offres."),
        Field("sources.greenhouse.boards", "pipeline", "Entreprises sur Greenhouse",
              "tags", "Une étiquette par entreprise, sous la forme "
              "identifiant=Nom affiché. L'identifiant est ce qui apparaît dans "
              "l'adresse de leur page emploi. Utilise « Chercher une entreprise » "
              "ci-dessous si tu ne le connais pas."),
        Field("sources.lever.boards", "pipeline", "Entreprises sur Lever", "tags"),
        Field("sources.ashby.boards", "pipeline", "Entreprises sur Ashby", "tags"),
        Field("sourcing.boards_per_run", "pipeline", "Entreprises interrogées par cycle",
              "number", "Pour étaler la charge sur la journée plutôt que tout "
              "demander d'un coup.", min=1, max=100),
        Field("sourcing.board_min_interval_minutes", "pipeline",
              "Attendre avant de réinterroger la même entreprise", "number",
              "", min=10, max=2880, unit="minutes"),
    ]),
    ("search", "Ce que je cherche", [
        Field("prefilter.title_include", "pipeline", "Intitulés qui m'intéressent", "tags",
              "Un mot par étiquette. Mettre * devant pour accepter aussi les "
              "variantes collées, comme *ml pour MLOps."),
        Field("prefilter.title_exclude", "pipeline", "Intitulés à écarter", "tags",
              "Senior, Lead, Manager… tout ce qui ne te correspond pas encore."),
        Field("prefilter.location_include", "pipeline", "Lieux acceptés", "tags",
              "Villes, pays, ou remote."),
        Field("prefilter.location_exclude", "pipeline", "Lieux à écarter", "tags"),
        Field("prefilter.max_years_required", "pipeline", "Années d'expérience maximum "
              "demandées", "number",
              "Une offre qui demande plus est écartée gratuitement, sans appel au "
              "modèle. 0 désactive ce filtre.", min=0, max=15),
        Field("prefilter.max_age_days", "pipeline", "Ne pas regarder les offres plus "
              "vieilles que", "number", "", min=1, max=730, unit="jours"),
        Field("prefilter.max_per_company", "pipeline",
              "Candidatures simultanées maximum par entreprise", "number",
              "Postuler à sept rôles chez la même entreprise en quelques jours "
              "est lu comme du spam par les plateformes, et c'est toi qui es "
              "signalé. Les mieux notées sont gardées. 0 = pas de plafond.",
              min=0, max=20),
        Field("prefilter.min_score", "pipeline", "Score du tri gratuit minimum", "number",
              "Avant tout appel au modèle, chaque offre reçoit un score gratuit selon "
              "les compétences qu'elle partage avec tes CV. En dessous, elle est "
              "écartée sans coûter d'appel. 0 laisse tout passer et fait dépenser "
              "du quota sur des offres très éloignées.",
              min=0, max=1, step=0.05),
    ]),
    ("cv", "Le CV", [
        Field("tailor.style", "pipeline", "Police", "choice",
              "Chaque CV peut en changer dans l'éditeur.",
              options=[("calibri", "Calibri", "la plus courante"),
                       ("cambria", "Cambria", "avec empattements"),
                       ("garamond", "Garamond", "classique"),
                       ("arial", "Arial", "neutre")]),
        Field("tailor.link_style", "pipeline", "Liens du CV", "choice",
              "Dans les deux cas le lien est cliquable dans le PDF.",
              options=[("label", "Le mot", "LinkedIn, GitHub, Portfolio"),
                       ("url", "L'adresse", "linkedin.com/in/…")]),
        Field("tailor.max_pages", "pipeline", "Nombre de pages visé", "number",
              "Le rendu resserre l'espacement pour tenir, jusqu'à une limite "
              "lisible. Un CV qui déborde encore est signalé, jamais rétréci.",
              min=1, max=3),
        Field("tailor.photo_langs", "pipeline", "Photo sur les CV en", "tags",
              "fr, en. Vide = aucune photo. La photo est courante en France, "
              "souvent déconseillée au Royaume-Uni et aux États-Unis."),
    ]),
]

BY_ID = {f.id: f for g in GROUPS for f in g[2]}


# ------------------------------------------------------------ TOML patching --
def _fmt(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, list):
        return "[" + ", ".join(json.dumps(str(x), ensure_ascii=False) for x in v) + "]"
    return json.dumps(str(v), ensure_ascii=False)


_SECTION = re.compile(r"^\s*\[([^\]]+)\]\s*$")


def _assign(line: str, key: str) -> re.Match | None:
    return re.match(rf"^(\s*){re.escape(key)}(\s*)=(\s*)(.*)$", line)


def patch(text: str, changes: dict[str, object]) -> str:
    """Replace `section.key = value` assignments, keeping everything else.

    Comments, ordering and spacing survive, because in these files the comments
    are the documentation. A key absent from its section is appended to it; a
    section that does not exist yet is created at the end.
    """
    want: dict[str, dict[str, object]] = {}
    for dotted, v in changes.items():
        sec, key = dotted.rsplit(".", 1)
        want.setdefault(sec, {})[key] = v

    out, section, done = [], "", set()
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        m = _SECTION.match(line)
        if m:
            section = m.group(1)
            out.append(line)
            i += 1
            continue
        hit = None
        for key in want.get(section, {}):
            a = _assign(line, key)
            if a:
                hit = (key, a)
                break
        if not hit:
            out.append(line)
            i += 1
            continue
        key, a = hit
        pre, sp1, sp2, rest = a.groups()
        # an array may run over several lines: swallow it whole before replacing
        if rest.lstrip().startswith("[") and rest.count("[") > rest.count("]"):
            depth = rest.count("[") - rest.count("]")
            while depth > 0 and i + 1 < len(lines):
                i += 1
                depth += lines[i].count("[") - lines[i].count("]")
            rest = ""
        comment = ""
        mc = re.search(r"\s+(#.*)$", rest)
        if mc and not rest.lstrip().startswith("#"):
            comment = "   " + mc.group(1)
        out.append(f"{pre}{key}{sp1}={sp2}{_fmt(want[section][key])}{comment}")
        done.add(f"{section}.{key}")
        i += 1

    # keys whose section exists but which were never assigned in it
    missing: dict[str, dict] = {}
    for sec, kv in want.items():
        for key, v in kv.items():
            if f"{sec}.{key}" not in done:
                missing.setdefault(sec, {})[key] = v
    if not missing:
        return "\n".join(out) + "\n"

    final, section = [], ""
    for n, line in enumerate(out):
        m = _SECTION.match(line)
        if m or n == len(out) - 1:
            if m and section in missing:
                while final and not final[-1].strip():
                    final.pop()
                final += [f"{k} = {_fmt(v)}" for k, v in missing.pop(section).items()]
                final.append("")
            if m:
                section = m.group(1)
        final.append(line)
    for sec, kv in missing.items():                  # sections that did not exist
        final += ["", f"[{sec}]"] + [f"{k} = {_fmt(v)}" for k, v in kv.items()]
    return "\n".join(final) + "\n"


class SettingsError(ValueError):
    pass


def coerce(f: Field, v):
    """Turn what the form sent into the type the file expects, or refuse."""
    if f.kind == "toggle":
        return bool(v) if isinstance(v, bool) else str(v).lower() in ("true", "1", "on")
    if f.kind == "number":
        try:
            n = float(v)
        except (TypeError, ValueError):
            raise SettingsError(f"{f.label} : « {v} » n'est pas un nombre")
        if f.min is not None and n < f.min or f.max is not None and n > f.max:
            raise SettingsError(f"{f.label} : garde une valeur entre {f.min:g} et {f.max:g}")
        return int(n) if float(n).is_integer() else n
    if f.kind == "model":
        v = str(v).strip()
        if not v:
            raise SettingsError(f"{f.label} : donne le nom du modèle")
        return v
    if f.kind == "choice":
        ok = [o[0] for o in f.options or []]
        if v not in ok:
            raise SettingsError(f"{f.label} : « {v} » n'est pas un choix possible")
        return v
    if f.kind == "tags":
        items = v if isinstance(v, list) else re.split(r"[,\n]", str(v))
        return [x.strip() for x in items if str(x).strip()]
    return str(v).strip()


def current() -> dict:
    """Every setting's value as it stands in the files."""
    raw = {name: tomllib.loads(p.read_text()) for name, p in FILES.items()}
    out = {}
    for fid, f in BY_ID.items():
        node = raw[f.file]
        for part in f.section.split("."):
            node = node.get(part, {}) if isinstance(node, dict) else {}
        out[fid] = node.get(f.key) if isinstance(node, dict) else None
    return out


def write(changes: dict) -> list[str]:
    """Validate, patch, check it still parses, then replace the file.

    Returns the ids actually changed. Nothing is written if anything is wrong:
    a config file that does not parse would leave the app unable to start, and
    the person who set a value from a web form cannot be asked to repair TOML.
    """
    clean, unknown = {}, [k for k in changes if k not in BY_ID]
    if unknown:
        raise SettingsError(f"réglage inconnu : {', '.join(unknown)}")
    now = current()
    for fid, v in changes.items():
        val = coerce(BY_ID[fid], v)
        if val != now.get(fid):
            clean[fid] = val
    if not clean:
        return []

    thr = {**now, **clean}
    if thr["thresholds.auto"] < thr["thresholds.review"]:
        raise SettingsError("le seuil d'adaptation automatique doit être au-dessus "
                            "du seuil de revue, sinon rien n'arrive jamais en revue")

    for name, path in FILES.items():
        mine = {k: v for k, v in clean.items() if BY_ID[k].file == name}
        if not mine:
            continue
        text = patch(path.read_text(), mine)
        try:
            tomllib.loads(text)
        except tomllib.TOMLDecodeError as e:
            raise SettingsError(f"{path.name} serait illisible après ce changement "
                                f"({e}) : rien n'a été écrit") from e
        tmp = path.with_suffix(path.suffix + ".new")
        tmp.write_text(text)
        os.replace(tmp, path)                        # atomic: no half-written file

    # A folder named here is a folder meant to exist. Creating it now is the
    # difference between a setting that works and one that reports, on the next
    # start, that the place you just chose is not there.
    for fid in ("paths.watch_dir", "paths.cv_root"):
        if fid in clean:
            d = Path(os.path.expanduser(str(clean[fid])))
            if not d.is_absolute():
                d = ROOT / d
            try:
                d.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                raise SettingsError(f"le dossier {d} n'a pas pu être créé : {e}") from e
    return sorted(clean)


# ------------------------------------------------------------------- the key --
def key_state(cfg) -> dict:
    """Whether a key is set and where from. Never the key itself."""
    env = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if env:
        return {"set": True, "source": "env", "hint": "…" + env[-4:]}
    if cfg.key_file.is_file():
        k = cfg.key_file.read_text().strip()
        if k:
            return {"set": True, "source": "file", "hint": "…" + k[-4:],
                    "path": str(cfg.key_file)}
    return {"set": False, "source": None, "hint": "", "path": str(cfg.key_file)}


def save_key(cfg, key: str, provider: str | None = None) -> dict:
    """Write the key to its own file, readable by you alone.

    `provider` is what the page currently has selected, which may not be what
    is saved yet: someone picks Groq and pastes a Groq key before pressing
    Enregistrer, and rejecting it for not starting with sk-ant- would be wrong.
    """
    key = (key or "").strip()
    info = cr.PROVIDERS.get(provider or cfg.provider, {})
    prefix = info.get("prefix", "")
    if key and prefix and not key.startswith(prefix):
        raise SettingsError(
            f"une clé {info.get('label', '')} commence par {prefix} — "
            f"vérifie que c'est bien la clé du fournisseur sélectionné")
    cfg.key_file.parent.mkdir(parents=True, exist_ok=True)
    if not key:
        cfg.key_file.unlink(missing_ok=True)
        return key_state(cfg)
    cfg.key_file.write_text(key + "\n")
    cfg.key_file.chmod(stat.S_IRUSR | stat.S_IWUSR)          # 0600
    return key_state(cfg)


# ------------------------------------------------------------ does it work? --
def test_backend(cfg, timeout: int = 90) -> dict:
    """One tiny real call, so "it works" is measured and not assumed."""
    import time
    system = 'Reply with the JSON object {"ok": true} and nothing else.'
    t0 = time.monotonic()
    try:
        if cfg.backend == "claude_cli":
            binp = Path(cfg.claude_bin) if cfg.claude_bin else cr.find_claude_bin()
            if not binp or not binp.is_file():
                return {"ok": False, "error":
                        "Claude Code n'est pas installé sur cette machine, ou pas "
                        "trouvé. Installe-le, ou passe à une clé API."}
            body = cr._ask_cli(cfg, system, "ping", timeout=timeout)
        elif cfg.provider == "anthropic":
            if not cfg.api_key:
                return {"ok": False, "error": "aucune clé API enregistrée"}
            body = cr._ask_api(cfg, system, "ping", 64)
        else:
            # Every other provider speaks the OpenAI shape, and this branch used
            # to send them through the Anthropic SDK: the Test button failed for
            # Groq, Gemini and the rest whatever the key was. Ollama needs no key
            # at all, and demanding one here made it untestable too.
            info = cr.PROVIDERS.get(cfg.provider, {})
            if not cfg.api_key and not info.get("no_key"):
                return {"ok": False, "error": "aucune clé API enregistrée"}
            body = cr._ask_compatible(cfg, system, "ping", 64)
    except cr.AIError as e:
        return {"ok": False, "error": str(e)[:300]}
    except Exception as e:                            # a key rejected by the API
        return {"ok": False, "error": f"{type(e).__name__}: {str(e)[:250]}"}
    took = round(time.monotonic() - t0, 1)
    if '"ok"' not in body and "ok" not in body.lower():
        return {"ok": False, "error": f"réponse inattendue : {body.strip()[:120]}",
                "seconds": took}
    return {"ok": True, "seconds": took,
            "model": cfg.cli_model if cfg.backend == "claude_cli" else cfg.model}


def schema(cfg, pcfg: pc.PipelineConfig) -> dict:
    """Everything the settings page needs to draw itself."""
    binp = Path(cfg.claude_bin) if cfg.claude_bin else cr.find_claude_bin()
    return {
        "groups": [{"id": gid, "title": title, "fields": [
            {"id": f.id, "label": f.label, "kind": f.kind, "help": f.help,
             "options": f.options, "min": f.min, "max": f.max, "step": f.step,
             "unit": f.unit, "depends": f.depends} for f in fields]}
            for gid, title, fields in GROUPS],
        "values": current(),
        "key": key_state(cfg),
        "claude_bin": str(binp) if binp else "",
        "providers": cr.PROVIDERS,
        "profile_ok": bool(pc.load_profile().get("base")),
        "answers": len(pc.load_profile().get("answers", [])),
    }
