"""DANE / INEGI / IBGE / INEI national-survey microdata loaders.

These loaders serve the **robustness branch** of the data plan
(DECISIONS.md D-014). The primary ground truth path goes through LAPOP
2023 (`apd.ingest.lapop`); the four national surveys here are used to
confirm that the LAPOP-derived f_emp distributions are not artefacts of
that particular instrument.

Each loader's docstring records: (1) the public URL where the file can be
downloaded without institutional credentials, (2) the variable name
carrying the phenotype signal (or ethnic category, if PERLA is to be
imputed), and (3) the variable name carrying the occupation code.

Production wiring will fill these in once a coauthor has actually placed
the raw files in ``data/raw/`` and the variable layout is confirmed
against each survey's published codebook.
"""

from __future__ import annotations

from pathlib import Path


# ---------- Colombia — GEIH 2023 (DANE) ---------------------------------

GEIH_URL = "https://microdatos.dane.gov.co/index.php/catalog/MICRODATOS"
GEIH_CODEBOOK_NOTE = """
GEIH 2023 (Gran Encuesta Integrada de Hogares, DANE).

Phenotype-relevant variables (codebook):
* P6080  : Self-identified ethnic group (afrodescendiente, indígena,
           palenquero, raizal, ROM, ninguno).
* OFICIO : 4-digit CNO-2015 occupation code (Clasificación Nacional de
           Ocupaciones, DANE 2015).
* INGLABO: Monthly labour income (for status weights).

GEIH does NOT carry a direct PERLA tone variable. PERLA is imputed by
crossing P6080 with the PERLA-coded distribution observed in PERLA core
2010 Colombia for the same ethnic categories (Telles 2014 procedure).

Access: requires a free DANE account (email-only). Documented as
non-institutional credential, satisfies the binding spec.
"""


def load_geih_colombia(path: Path):
    """Load and harmonise the GEIH 2023 microdata to the project schema."""
    raise NotImplementedError(
        f"GEIH loader deferred. URL: {GEIH_URL}. "
        f"See module docstring for variable mapping. "
        f"Place the .CSV / .DTA in {path} and implement when needed.",
    )


# ---------- Mexico — ENADIS 2022 (INEGI) --------------------------------

ENADIS_URL = "https://www.inegi.org.mx/programas/enadis/2022/"
ENADIS_CODEBOOK_NOTE = """
ENADIS 2022 (Encuesta Nacional sobre Discriminación, INEGI).

Phenotype-relevant variables (codebook):
* RPESCALA: Skin tone applied by the interviewer using the PERLA palette
            (11 tones). This is the canonical phenotype variable for
            Mexico — ENADIS is the only national survey in our four
            countries to carry PERLA directly.
* P11_3   : 4-digit SINCO-2011 occupation code.
* P10_6   : Monthly income.

Access: public CSV download from the INEGI portal; no account required.
"""


def load_enadis_mexico(path: Path):
    """Load and harmonise the ENADIS 2022 microdata to the project schema."""
    raise NotImplementedError(
        f"ENADIS loader deferred. URL: {ENADIS_URL}. "
        f"See module docstring for variable mapping. "
        f"ENADIS already carries PERLA (RPESCALA) — this is the easiest "
        f"of the four national surveys to wire up. "
        f"Place the .CSV in {path} and implement when needed.",
    )


# ---------- Brazil — PNADC 2023 (IBGE) ----------------------------------

PNADC_URL = "https://www.ibge.gov.br/estatisticas/sociais/trabalho/9171-pesquisa-nacional-por-amostra-de-domicilios-continua-trimestral.html"
PNADC_CODEBOOK_NOTE = """
PNADC 2023 (Pesquisa Nacional por Amostra de Domicílios Contínua, IBGE).

Phenotype-relevant variables (codebook):
* V2010 : Self-declared cor/raça (5 categories: branca, preta, amarela,
          parda, indígena). NOT PERLA — needs imputation.
* VD4002: 4-digit CBO occupation code.
* VD4019: Monthly real labour income (deflated).

PERLA imputation: cross V2010 with the PERLA-coded distribution observed
in PERLA core 2010 Brazil for the same cor/raça categories. The Telles
2014 / Campos-Vázquez & Medina-Cortina 2019 procedure.

Access: public ZIP download from the IBGE portal (each quarter as a
separate file); no account required.
"""


def load_pnadc_brazil(path: Path):
    """Load and harmonise the PNADC 2023 microdata to the project schema."""
    raise NotImplementedError(
        f"PNADC loader deferred. URL: {PNADC_URL}. "
        f"See module docstring for variable mapping. "
        f"PERLA must be imputed from V2010 cor/raça via PERLA core 2010. "
        f"Place the quarterly ZIP files in {path} and implement when needed.",
    )


# ---------- Peru — ENAHO 2023 (INEI) ------------------------------------

ENAHO_URL = "https://proyectos.inei.gob.pe/microdatos/"
ENAHO_CODEBOOK_NOTE = """
ENAHO 2023 (Encuesta Nacional de Hogares, INEI).

Phenotype-relevant variables (codebook):
* P558N : Native-language self-identification (Quechua, Aymara,
          Spanish, etc.); proxy for ethnic affiliation.
* P558  : Ethnic self-identification (mestizo, quechua, aymara,
          afroperuano, blanco, etc.). NOT PERLA — needs imputation.
* P504N : Occupation code (4-digit COP, Clasificación de Ocupaciones del
          Perú).
* I524A1: Monthly income.

PERLA imputation: cross P558 with the PERLA distribution observed in
PERLA core 2010 Peru. ENADIS Peru (if available as a separate file)
carries an interviewer-applied PERLA scale and would be preferred over
the imputation.

Access: public ZIP download from the INEI microdatos portal; no account
required.
"""


def load_enaho_peru(path: Path):
    """Load and harmonise the ENAHO 2023 microdata to the project schema."""
    raise NotImplementedError(
        f"ENAHO loader deferred. URL: {ENAHO_URL}. "
        f"See module docstring for variable mapping. "
        f"PERLA must be imputed from P558 ethnic category via PERLA core 2010 "
        f"(or sourced directly from ENADIS Peru if separately available). "
        f"Place the .CSV / .SAV files in {path} and implement when needed.",
    )


# ---------- Output schema (target for all four loaders) -----------------

NORMALISED_SCHEMA: dict[str, str] = {
    "country": "str — ISO 3166-1 alpha-2 country code ('CO' / 'MX' / 'BR' / 'PE').",
    "respondent_id": "str — unique respondent identifier within the survey.",
    "isco08_minor": "str — 3-digit ISCO-08 minor group code (harmonised "
                    "from the national classifier via the crosswalk).",
    "perla_tone": "int 1..11 — applied (Mexico) or imputed PERLA tone.",
    "perla_source": "str — 'observed' (ENADIS Mexico, LAPOP) or 'imputed' "
                    "(PNADC, ENAHO, GEIH).",
    "income_monthly": "float — monthly labour income in local currency.",
    "weight": "float — survey-design weight for that respondent.",
}
