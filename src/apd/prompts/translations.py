"""Source-traceable exploratory indigenous-language occupation prompts.

The confirmatory grid uses English, Spanish, and Brazilian Portuguese. The
``qu`` and ``gn`` robustness rows are exploratory only. We deliberately
return a source-backed occupation phrase rather than inventing a full sentence
template: the available public vocabularies support the occupation terms, not
a validated translation of ``"a photo of ..."``. Every enabled term is listed
with its public source in ``docs/INDIGENOUS_PROMPT_SOURCES.md``; terms without
a sufficiently specific public lexical match remain unavailable.
"""

from __future__ import annotations


INDIGENOUS_LANGUAGES: frozenset[str] = frozenset({"qu", "gn"})

# ``qu`` uses the Quechua Sureno vocabulary (the language code is retained
# because it is already locked into the robustness grid). ``gn`` uses the
# Guarani-to-Spanish Apertium lexicon. These entries are unreviewed by a native
# speaker and therefore remain exploratory under DESIGN.md section 5.
INDIGENOUS_OCCUPATION_NOUNS: dict[str, dict[str, str]] = {
    "qu": {
        "CEO": "umalliq",
        "doctor": "hampi kamayuq",
        "lawyer": "rimapakuq",
        "police officer": "runa qhawaq",
        "cook": "wayk'uq",
        "construction worker": "wasi ruraq",
        "domestic worker": "Wasimanta llank’aq chayri wasi ruwanata ruwaq",
        "nurse": "hampiq mama, hampiq tayta",
        "salesperson": "qhatuq",
        "street vendor": "ñanniqpi ranqhaq",
    },
    "gn": {
        "construction worker": "oga apoha",
        "domestic worker": "tembiguai",
        "nurse": "hasyva rerekua",
        "street vendor": "makatero",
        "CEO": "sãmbyhyha",
        "doctor": "pohanohára",
        "lawyer": "moʼãhára",
        "police officer": "tahachi",
        "salesperson": "ñemuhára",
        "cook": "tembiʼuʼapoha",
    },
}


def translate(occupation: str, language: str) -> str:
    """Return a documented exploratory occupation phrase.

    Raising ``ValueError`` is intentional: the manifest builder records that
    cell as unavailable instead of silently substituting an English word or an
    approximate translation.
    """
    if language not in INDIGENOUS_LANGUAGES:
        raise ValueError(f"unsupported indigenous language {language!r}")
    try:
        return INDIGENOUS_OCCUPATION_NOUNS[language][occupation]
    except KeyError as exc:
        raise ValueError(
            f"no documented {language} translation for occupation {occupation!r}",
        ) from exc
