"""The module's own config, read from canada.toml.

Deliberately not merged into config.toml or pipeline.toml: the studio is a
separate tool with its own output folder, and a reader of either of those files
should not have to wonder which half belongs to which program.
"""
from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

LOCATION_MODES = ("city_province", "city_country", "full_address", "omit")
AUTH_MODES = ("omit", "one_line", "relocation_note")
CREDENTIAL_MODES = ("none", "equivalence_line", "eca_reference")


class ConfigError(ValueError):
    pass


@dataclass
class CanadaConfig:
    output_dir: Path
    rules_file: Path
    lang: str
    province: str
    city_default: str
    location_mode: str
    city: str
    country: str
    overseas_suffix: str
    auth_mode: str
    authorized_to_work: bool
    credential_mode: str
    equivalence_text: str
    eca_body: str
    eca_reference: str
    chrome_bin: str
    emit_docx: bool
    path: Path | None = None

    def __post_init__(self) -> None:
        if self.location_mode not in LOCATION_MODES:
            raise ConfigError(f"[contact] location_mode must be one of "
                              f"{LOCATION_MODES}, got {self.location_mode!r}")
        if self.auth_mode not in AUTH_MODES:
            raise ConfigError(f"[work_authorization] mode must be one of "
                              f"{AUTH_MODES}, got {self.auth_mode!r}")
        if self.credential_mode not in CREDENTIAL_MODES:
            raise ConfigError(f"[education] foreign_credential_mode must be one "
                              f"of {CREDENTIAL_MODES}, got "
                              f"{self.credential_mode!r}")
        if self.lang not in ("en", "fr_qc"):
            raise ConfigError(f"[defaults] lang must be 'en' or 'fr_qc', got "
                              f"{self.lang!r}")
        # The one_line mode asserts something about you that no source file can
        # confirm. Refuse it rather than write it on your behalf.
        if self.auth_mode == "one_line" and not self.authorized_to_work:
            raise ConfigError(
                "[work_authorization] mode = 'one_line' writes 'eligible to "
                "work in Canada' on the resume. Set authorized_to_work = true "
                "to confirm that yourself, or use 'omit' / 'relocation_note'.")
        if self.credential_mode == "eca_reference" and not (
                self.eca_body and self.eca_reference):
            raise ConfigError(
                "[education] foreign_credential_mode = 'eca_reference' needs "
                "eca_body and eca_reference. An ECA line without a reference "
                "number is not verifiable.")


def _abs(v: str) -> Path:
    p = Path(v).expanduser()
    return p if p.is_absolute() else (ROOT / p)


def load(path: Path | str | None = None) -> CanadaConfig:
    """Read canada.toml, falling back to canada.example.toml.

    The example is a working config, so the module runs before you have copied
    it — it just writes into the repo's own output folder.
    """
    if path:
        p = Path(path)
    else:
        p = HERE / "canada.toml"
        if not p.is_file():
            p = HERE / "canada.example.toml"
    if not p.is_file():
        raise ConfigError(f"no config at {p}")
    d = tomllib.loads(p.read_text(encoding="utf-8"))

    paths, dflt = d.get("paths", {}), d.get("defaults", {})
    con, auth = d.get("contact", {}), d.get("work_authorization", {})
    edu, ren = d.get("education", {}), d.get("render", {})
    return CanadaConfig(
        output_dir=_abs(paths.get("output_dir", "canada_module/output")),
        rules_file=_abs(paths.get("rules_file",
                                  "canada_module/canada_rules.yaml")),
        lang=dflt.get("lang", "en"),
        province=dflt.get("province", ""),
        city_default=dflt.get("city", ""),
        location_mode=con.get("location_mode", "city_province"),
        city=con.get("city", ""),
        country=con.get("country", ""),
        overseas_suffix=con.get("overseas_suffix", ""),
        auth_mode=auth.get("mode", "omit"),
        authorized_to_work=bool(auth.get("authorized_to_work", False)),
        credential_mode=edu.get("foreign_credential_mode", "equivalence_line"),
        equivalence_text=edu.get("equivalence_text", ""),
        eca_body=edu.get("eca_body", ""),
        eca_reference=edu.get("eca_reference", ""),
        chrome_bin=ren.get("chrome_bin", ""),
        emit_docx=bool(ren.get("emit_docx", True)),
        path=p,
    )
