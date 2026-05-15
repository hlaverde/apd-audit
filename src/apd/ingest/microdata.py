"""DANE / INEGI / IBGE / INEI microdata loaders.

Stubs for production. The POC ground truth path runs through
``apd.ingest.lapop.load_or_synthetic``; these loaders will be implemented
when the corresponding national microdata files are available.
"""

from __future__ import annotations

from pathlib import Path


def load_geih_colombia(_path: Path):
    raise NotImplementedError("GEIH ingestion deferred — see DECISIONS.md")


def load_enadis_mexico(_path: Path):
    raise NotImplementedError("ENADIS ingestion deferred — see DECISIONS.md")


def load_pnadc_brazil(_path: Path):
    raise NotImplementedError("PNADC ingestion deferred — see DECISIONS.md")


def load_enaho_peru(_path: Path):
    raise NotImplementedError("ENAHO ingestion deferred — see DECISIONS.md")
