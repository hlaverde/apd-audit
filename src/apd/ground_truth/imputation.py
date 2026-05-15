"""Ethnic-category ↔ PERLA-tone imputation.

The imputation strategy of §4.2 of the binding proposal is deferred to the
production phase: cross self-declared ethnic category in the main household
survey with the PERLA-coded distribution observed for the same category in
LAPOP / PERLA core. For the POC we use the synthetic-prior shortcut in
``apd.ingest.lapop``.
"""

from __future__ import annotations


def impute_perla_from_ethnic_category(*_args, **_kwargs):
    raise NotImplementedError(
        "Production imputation deferred — POC uses synthetic prior. "
        "See DECISIONS.md D-003.",
    )
