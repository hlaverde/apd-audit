"""01 — Document microdata download (and attempt automated retrieval when possible).

For Colombia / LAPOP 2023 the file is distributed by Vanderbilt behind a free
registration and there is no scriptable public-URL download. This script
documents the manual placement procedure and exits with a clear message.

When real LAPOP files are placed in ``data/raw/`` the downstream
``02_build_ground_truth.py`` will pick them up automatically; otherwise the
ground truth falls back to the synthetic prior documented in
``DECISIONS.md`` D-003.
"""

from __future__ import annotations

import logging
import sys

from apd.config import settings
from apd.ingest.lapop import LAPOP_FILE_NAMES

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("01_download")


def main() -> int:
    raw_dir = settings.data_raw
    raw_dir.mkdir(parents=True, exist_ok=True)
    log.info("Raw-data directory: %s", raw_dir)

    candidates = [raw_dir / name for name in LAPOP_FILE_NAMES]
    present = [p for p in candidates if p.exists()]
    if present:
        log.info("LAPOP file already present: %s", present[0])
        return 0

    log.warning(
        "LAPOP 2023 Colombia not found in %s. The 2023 wave requires a free "
        "user account at https://www.lapopsurveys.org/data-access — that is "
        "*not* an institutional credential, so it complies with the binding "
        "spec, but the download cannot be scripted from a clean clone.",
        raw_dir,
    )
    log.warning(
        "To use the real distribution: (1) register at "
        "https://www.lapopsurveys.org/data-access, (2) download the Colombia "
        "2023 file in CSV/STATA format, (3) save it under any of these names:",
    )
    for name in LAPOP_FILE_NAMES:
        log.warning("    %s", raw_dir / name)
    log.info(
        "Until then, the pipeline transparently falls back to the documented "
        "synthetic prior (DECISIONS.md D-003) so that `make all-poc` can "
        "still validate the plumbing end-to-end.",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
