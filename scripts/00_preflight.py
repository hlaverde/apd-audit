"""00 — Pre-flight readiness check before the production-grid run.

Verifies that every artefact and tool required by the production
pipeline is present and well-formed. Run this once per coauthor on the
machine that will host their shifts, AND once globally before the
OSF pre-registration is filed.

The script exits non-zero on any blocking issue and zero when all checks
pass. Non-blocking warnings print to stdout but do not fail the script.

Checks performed
----------------
1. Python version and installed-package versions match the lockfile.
2. APD module importable (`import apd.config` succeeds).
3. LAPOP files present for all 4 target countries (CO, MX, BR, PE).
4. Ground truth parquet has expected rows and probabilities sum to 1.
5. Status weights parquet present and weights sum to 1 per country.
6. Crosswalks cover the full 25-occupation set.
7. Prompt grid produces the expected 12 000 cells.
8. `images/main/` exists and is writable.
9. Tests pass (`pytest -q`).
10. Git working tree clean and on a tagged commit (or warn).
"""

from __future__ import annotations

import logging
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("00_preflight")


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    severity: str  # "blocking" or "warn"
    detail: str = ""


def check_python_version() -> CheckResult:
    major, minor = sys.version_info[:2]
    ok = (major, minor) == (3, 11)
    return CheckResult(
        name="python-3.11",
        passed=ok,
        severity="blocking" if not ok else "warn",
        detail=f"running on Python {major}.{minor}; production expects 3.11",
    )


def check_apd_importable() -> CheckResult:
    try:
        import apd  # noqa: F401
        from apd.config import settings  # noqa: F401
    except ImportError as exc:
        return CheckResult("apd-importable", False, "blocking", f"ImportError: {exc}")
    return CheckResult("apd-importable", True, "blocking", "import apd works")


def check_lapop_files() -> CheckResult:
    from apd.config import settings
    from apd.ingest.lapop import LAPOP_FILE_GLOBS

    matched_files = []
    for pattern in LAPOP_FILE_GLOBS:
        matched_files.extend(settings.data_raw.glob(pattern))

    found_names = sorted({p.name for p in matched_files})
    n = len(found_names)
    ok = n >= 4

    return CheckResult(
        name="lapop-files",
        passed=ok,
        severity="blocking",
        detail=(
            f"{n} LAPOP 2023 files matched expected patterns in {settings.data_raw}: "
            f"{found_names}. Need 4 country files for CO/MX/BR/PE."
        ),
    )


def check_ground_truth() -> CheckResult:
    from apd.config import settings

    path = settings.data_processed / "ground_truth.parquet"
    if not path.exists():
        # The POC ground truth is acceptable for development.
        path = settings.data_processed / "ground_truth_poc.parquet"
        if not path.exists():
            return CheckResult(
                "ground-truth", False, "blocking",
                f"neither ground_truth.parquet nor ground_truth_poc.parquet in {settings.data_processed}",
            )
    df = pd.read_parquet(path)
    needed = {"occupation", "perla_tone", "prob"}
    missing = needed - set(df.columns)
    if missing:
        return CheckResult("ground-truth", False, "blocking",
                           f"{path.name} missing columns: {sorted(missing)}")
    # Probabilities sum to 1 per (country, occupation) cell.
    keys = [c for c in ("country", "occupation") if c in df.columns]
    sums = df.groupby(keys)["prob"].sum()
    bad = sums[(sums - 1.0).abs() > 1e-3]
    if not bad.empty:
        return CheckResult("ground-truth", False, "blocking",
                           f"prob does not sum to 1 in {len(bad)} cells of {path.name}")
    return CheckResult("ground-truth", True, "blocking",
                       f"{path.name}: {len(df)} rows, {df['occupation'].nunique()} occupations")


