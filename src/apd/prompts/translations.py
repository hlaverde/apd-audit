"""Validated dialectal-variant prompt translations.

Stub. The main study uses inglés / español peninsular / español
latinoamericano genérico / portugués brasileño as confirmatory languages,
plus quechua and guaraní as exploratory. Translations are produced from
Apertium + open dictionaries + community validation (see DESIGN.md §5
when it exists). The POC uses English only.
"""

from __future__ import annotations


def translate(occupation: str, language: str) -> str:  # pragma: no cover
    raise NotImplementedError(
        "Translation grid deferred — POC uses English only. "
        "See proposal §6.1 and DECISIONS.md.",
    )
