"""TAREA 1 — Pollinations.ai parallel throughput probe.

Why this exists
---------------
The first manual production shift (50 imgs FLUX via Pollinations) ran at
88.2 s/img sequential — 9x slower than the POC (≈10 s/img). The hypothesis
is single-IP throttling: Pollinations slows down after N sequential requests.
If asyncio + httpx with N concurrent streams recovers the throughput, the
APD automation can lean on a public-repo GitHub Actions cron (Layer 1) plus
a local async worker (Layer 2) for the ~3 320 FLUX-via-Pollinations cells.
If parallelism is rate-limited too, those layers are not worth building and
we route everything through Kaggle GPU (Layer 3, local diffusers).

This probe answers the question with numbers before committing to an
architecture.

Method
------
4 phases, concurrency N ∈ {1, 3, 5, 10}. Each phase issues 20 image
requests against Pollinations via ``httpx.AsyncClient`` capped at N
in-flight requests by an ``asyncio.Semaphore(N)``. Per-request wall-clock
times, HTTP status codes, and aggregate throughput (imgs/min) are recorded.

Seeds are pinned to a disjoint range (``base + 90_000_000_000 + ...``) so
the 80 probe images do **not** collide with the main grid, the H5 grid, or
the robustness grid. The images are kept in memory only — they are never
written to ``images/main/`` and do not pollute the production panel.

Outputs
-------
* ``results/pollinations_probe.json`` — full per-phase metrics + a textual
  recommendation block.
* stdout — a four-row summary table + the same recommendation block.
* ``docs/COST_LOG.md`` — appended row: probe / Pollinations free /
  80 imgs / Xs / $0.00.

Run it
------
    python scripts/_probe_pollinations_parallel.py

Wall clock estimate: 20–40 min depending on Pollinations latency.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import statistics
import sys
import time
import urllib.parse
from dataclasses import asdict, dataclass, field
from pathlib import Path

import httpx

# Make ``apd`` importable when running this script directly.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from apd.config import settings  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("probe")

# -------------------------------------------------------------------------
# Configuration
# -------------------------------------------------------------------------

API_TEMPLATE = "https://image.pollinations.ai/prompt/{prompt}"

# Mirror PollinationsBackend defaults so the probe measures what the
# production backend will actually experience.
MODEL = "flux"
WIDTH = 512
HEIGHT = 512
PER_REQUEST_TIMEOUT_S = 180.0

# Phases (concurrency level → number of imgs in that phase).
PHASES: tuple[tuple[int, int], ...] = (
    (1, 20),
    (3, 20),
    (5, 20),
    (10, 20),
)

# Three POC occupations × English. Identical lexical surface to existing POC
# prompts so any throttling difference is attributable to concurrency, not
# prompt content.
PROBE_OCCUPATIONS: tuple[str, ...] = ("CEO", "nurse", "domestic worker")
PROMPT_TEMPLATE = "a photo of {article}{occ}"


def probe_prompt(occupation: str) -> str:
    """Mirror the POC English-language prompt format."""
    if occupation == "domestic worker":
        article = "a "
    elif occupation == "CEO":
        article = "a "  # consonant sound 'see-ee-oh'
    else:
        article = "a "  # nurse → 'a'
    return PROMPT_TEMPLATE.format(article=article, occ=occupation)


# Disjoint seed namespace: 90_000_000_000 ≪ main (<= 12B from cell_seed
# formula) and far above main+H5+robust offsets. The probe imgs are
# discarded after measurement and never enter the production panel.
PROBE_SEED_OFFSET = 90_000_000_000


def probe_seed(base: int, phase_idx: int, img_idx: int, occ_idx: int) -> int:
    """Deterministic seed inside the disjoint probe range."""
    return PROBE_SEED_OFFSET + base * 1_000_000 + phase_idx * 10_000 + occ_idx * 1_000 + img_idx


# -------------------------------------------------------------------------
# Per-request and per-phase records
# -------------------------------------------------------------------------


@dataclass
class RequestRecord:
    """One image request attempt."""

    phase_n: int
    img_idx: int
    occupation: str
    seed: int
    wall_s: float
    status: int | None
    ok: bool
    bytes_received: int
    error: str = ""


@dataclass
class PhaseMetrics:
    """Aggregate metrics for one concurrency-N phase."""

    n_concurrent: int
    n_attempted: int
    wall_total_s: float
    imgs_ok: int
    http_429_count: int
    http_5xx_count: int
    http_other_error_count: int
    p50_wall_s: float
    p95_wall_s: float
    throughput_agg_imgs_per_min: float
    throughput_per_stream_imgs_per_min: float
    error_examples: list[str] = field(default_factory=list)

    @classmethod
    def from_records(
        cls, n_concurrent: int, wall_total_s: float, records: list[RequestRecord]
    ) -> PhaseMetrics:
        ok_walls = [r.wall_s for r in records if r.ok]
        p50 = statistics.median(ok_walls) if ok_walls else float("nan")
        p95 = (
            statistics.quantiles(ok_walls, n=20)[-1]
            if len(ok_walls) >= 20
            else (max(ok_walls) if ok_walls else float("nan"))
        )
        n_429 = sum(1 for r in records if r.status == 429)
        n_5xx = sum(1 for r in records if r.status is not None and 500 <= r.status < 600)
        n_other = sum(
            1
            for r in records
            if not r.ok
            and r.status not in (429, None)
            and not (r.status is not None and 500 <= r.status < 600)
        )
        n_net_err = sum(1 for r in records if r.status is None and not r.ok)
        n_other_err = n_other + n_net_err
        agg_per_min = (
            (sum(1 for r in records if r.ok) / wall_total_s) * 60.0 if wall_total_s > 0 else 0.0
        )
        per_stream_per_min = agg_per_min / n_concurrent if n_concurrent > 0 else 0.0
        examples = [r.error for r in records if r.error][:3]
        return cls(
            n_concurrent=n_concurrent,
            n_attempted=len(records),
            wall_total_s=wall_total_s,
            imgs_ok=len(ok_walls),
            http_429_count=n_429,
            http_5xx_count=n_5xx,
            http_other_error_count=n_other_err,
            p50_wall_s=p50,
            p95_wall_s=p95,
            throughput_agg_imgs_per_min=agg_per_min,
            throughput_per_stream_imgs_per_min=per_stream_per_min,
            error_examples=examples,
        )


# -------------------------------------------------------------------------
# Async request execution
# -------------------------------------------------------------------------


async def issue_one(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    phase_n: int,
    img_idx: int,
    occupation: str,
    seed: int,
) -> RequestRecord:
    """Single Pollinations GET, gated by ``semaphore``.

    Mirrors the parameter shape of ``PollinationsBackend.generate`` so the
    probe measures the same path the production worker will exercise.
    """
    prompt = probe_prompt(occupation)
    encoded = urllib.parse.quote(prompt)
    url = API_TEMPLATE.format(prompt=encoded)
    params = {
        "model": MODEL,
        "seed": int(seed),
        "width": WIDTH,
        "height": HEIGHT,
        "nologo": "true",
        "private": "true",
    }
    async with semaphore:
        started = time.monotonic()
        status: int | None = None
        ok = False
        n_bytes = 0
        error = ""
        try:
            r = await client.get(url, params=params, timeout=PER_REQUEST_TIMEOUT_S)
            status = r.status_code
            ctype = r.headers.get("content-type", "")
            if r.status_code == 200 and ctype.startswith("image/"):
                ok = True
                n_bytes = len(r.content)
            else:
                error = f"status={r.status_code} ctype={ctype} body={r.text[:120]!r}"
        except httpx.HTTPError as exc:
            error = f"{type(exc).__name__}: {exc}"
        wall = time.monotonic() - started
    return RequestRecord(
        phase_n=phase_n,
        img_idx=img_idx,
        occupation=occupation,
        seed=seed,
        wall_s=wall,
        status=status,
        ok=ok,
        bytes_received=n_bytes,
        error=error,
    )


async def run_phase(
    phase_idx: int, n_concurrent: int, n_imgs: int, base_seed: int
) -> tuple[PhaseMetrics, list[RequestRecord]]:
    log.info(
        "phase %d: N=%d concurrent, %d imgs",
        phase_idx + 1,
        n_concurrent,
        n_imgs,
    )
    semaphore = asyncio.Semaphore(n_concurrent)
    tasks: list[asyncio.Task[RequestRecord]] = []
    started = time.monotonic()
    async with httpx.AsyncClient(http2=False, follow_redirects=True) as client:
        for img_idx in range(n_imgs):
            occ_idx = img_idx % len(PROBE_OCCUPATIONS)
            occupation = PROBE_OCCUPATIONS[occ_idx]
            seed = probe_seed(base_seed, phase_idx, img_idx, occ_idx)
            tasks.append(
                asyncio.create_task(
                    issue_one(client, semaphore, n_concurrent, img_idx, occupation, seed),
                )
            )
        records = await asyncio.gather(*tasks)
    wall_total = time.monotonic() - started
    metrics = PhaseMetrics.from_records(n_concurrent, wall_total, list(records))
    log.info(
        "phase %d done: imgs_ok=%d/%d, 429=%d, 5xx=%d, wall=%.1fs, agg=%.2f imgs/min",
        phase_idx + 1,
        metrics.imgs_ok,
        metrics.n_attempted,
        metrics.http_429_count,
        metrics.http_5xx_count,
        metrics.wall_total_s,
        metrics.throughput_agg_imgs_per_min,
    )
    return metrics, list(records)


# -------------------------------------------------------------------------
# Recommendation rubric
# -------------------------------------------------------------------------


def recommend(phases: list[PhaseMetrics]) -> tuple[int, str]:
    """Pick the best N based on a simple plateau-detection rubric.

    Decision rules (applied in order):

    1. If *any* phase has http_429_ratio > 20% → recommend ``N=1`` and flag
       hard rate-limiting (Branch B in the plan).
    2. If a phase with N>1 has http_other_error_ratio > 20% AND phase N=1
       worked → Pollinations rate-limits parallel (saw 402 in TAREA 1
       on 2026-05-16). Recommend ``N=1`` with Branch B route for the
       SD-family work but keep N=1 sequential trickle on Pollinations.
    3. Otherwise, walk phases in order. Adopt the largest N whose
       aggregate throughput is >= 1.15 × the previous phase's throughput.
       Stop upgrading when the gain falls below 15% (plateau) or
       http_429_ratio exceeds 5% at the candidate N.
    4. Tie-breaker: prefer smaller N (less aggressive against Pollinations).
    """
    if not phases:
        return 1, "no phases — defaulting to N=1"

    # Rule 1
    worst_429 = max((p.http_429_count / max(p.n_attempted, 1) for p in phases), default=0.0)
    if worst_429 > 0.20:
        return 1, (
            f"hard rate-limiting (429) detected (max http_429_ratio={worst_429:.0%}); "
            "Branch B: skip Layer 1+2, route all FLUX cells through Kaggle local diffusers (Layer 3)."
        )

    # Rule 2 — Pollinations 402 / other-error spike on parallel phases
    # while N=1 still worked. This is the TAREA 1 observed signature
    # (Pollinations charges parallel access while tolerating sequential).
    seq_phase = next((p for p in phases if p.n_concurrent == 1), None)
    parallel_phases = [p for p in phases if p.n_concurrent > 1]
    if (
        seq_phase is not None
        and seq_phase.imgs_ok / max(seq_phase.n_attempted, 1) >= 0.5
        and parallel_phases
    ):
        worst_other = max(
            (p.http_other_error_count / max(p.n_attempted, 1) for p in parallel_phases),
            default=0.0,
        )
        if worst_other > 0.20:
            return 1, (
                f"parallel access rate-limited at the application layer "
                f"(max http_other_error_ratio={worst_other:.0%} on N>=2 phases, "
                f"while N=1 succeeded {seq_phase.imgs_ok}/{seq_phase.n_attempted}); "
                "Branch B: route SD-family + robustness + indigenous-langs through "
                "Kaggle local diffusers (Layer 3). Pollinations N=1 sequential trickle "
                "(Layer 1 GH Actions every 6h + Layer 2 local async with --workers 1) "
                "remains operational for the ~3 320 FLUX cells."
            )

    # Rule 3
    best_n = phases[0].n_concurrent
    best_throughput = phases[0].throughput_agg_imgs_per_min
    reason_steps: list[str] = [f"N={best_n}: {best_throughput:.2f} imgs/min baseline"]
    for prev, curr in zip(phases, phases[1:]):
        gain = (
            (curr.throughput_agg_imgs_per_min / prev.throughput_agg_imgs_per_min)
            if prev.throughput_agg_imgs_per_min > 0
            else 0
        )
        n_429_ratio = curr.http_429_count / max(curr.n_attempted, 1)
        reason_steps.append(
            f"N={curr.n_concurrent}: {curr.throughput_agg_imgs_per_min:.2f} imgs/min "
            f"(gain ×{gain:.2f} vs N={prev.n_concurrent}; 429_ratio={n_429_ratio:.0%})"
        )
        if gain >= 1.15 and n_429_ratio <= 0.05:
            best_n = curr.n_concurrent
            best_throughput = curr.throughput_agg_imgs_per_min
        else:
            break  # plateau or 429s — stop upgrading

    reason = (
        "; ".join(reason_steps)
        + f". Picked N={best_n} as the largest N with >=15% throughput gain and <=5% 429 ratio."
    )
    return best_n, reason


# -------------------------------------------------------------------------
# Output formatting
# -------------------------------------------------------------------------


def render_table(phases: list[PhaseMetrics]) -> str:
    header = (
        f"{'N':>3} | {'attempted':>9} | {'ok':>4} | "
        f"{'429':>4} | {'5xx':>4} | {'other_err':>9} | "
        f"{'wall_s':>7} | {'p50_s':>6} | {'p95_s':>6} | "
        f"{'agg/min':>8} | {'per_stream/min':>14}"
    )
    sep = "-" * len(header)
    rows = [header, sep]
    for p in phases:
        rows.append(
            f"{p.n_concurrent:>3} | {p.n_attempted:>9} | {p.imgs_ok:>4} | "
            f"{p.http_429_count:>4} | {p.http_5xx_count:>4} | {p.http_other_error_count:>9} | "
            f"{p.wall_total_s:>7.1f} | {p.p50_wall_s:>6.1f} | {p.p95_wall_s:>6.1f} | "
            f"{p.throughput_agg_imgs_per_min:>8.2f} | {p.throughput_per_stream_imgs_per_min:>14.2f}"
        )
    return "\n".join(rows)


def write_json(
    path: Path,
    phases: list[PhaseMetrics],
    recommended_n: int,
    reason: str,
    started_at: float,
    ended_at: float,
) -> None:
    payload = {
        "started_at_utc": int(started_at),
        "ended_at_utc": int(ended_at),
        "wall_total_s": ended_at - started_at,
        "model": MODEL,
        "image_dims": [WIDTH, HEIGHT],
        "phases": [asdict(p) for p in phases],
        "recommended_n": recommended_n,
        "recommendation_reason": reason,
        "branch": "A" if recommended_n >= 3 else ("A-conservative" if recommended_n == 1 else "B"),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(path)


def append_cost_log(cost_log: Path, n_imgs: int, elapsed_s: float) -> None:
    line = (
        f"| {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())} | probe TAREA 1 | "
        f"Pollinations free | {n_imgs} imgs / {elapsed_s:.0f}s | $0.00 | **$0.00** |\n"
    )
    try:
        with cost_log.open("a", encoding="utf-8") as fh:
            fh.write(line)
    except OSError as exc:
        log.warning("Could not append to %s: %s", cost_log, exc)


# -------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------


async def amain(out_json: Path, cost_log: Path) -> int:
    base_seed = settings.seed
    started_at = time.time()
    started_mono = time.monotonic()
    phase_metrics: list[PhaseMetrics] = []
    for phase_idx, (n_concurrent, n_imgs) in enumerate(PHASES):
        metrics, _records = await run_phase(phase_idx, n_concurrent, n_imgs, base_seed)
        phase_metrics.append(metrics)

    total_wall = time.monotonic() - started_mono
    ended_at = time.time()
    total_imgs = sum(p.n_attempted for p in phase_metrics)

    recommended_n, reason = recommend(phase_metrics)
    table = render_table(phase_metrics)

    # Persist the JSON FIRST so a downstream print() crash (e.g. Windows
    # cp1252 stdout choking on a Unicode glyph) does not throw away the
    # 80-image measurement run. The probe is the artefact, not the print.
    write_json(out_json, phase_metrics, recommended_n, reason, started_at, ended_at)
    log.info("wrote %s", out_json)
    append_cost_log(cost_log, total_imgs, total_wall)

    print()
    print("=" * 96)
    print("Pollinations parallel throughput probe -- results")
    print("=" * 96)
    print(table)
    print()
    print(
        f"Total wall: {total_wall:.1f}s for {total_imgs} requests across {len(phase_metrics)} phases."
    )
    print()
    print(f"Recommended N = {recommended_n}")
    print("Reason:")
    try:
        print(f"  {reason}")
    except UnicodeEncodeError:
        # Fall back to ASCII-safe rendering for the stdout transcript.
        print("  " + reason.encode("ascii", errors="replace").decode("ascii"))
    print()
    print("=" * 96)

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out-json",
        type=Path,
        default=PROJECT_ROOT / "results" / "pollinations_probe.json",
        help="Where to write the per-phase metrics JSON.",
    )
    parser.add_argument(
        "--cost-log",
        type=Path,
        default=PROJECT_ROOT / "docs" / "COST_LOG.md",
        help="Markdown cost ledger to append a probe row to.",
    )
    args = parser.parse_args(argv)
    return asyncio.run(amain(args.out_json, args.cost_log))


if __name__ == "__main__":
    sys.exit(main())
