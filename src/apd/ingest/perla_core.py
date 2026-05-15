"""PERLA core surveys (Princeton / UCSB) loader.

Stub for production: the PERLA core 2010 surveys provide PERLA tone applied
by interviewers in four LatAm countries, used for ethnic-category-to-PERLA
imputation. Not used in the POC.
"""

from __future__ import annotations

from pathlib import Path


def load_perla_core(_path: Path):
    raise NotImplementedError(
        "PERLA core ingestion deferred — see DATA_SOURCES.md for URL.",
    )
