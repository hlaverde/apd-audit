"""Occupational crosswalks: ISCO-08 ↔ CNO-2015 / SINCO / CBO / COP.

Only the three POC occupations are hard-coded here. Full crosswalks will be
loaded from the official CSV/XLSX files published by the four statistical
agencies (see DATA_SOURCES.md) when production runs are scheduled.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OccupationMapping:
    """ISCO-08 anchor + national-classifier code for a single occupation."""

    occupation: str
    isco08_minor: str  # 3-digit ISCO-08 sub-major group code
    cno_2015: str = ""  # Colombia
    sinco_2011: str = ""  # Mexico
    cbo: str = ""  # Brazil
    cop: str = ""  # Peru


POC_MAPPINGS: dict[str, OccupationMapping] = {
    "CEO": OccupationMapping(
        occupation="CEO",
        isco08_minor="112",  # Managing directors and chief executives
        cno_2015="1120",
        sinco_2011="111",
        cbo="121",
        cop="1120",
    ),
    "nurse": OccupationMapping(
        occupation="nurse",
        isco08_minor="222",  # Nursing professionals
        cno_2015="2221",
        sinco_2011="2421",
        cbo="2235",
        cop="2221",
    ),
    "domestic worker": OccupationMapping(
        occupation="domestic worker",
        isco08_minor="911",  # Domestic cleaners and helpers
        cno_2015="9111",
        sinco_2011="9611",
        cbo="5121",
        cop="9111",
    ),
}


def get_mapping(occupation: str) -> OccupationMapping:
    try:
        return POC_MAPPINGS[occupation]
    except KeyError as e:
        raise KeyError(
            f"no crosswalk registered for occupation {occupation!r}. "
            f"Known: {list(POC_MAPPINGS)}",
        ) from e
