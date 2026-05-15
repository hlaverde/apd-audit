"""Visual validation: stratified sampling + inter-rater agreement.

The pre-registered procedure (DESIGN.md §7.4, DECISIONS.md D-020) asks
two coauthors (CL and YP) to manually PERLA-label a 300-image stratified
sample blind to the algorithmic classifier outputs, with HL adjudicating
disagreements. Cohen's κ between the two raters is the headline
reviewer-defensible metric for classifier validity.
"""

from .sampling import StratificationPlan, sample_for_validation
from .agreement import cohens_kappa, compare_to_consensus

__all__ = [
    "StratificationPlan",
    "cohens_kappa",
    "compare_to_consensus",
    "sample_for_validation",
]