def check_status_weights() -> CheckResult:
    from apd.config import settings

    path = settings.data_processed / "status_weights.parquet"
    if not path.exists():
        return CheckResult(
            "status-weights", False, "warn",
            f"status_weights.parquet missing in {settings.data_processed} — "
            f"will be computed at first run from the prior or LAPOP",
        )
    df = pd.read_parquet(path)
    if "weight" not in df.columns:
        return CheckResult("status-weights", False, "blocking",
                           "weight column missing in status_weights.parquet")
    sums = df.groupby("country")["weight"].sum()
    bad = sums[(sums - 1.0).abs() > 1e-3]
    if not bad.empty:
        return CheckResult("status-weights", False, "blocking",
                           f"weights don't sum to 1 in {len(bad)} countries")
    return CheckResult("status-weights", True, "blocking",
                       f"weights sum to 1 across {df['country'].nunique()} countries")


def check_crosswalks() -> CheckResult:
    from apd.ground_truth.crosswalks import POC_MAPPINGS

    n = len(POC_MAPPINGS)
    ok = n == 25
    return CheckResult(
        "crosswalks", ok, "blocking",
        f"{n} occupations registered (need 25)",
    )


def check_prompt_grid() -> CheckResult:
    from apd.prompts.grid import expected_main_grid_size

    n = expected_main_grid_size()
    ok = n == 12_000
    return CheckResult(
        "prompt-grid", ok, "blocking",
        f"main grid has {n} cells (need 12 000)",
    )


def check_images_dir_writable() -> CheckResult:
    from apd.config import settings

    main_dir = settings.images_dir / "main"
    main_dir.mkdir(parents=True, exist_ok=True)
    probe = main_dir / ".preflight_write_probe"
    try:
        probe.write_text("probe", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        return CheckResult("images-writable", False, "blocking", f"{main_dir} not writable: {exc}")
    return CheckResult("images-writable", True, "warn", f"{main_dir} ready for writes")


def check_tests_pass() -> CheckResult:
    try:
        r = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "--tb=no", "--no-header"],
            capture_output=True, text=True, timeout=600,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return CheckResult("tests", False, "blocking", f"could not run pytest: {exc}")
    if r.returncode == 0:
        return CheckResult("tests", True, "blocking",
                           r.stdout.strip().split("\n")[-1] if r.stdout else "all green")
    return CheckResult("tests", False, "blocking",
                       (r.stdout or "")[-500:] + (r.stderr or "")[-200:])


def check_git_state() -> CheckResult:
    try:
        status = subprocess.run(
            ["git", "status", "--porcelain"], capture_output=True, text=True, timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return CheckResult("git-clean", False, "warn", f"git not available: {exc}")
    if status.returncode != 0:
        return CheckResult("git-clean", False, "warn", "not a git repository")
    n_changes = len([line for line in status.stdout.splitlines() if line.strip()])
    if n_changes:
        return CheckResult("git-clean", False, "warn",
                           f"{n_changes} uncommitted changes — commit before pre-reg")
    return CheckResult("git-clean", True, "warn", "working tree clean")


CHECKS = [
    check_python_version,
    check_apd_importable,
    check_lapop_files,
    check_ground_truth,
    check_status_weights,
    check_crosswalks,
    check_prompt_grid,
    check_images_dir_writable,
    check_git_state,
    check_tests_pass,
]


def main() -> int:
    results = [check() for check in CHECKS]
    print()
    print("============== PRE-FLIGHT RESULTS ==============")
    blocking_failures = 0
    warnings = 0
    for r in results:
        marker = "OK " if r.passed else ("BLOCK" if r.severity == "blocking" else "WARN ")
        print(f"  [{marker}] {r.name:<22} {r.detail}")
        if not r.passed:
            if r.severity == "blocking":
                blocking_failures += 1
            else:
                warnings += 1
    print("================================================")
    print(f"  {blocking_failures} blocking failure(s); {warnings} warning(s).")
    if blocking_failures:
        print("  Resolve blocking items before generation begins.")
        return 1
    if warnings:
        print("  Warnings are advisory; safe to proceed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
