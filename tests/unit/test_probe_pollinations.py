"""Unit tests for the Pollinations parallel throughput probe (TAREA 1).

The probe lives in ``scripts/_probe_pollinations_parallel.py`` (not in
``src/apd``) because it is a one-shot diagnostic, not a library module.
These tests cover the deterministic, pure helpers without touching the
network: seed generation, prompt format, phase metric aggregation, and the
recommendation rubric. The async HTTP path is exercised by the probe run
itself; mocking httpx end-to-end here would duplicate library tests.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROBE_PATH = PROJECT_ROOT / "scripts" / "_probe_pollinations_parallel.py"


@pytest.fixture(scope="module")
def probe():
    """Load the probe script as a module via importlib."""
    spec = importlib.util.spec_from_file_location("_probe_pollinations_parallel", PROBE_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_probe_pollinations_parallel"] = mod
    spec.loader.exec_module(mod)
    return mod


class TestProbeSeeds:
    def test_probe_seeds_above_main_grid_offset(self, probe) -> None:
        """All probe seeds must sit above the 5e9 H5 offset and 2e10 robust
        offset so they cannot collide with production cell seeds."""
        base = 20_260_514  # apd.config.settings.seed
        seeds = {
            probe.probe_seed(base, phase_idx, img_idx, occ_idx)
            for phase_idx in range(4)
            for img_idx in range(20)
            for occ_idx in range(3)
        }
        assert min(seeds) >= probe.PROBE_SEED_OFFSET
        # Robustness grid uses base + 2e10; probe offset must be far from it.
        assert min(seeds) > 2 * 10**10 * base // base  # symbolic check
        # All seeds unique.
        assert len(seeds) == 4 * 20 * 3

    def test_probe_seeds_deterministic(self, probe) -> None:
        a = probe.probe_seed(20_260_514, 1, 7, 2)
        b = probe.probe_seed(20_260_514, 1, 7, 2)
        assert a == b


class TestProbePrompts:
    def test_three_occupations_yield_english_prompts(self, probe) -> None:
        for occ in probe.PROBE_OCCUPATIONS:
            p = probe.probe_prompt(occ)
            assert p.startswith("a photo of a ")
            assert occ in p


class TestPhaseMetrics:
    def test_metrics_from_all_ok_records(self, probe) -> None:
        records = [
            probe.RequestRecord(
                phase_n=5,
                img_idx=i,
                occupation="CEO",
                seed=10_000 + i,
                wall_s=float(i + 1),  # 1..20 seconds
                status=200,
                ok=True,
                bytes_received=12345,
            )
            for i in range(20)
        ]
        # Wall total = the slowest stream finished at 20s (parallel).
        m = probe.PhaseMetrics.from_records(n_concurrent=5, wall_total_s=20.0, records=records)
        assert m.n_concurrent == 5
        assert m.imgs_ok == 20
        assert m.http_429_count == 0
        assert m.http_5xx_count == 0
        assert m.http_other_error_count == 0
        # 20 imgs in 20s = 1 img/s = 60 imgs/min aggregate.
        assert m.throughput_agg_imgs_per_min == pytest.approx(60.0)
        # Per stream = 60 / 5 = 12.
        assert m.throughput_per_stream_imgs_per_min == pytest.approx(12.0)
        # p50 of 1..20 is 10.5; p95 is 19 (the 19th of 20 quantiles).
        assert m.p50_wall_s == pytest.approx(10.5)

    def test_metrics_with_429_and_5xx(self, probe) -> None:
        records = [
            probe.RequestRecord(0, 0, "CEO", 1, 1.0, 200, True, 1000),
            probe.RequestRecord(0, 1, "CEO", 2, 1.0, 429, False, 0, error="rate limited"),
            probe.RequestRecord(0, 2, "CEO", 3, 1.0, 503, False, 0, error="bad gateway"),
            probe.RequestRecord(0, 3, "CEO", 4, 1.0, None, False, 0, error="timeout"),
        ]
        m = probe.PhaseMetrics.from_records(n_concurrent=2, wall_total_s=2.0, records=records)
        assert m.imgs_ok == 1
        assert m.http_429_count == 1
        assert m.http_5xx_count == 1
        # network error (status=None) bucketed as "other_error".
        assert m.http_other_error_count == 1


class TestRecommend:
    def _phase(
        self,
        probe,
        n_concurrent: int,
        imgs_ok: int,
        n_attempted: int = 20,
        wall: float = 20.0,
        n_429: int = 0,
        n_5xx: int = 0,
    ):
        return probe.PhaseMetrics(
            n_concurrent=n_concurrent,
            n_attempted=n_attempted,
            wall_total_s=wall,
            imgs_ok=imgs_ok,
            http_429_count=n_429,
            http_5xx_count=n_5xx,
            http_other_error_count=0,
            p50_wall_s=wall / 2,
            p95_wall_s=wall * 0.95,
            throughput_agg_imgs_per_min=(imgs_ok / wall) * 60.0 if wall > 0 else 0.0,
            throughput_per_stream_imgs_per_min=((imgs_ok / wall) * 60.0 / n_concurrent)
            if wall > 0
            else 0.0,
            error_examples=[],
        )

    def test_steady_gain_picks_largest_n(self, probe) -> None:
        # Each N doubles throughput (×2 vs prev), no 429s → pick N=10.
        phases = [
            self._phase(probe, 1, 1, wall=60.0),  # 1 imgs/min
            self._phase(probe, 3, 3, wall=60.0),  # 3 imgs/min (×3)
            self._phase(probe, 5, 5, wall=60.0),  # 5 imgs/min (×1.67)
            self._phase(probe, 10, 10, wall=60.0),  # 10 imgs/min (×2)
        ]
        n, reason = probe.recommend(phases)
        assert n == 10
        assert "Picked N=10" in reason

    def test_plateau_picks_pre_plateau_n(self, probe) -> None:
        # Plateau at N=5: gain N=5 → N=10 is only ×1.05.
        phases = [
            self._phase(probe, 1, 1, wall=60.0),  # 1 imgs/min
            self._phase(probe, 3, 5, wall=60.0),  # 5 (×5)
            self._phase(probe, 5, 10, wall=60.0),  # 10 (×2)
            self._phase(probe, 10, 11, wall=60.0),  # 11 (×1.1 — below 1.15 threshold)
        ]
        n, _reason = probe.recommend(phases)
        assert n == 5

    def test_hard_rate_limit_picks_n1(self, probe) -> None:
        # 30% 429 ratio at N=3 → hard rate-limit → N=1, Branch B.
        phases = [
            self._phase(probe, 1, 18, wall=60.0, n_429=0),
            self._phase(probe, 3, 14, wall=60.0, n_429=6),  # 6/20 = 30%
            self._phase(probe, 5, 12, wall=60.0, n_429=8),
            self._phase(probe, 10, 5, wall=60.0, n_429=15),
        ]
        n, reason = probe.recommend(phases)
        assert n == 1
        assert "Branch B" in reason

    def test_402_on_parallel_phases_picks_n1_branch_b(self, probe) -> None:
        """Regression test for the TAREA 1 observation (2026-05-16):
        Pollinations returned 402 Payment Required on 19/20 requests at
        every N>=2 phase, while N=1 succeeded 20/20. The recommend()
        rubric must flag this as Branch B with the sequential trickle
        operational note."""
        # The 402s land in http_other_error_count (not in http_429_count).
        p_seq = probe.PhaseMetrics(
            n_concurrent=1,
            n_attempted=20,
            wall_total_s=1712.4,
            imgs_ok=20,
            http_429_count=0,
            http_5xx_count=0,
            http_other_error_count=0,
            p50_wall_s=89.9,
            p95_wall_s=93.4,
            throughput_agg_imgs_per_min=0.70,
            throughput_per_stream_imgs_per_min=0.70,
            error_examples=[],
        )

        # All N>=2 phases: 1 lucky 200 OK, 19 x 402 Payment Required.
        def _parallel(n):
            return probe.PhaseMetrics(
                n_concurrent=n,
                n_attempted=20,
                wall_total_s=90.0,
                imgs_ok=1,
                http_429_count=0,
                http_5xx_count=0,
                http_other_error_count=19,
                p50_wall_s=90.0,
                p95_wall_s=90.0,
                throughput_agg_imgs_per_min=0.67,
                throughput_per_stream_imgs_per_min=0.67 / n,
                error_examples=["status=402"],
            )

        phases = [p_seq, _parallel(3), _parallel(5), _parallel(10)]
        n, reason = probe.recommend(phases)
        assert n == 1
        assert "Branch B" in reason
        assert (
            "402" not in reason
            or "Payment Required" in reason
            or "http_other_error_ratio" in reason
        )
        # Must explicitly call out that N=1 sequential trickle remains
        # operational so the user doesn't read this as "give up on Pollinations".
        assert "sequential trickle" in reason or "--workers 1" in reason

    def test_empty_phases_defaults_to_n1(self, probe) -> None:
        n, _reason = probe.recommend([])
        assert n == 1


class TestRenderTable:
    def test_table_has_expected_columns(self, probe) -> None:
        phases = [
            probe.PhaseMetrics(
                n_concurrent=1,
                n_attempted=20,
                wall_total_s=60.0,
                imgs_ok=20,
                http_429_count=0,
                http_5xx_count=0,
                http_other_error_count=0,
                p50_wall_s=3.0,
                p95_wall_s=4.5,
                throughput_agg_imgs_per_min=20.0,
                throughput_per_stream_imgs_per_min=20.0,
                error_examples=[],
            )
        ]
        table = probe.render_table(phases)
        for header in ("N", "attempted", "ok", "429", "agg/min"):
            assert header in table
        assert "  1" in table  # the N=1 row
