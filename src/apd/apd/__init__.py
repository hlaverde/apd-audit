"""APD indicator: distances, signed Δ, status-weighted aggregation.

See §5.2 of the binding proposal for the formal definition.
"""

from .bootstrap import BootstrapEstimate, bootstrap_apd
from .delta import expected_perla, signed_delta
from .distances import wasserstein1_perla
from .indicator import OccupationResult, apd, compute_occupation_metrics

__all__ = [
    "BootstrapEstimate",
    "OccupationResult",
    "apd",
    "bootstrap_apd",
    "compute_occupation_metrics",
    "expected_perla",
    "signed_delta",
    "wasserstein1_perla",
]
