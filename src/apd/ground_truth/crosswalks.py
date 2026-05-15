"""Occupational crosswalks: ISCO-08 ↔ national classifiers.

The 25 study occupations are anchored to **ISCO-08 minor groups (3-digit)**
because the proposal §4.4 explicitly chooses ISCO-08 as the international
anchor and because LAPOP 2023's occupation variable is ISCO-coded. National
codes (CNO-2015 Colombia, SINCO-2011 Mexico, CBO Brazil, COP Peru) are
filled when they enter the robustness analysis; the crosswalks are public
XLSX files from the four statistical offices (see DATA_SOURCES.md).

Granularity note: ISCO-08 3-digit groups are *minor groups* (130 groups
total). LAPOP's ``OCCUP4A`` variable may be at the 1-digit *major group*
level (10 groups). When that is the case, several of the study occupations
collapse to the same f_emp baseline — that is a known and documented
feature: the algorithmic distributions still differ across prompts even
when the empirical baselines are shared. The crosswalk records both the
3-digit minor code and (where applicable) the 1-digit major code to
support both granularities.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


@dataclass(frozen=True)
class OccupationMapping:
    """ISCO-08 anchor plus the national-classifier codes for one occupation.

    Each ``cno_2015`` / ``sinco_2011`` / ``cbo`` / ``cop`` field is the
    canonical 4-digit national code; an empty string means "not yet
    cross-walked, see DATA_SOURCES.md for the official XLSX."
    """

    occupation: str
    spanish: str
    portuguese: str
    isco08_minor: str  # 3-digit ISCO-08 minor group code
    isco08_major: str = ""  # 1-digit ISCO-08 major group, derived if blank
    status_tier: str = ""  # qualitative: "high" / "medium" / "low"
    cno_2015: str = ""  # Colombia (DANE)
    sinco_2011: str = ""  # Mexico (INEGI)
    cbo: str = ""  # Brazil (IBGE)
    cop: str = ""  # Peru (INEI)

    @property
    def derived_major(self) -> str:
        return self.isco08_major or self.isco08_minor[:1]


# ---- The 25 study occupations -----------------------------------------
# Source: proposal §6.1 grilla.

POC_MAPPINGS: dict[str, OccupationMapping] = {
    # High-status (ISCO majors 1–2)
    "CEO": OccupationMapping(
        occupation="CEO", spanish="director general", portuguese="diretor geral",
        isco08_minor="112", isco08_major="1", status_tier="high",
        cno_2015="1120", sinco_2011="111", cbo="121", cop="1120",
    ),
    "doctor": OccupationMapping(
        occupation="doctor", spanish="médico", portuguese="médico",
        isco08_minor="221", isco08_major="2", status_tier="high",
    ),
    "software engineer": OccupationMapping(
        occupation="software engineer", spanish="ingeniero de software",
        portuguese="engenheiro de software",
        isco08_minor="251", isco08_major="2", status_tier="high",
    ),
    "lawyer": OccupationMapping(
        occupation="lawyer", spanish="abogado", portuguese="advogado",
        isco08_minor="261", isco08_major="2", status_tier="high",
    ),
    "university professor": OccupationMapping(
        occupation="university professor", spanish="profesor universitario",
        portuguese="professor universitário",
        isco08_minor="231", isco08_major="2", status_tier="high",
    ),
    "architect": OccupationMapping(
        occupation="architect", spanish="arquitecto", portuguese="arquiteto",
        isco08_minor="216", isco08_major="2", status_tier="high",
    ),
    "accountant": OccupationMapping(
        occupation="accountant", spanish="contador", portuguese="contador",
        isco08_minor="241", isco08_major="2", status_tier="medium",
    ),
    "journalist": OccupationMapping(
        occupation="journalist", spanish="periodista", portuguese="jornalista",
        isco08_minor="264", isco08_major="2", status_tier="medium",
    ),

    # Medium-status (ISCO majors 3–5)
    "nurse": OccupationMapping(
        occupation="nurse", spanish="enfermero", portuguese="enfermeiro",
        isco08_minor="222", isco08_major="2", status_tier="medium",
        cno_2015="2221", sinco_2011="2421", cbo="2235", cop="2221",
    ),
    "police officer": OccupationMapping(
        occupation="police officer", spanish="policía", portuguese="policial",
        isco08_minor="541", isco08_major="5", status_tier="medium",
    ),
    "mechanic": OccupationMapping(
        occupation="mechanic", spanish="mecánico", portuguese="mecânico",
        isco08_minor="723", isco08_major="7", status_tier="medium",
    ),
    "salesperson": OccupationMapping(
        occupation="salesperson", spanish="vendedor", portuguese="vendedor",
        isco08_minor="522", isco08_major="5", status_tier="medium",
    ),
    "secretary": OccupationMapping(
        occupation="secretary", spanish="secretario", portuguese="secretário",
        isco08_minor="412", isco08_major="4", status_tier="medium",
    ),
    "cook": OccupationMapping(
        occupation="cook", spanish="cocinero", portuguese="cozinheiro",
        isco08_minor="512", isco08_major="5", status_tier="medium",
    ),
    "hairdresser": OccupationMapping(
        occupation="hairdresser", spanish="peluquero", portuguese="cabeleireiro",
        isco08_minor="514", isco08_major="5", status_tier="medium",
    ),
    "driver": OccupationMapping(
        occupation="driver", spanish="conductor", portuguese="motorista",
        isco08_minor="832", isco08_major="8", status_tier="medium",
    ),
    "security guard": OccupationMapping(
        occupation="security guard", spanish="vigilante", portuguese="vigilante",
        isco08_minor="541", isco08_major="5", status_tier="medium",
    ),

    # Low-status (ISCO majors 6–9)
    "farmer": OccupationMapping(
        occupation="farmer", spanish="agricultor", portuguese="agricultor",
        isco08_minor="611", isco08_major="6", status_tier="low",
    ),
    "nanny": OccupationMapping(
        occupation="nanny", spanish="niñero", portuguese="babá",
        isco08_minor="531", isco08_major="5", status_tier="low",
    ),
    "construction worker": OccupationMapping(
        occupation="construction worker",
        spanish="obrero de construcción", portuguese="operário de construção",
        isco08_minor="931", isco08_major="9", status_tier="low",
    ),
    "seamstress": OccupationMapping(
        occupation="seamstress", spanish="costurero", portuguese="costureiro",
        isco08_minor="753", isco08_major="7", status_tier="low",
    ),
    "janitor": OccupationMapping(
        occupation="janitor", spanish="conserje", portuguese="zelador",
        isco08_minor="911", isco08_major="9", status_tier="low",
    ),
    "domestic worker": OccupationMapping(
        occupation="domestic worker",
        spanish="empleado doméstico", portuguese="empregado doméstico",
        isco08_minor="911", isco08_major="9", status_tier="low",
        cno_2015="9111", sinco_2011="9611", cbo="5121", cop="9111",
    ),
    "street vendor": OccupationMapping(
        occupation="street vendor",
        spanish="vendedor callejero", portuguese="vendedor ambulante",
        isco08_minor="952", isco08_major="9", status_tier="low",
    ),
    "waste collector": OccupationMapping(
        occupation="waste collector", spanish="recolector", portuguese="coletor de lixo",
        isco08_minor="961", isco08_major="9", status_tier="low",
    ),
}


def get_mapping(occupation: str) -> OccupationMapping:
    """Return the OccupationMapping for ``occupation``, raise KeyError otherwise."""
    try:
        return POC_MAPPINGS[occupation]
    except KeyError as e:
        raise KeyError(
            f"no crosswalk registered for occupation {occupation!r}. "
            f"Known: {sorted(POC_MAPPINGS)}",
        ) from e


def occupations_by_tier(tier: str) -> list[str]:
    """List study occupations in the given status tier ('high', 'medium', 'low')."""
    return [name for name, m in POC_MAPPINGS.items() if m.status_tier == tier]


def all_isco08_minor_codes() -> list[str]:
    """Distinct 3-digit ISCO-08 minor codes across all study occupations."""
    return sorted({m.isco08_minor for m in POC_MAPPINGS.values()})
