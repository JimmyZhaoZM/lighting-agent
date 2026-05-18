"""Unit tests for Phase 4: optimizer (grid, checker, optimizer loop).

All Radiance subprocess calls are mocked; no Radiance installation required.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from lighting_agent.optimizer.checker import LightingCheck, check_compliance
from lighting_agent.optimizer.grid import (
    best_layout_for_count,
    candidate_layouts,
    candidate_layouts_from_estimate,
    estimate_luminaire_count,
    generate_grid,
)
from lighting_agent.optimizer.optimizer import OptimizationResult, optimize
from lighting_agent.schemas import Luminaire, Room, SimulationResult


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def make_room(
    width: float = 10.0,
    depth: float = 10.0,
    height: float = 4.0,
    target_lux: float = 300.0,
    mount_height: float | None = None,
) -> Room:
    polygon = [(0, 0), (width, 0), (width, depth), (0, depth)]
    return Room(
        name="test_room",
        polygon=polygon,
        height=height,
        target_lux=target_lux,
        mount_height=mount_height,
    )


def make_simulation_result(
    avg_lux: float = 300.0,
    min_lux: float = 150.0,
    max_lux: float = 450.0,
    uniformity: float = 0.5,
    target_lux: float = 300.0,
    luminaires: list[Luminaire] | None = None,
) -> SimulationResult:
    if luminaires is None:
        luminaires = []
    return SimulationResult(
        room_name="test_room",
        luminaires=luminaires,
        illuminance_grid=[[avg_lux]],
        grid_resolution=0.5,
        avg_lux=avg_lux,
        min_lux=min_lux,
        max_lux=max_lux,
        uniformity=uniformity,
        meets_target=avg_lux >= target_lux,
        target_lux=target_lux,
    )


IES_PATH = "/fixtures/dummy.ies"


# ===========================================================================
# Tests: optimizer/grid.py
# ===========================================================================

class TestGenerateGrid:
    def test_correct_luminaire_count(self):
        room = make_room()
        lums = generate_grid(room, IES_PATH, nx=3, ny=2)
        assert len(lums) == 6

    def test_all_luminaires_use_given_ies(self):
        room = make_room()
        lums = generate_grid(room, IES_PATH, nx=2, ny=2)
        assert all(l.ies_path == IES_PATH for l in lums)

    def test_luminaire_z_equals_mount_height(self):
        room = make_room(height=5.0, mount_height=4.5)
        lums = generate_grid(room, IES_PATH, nx=2, ny=2)
        assert all(l.z == pytest.approx(4.5) for l in lums)

    def test_z_defaults_to_height_when_mount_height_none(self):
        room = make_room(height=6.0, mount_height=None)
        lums = generate_grid(room, IES_PATH, nx=1, ny=1)
        assert lums[0].z == pytest.approx(6.0)

    def test_single_luminaire_placed_at_room_centre(self):
        room = make_room(width=10.0, depth=8.0)
        lums = generate_grid(room, IES_PATH, nx=1, ny=1)
        assert len(lums) == 1
        assert lums[0].x == pytest.approx(5.0)
        assert lums[0].y == pytest.approx(4.0)

    def test_2x2_grid_positions(self):
        room = make_room(width=10.0, depth=10.0)
        lums = generate_grid(room, IES_PATH, nx=2, ny=2)
        xs = sorted({l.x for l in lums})
        ys = sorted({l.y for l in lums})
        assert xs == pytest.approx([2.5, 7.5])
        assert ys == pytest.approx([2.5, 7.5])

    def test_3x4_grid_count(self):
        room = make_room(width=12.0, depth=16.0)
        lums = generate_grid(room, IES_PATH, nx=3, ny=4)
        assert len(lums) == 12

    def test_returns_luminaire_instances(self):
        room = make_room()
        lums = generate_grid(room, IES_PATH, nx=2, ny=3)
        assert all(isinstance(l, Luminaire) for l in lums)

    def test_invalid_nx_raises(self):
        room = make_room()
        with pytest.raises(ValueError):
            generate_grid(room, IES_PATH, nx=0, ny=2)

    def test_invalid_ny_raises(self):
        room = make_room()
        with pytest.raises(ValueError):
            generate_grid(room, IES_PATH, nx=2, ny=0)

    def test_non_square_room_layout(self):
        room = make_room(width=20.0, depth=5.0)
        lums = generate_grid(room, IES_PATH, nx=4, ny=2)
        assert len(lums) == 8
        xs = sorted({l.x for l in lums})
        assert xs[0] == pytest.approx(2.5)
        assert xs[-1] == pytest.approx(17.5)


class TestBestLayoutForCount:
    def test_square_room_1_luminaire(self):
        room = make_room(width=10, depth=10)
        nx, ny = best_layout_for_count(room, 1)
        assert nx * ny >= 1

    def test_square_room_4_luminaires_gives_2x2(self):
        room = make_room(width=10, depth=10)
        nx, ny = best_layout_for_count(room, 4)
        assert nx == 2 and ny == 2

    def test_wide_room_prefers_more_columns(self):
        room = make_room(width=20, depth=5)
        nx, ny = best_layout_for_count(room, 4)
        assert nx >= ny

    def test_tall_room_prefers_more_rows(self):
        room = make_room(width=5, depth=20)
        nx, ny = best_layout_for_count(room, 4)
        assert ny >= nx

    def test_zero_raises(self):
        room = make_room()
        with pytest.raises(ValueError):
            best_layout_for_count(room, 0)


class TestCandidateLayouts:
    def test_returns_list_of_tuples(self):
        room = make_room()
        layouts = candidate_layouts(room)
        assert all(isinstance(item, tuple) and len(item) == 2 for item in layouts)

    def test_no_duplicates(self):
        room = make_room()
        layouts = candidate_layouts(room)
        assert len(layouts) == len(set(layouts))

    def test_ascending_luminaire_count(self):
        room = make_room()
        layouts = candidate_layouts(room)
        counts = [nx * ny for nx, ny in layouts]
        assert counts == sorted(counts)

    def test_respects_max_count(self):
        room = make_room()
        layouts = candidate_layouts(room, max_count=10)
        assert all(nx * ny <= 10 for nx, ny in layouts)


# ===========================================================================
# Tests: optimizer/checker.py
# ===========================================================================

class TestCheckCompliance:
    def test_passes_when_both_criteria_met(self):
        result = make_simulation_result(avg_lux=350, uniformity=0.6, target_lux=300)
        check = check_compliance(result)
        assert check.passes is True
        assert check.reason == "OK"

    def test_fails_when_avg_lux_below_target(self):
        result = make_simulation_result(avg_lux=250, uniformity=0.6, target_lux=300)
        check = check_compliance(result)
        assert check.passes is False
        assert "avg" in check.reason

    def test_fails_when_uniformity_below_threshold(self):
        result = make_simulation_result(avg_lux=400, uniformity=0.3, target_lux=300)
        check = check_compliance(result)
        assert check.passes is False
        assert "uniformity" in check.reason

    def test_fails_when_both_criteria_missed(self):
        result = make_simulation_result(avg_lux=200, uniformity=0.2, target_lux=300)
        check = check_compliance(result)
        assert check.passes is False
        assert "avg" in check.reason
        assert "uniformity" in check.reason

    def test_exactly_on_boundary_passes(self):
        result = make_simulation_result(avg_lux=300.0, uniformity=0.4, target_lux=300)
        check = check_compliance(result, min_uniformity=0.4)
        assert check.passes is True

    def test_returns_lighting_check_instance(self):
        result = make_simulation_result()
        check = check_compliance(result)
        assert isinstance(check, LightingCheck)

    def test_custom_min_uniformity(self):
        result = make_simulation_result(avg_lux=350, uniformity=0.55, target_lux=300)
        check = check_compliance(result, min_uniformity=0.6)
        assert check.passes is False

    def test_check_fields_populated(self):
        result = make_simulation_result(avg_lux=350, min_lux=140, uniformity=0.5, target_lux=300)
        check = check_compliance(result, min_uniformity=0.4)
        assert check.avg_lux == pytest.approx(350)
        assert check.min_lux == pytest.approx(140)
        assert check.uniformity == pytest.approx(0.5)
        assert check.target_lux == pytest.approx(300)
        assert check.min_uniformity == pytest.approx(0.4)


# ===========================================================================
# Tests: estimate_luminaire_count
# ===========================================================================

class TestEstimateLuminaireCount:
    def test_basic_formula(self):
        # n = E*A / (Φ*CU*MF) = 300*100 / (10000*0.5*0.8) = 30000/4000 = 7.5 → 8
        room = make_room(width=10, depth=10, target_lux=300)
        assert estimate_luminaire_count(room, lumens=10_000) == 8

    def test_larger_room_needs_more(self):
        small = make_room(width=10, depth=10, target_lux=300)
        large = make_room(width=20, depth=20, target_lux=300)
        assert estimate_luminaire_count(large, 10_000) > estimate_luminaire_count(small, 10_000)

    def test_higher_target_needs_more(self):
        room_low = make_room(target_lux=100)
        room_high = make_room(target_lux=500)
        assert estimate_luminaire_count(room_high, 10_000) > estimate_luminaire_count(room_low, 10_000)

    def test_higher_lumens_needs_fewer(self):
        room = make_room(target_lux=300)
        assert estimate_luminaire_count(room, 5_000) > estimate_luminaire_count(room, 20_000)

    def test_minimum_is_one(self):
        room = make_room(width=1, depth=1, target_lux=1)
        assert estimate_luminaire_count(room, lumens=1_000_000) == 1

    def test_zero_area_returns_one(self):
        room = make_room(width=0, depth=0)
        assert estimate_luminaire_count(room, lumens=10_000) == 1

    def test_zero_lumens_returns_one(self):
        room = make_room()
        assert estimate_luminaire_count(room, lumens=0) == 1

    def test_custom_cu_and_mf(self):
        room = make_room(width=10, depth=10, target_lux=300)
        # Higher CU → fewer luminaires needed
        n_low_cu = estimate_luminaire_count(room, 10_000, cu=0.3)
        n_high_cu = estimate_luminaire_count(room, 10_000, cu=0.7)
        assert n_low_cu > n_high_cu

    def test_warehouse_order_of_magnitude(self):
        # 96×117m warehouse, 200 lux, 13000 lm lamp → roughly 200-500 lamps
        polygon = [(0, 0), (96, 0), (96, 117), (0, 117)]
        room = Room(name="wh", polygon=polygon, height=9, target_lux=200)
        n = estimate_luminaire_count(room, lumens=13_000)
        assert 100 < n < 1000


# ===========================================================================
# Tests: candidate_layouts_from_estimate
# ===========================================================================

class TestCandidateLayoutsFromEstimate:
    def test_returns_list_of_tuples(self):
        room = make_room()
        result = candidate_layouts_from_estimate(room, n_est=50)
        assert all(isinstance(item, tuple) and len(item) == 2 for item in result)

    def test_no_duplicates(self):
        room = make_room()
        result = candidate_layouts_from_estimate(room, n_est=50)
        assert len(result) == len(set(result))

    def test_ascending_count(self):
        room = make_room()
        result = candidate_layouts_from_estimate(room, n_est=50)
        counts = [nx * ny for nx, ny in result]
        assert counts == sorted(counts)

    def test_length_bounded_by_max_iterations(self):
        room = make_room()
        for mi in [3, 5, 10]:
            result = candidate_layouts_from_estimate(room, n_est=100, max_iterations=mi)
            assert len(result) <= mi

    def test_counts_near_estimate(self):
        # Candidates should be between ~50% and ~250% of n_est.
        # best_layout_for_count uses ceil so nx*ny can slightly exceed the target;
        # allow up to 15% overshoot on the upper bound.
        room = make_room()
        n_est = 100
        result = candidate_layouts_from_estimate(room, n_est=n_est)
        for nx, ny in result:
            count = nx * ny
            assert count >= round(n_est * 0.5) - 1
            assert count <= round(n_est * 2.5 * 1.15)

    def test_n_est_one_still_works(self):
        room = make_room()
        result = candidate_layouts_from_estimate(room, n_est=1)
        assert len(result) >= 1


# ===========================================================================
# Tests: optimizer/optimizer.py
# ===========================================================================

class TestOptimize:
    """All run_simulation calls are mocked.

    _load_lumens is also mocked so tests don't need a real IES file on disk.
    """

    def _patch(self, side_effects):
        """Patch run_simulation AND _load_lumens so no IES file or Radiance needed."""
        sim_patch = patch(
            "lighting_agent.optimizer.optimizer.run_simulation",
            side_effect=side_effects,
        )
        lm_patch = patch(
            "lighting_agent.optimizer.optimizer._load_lumens",
            return_value=10_000.0,
        )
        from contextlib import ExitStack
        stack = ExitStack()
        stack.enter_context(sim_patch)
        stack.enter_context(lm_patch)
        return stack

    def test_converges_on_first_iteration(self):
        room = make_room(target_lux=300)
        good = make_simulation_result(avg_lux=400, uniformity=0.6, target_lux=300)
        with self._patch([good]):
            opt = optimize(room, IES_PATH, max_iterations=10)
        assert opt.converged is True
        assert opt.iterations_used == 1

    def test_converges_on_second_iteration(self):
        room = make_room(target_lux=300)
        bad = make_simulation_result(avg_lux=200, uniformity=0.3, target_lux=300)
        good = make_simulation_result(avg_lux=400, uniformity=0.6, target_lux=300)
        with self._patch([bad, good]):
            opt = optimize(room, IES_PATH, max_iterations=10)
        assert opt.converged is True
        assert opt.iterations_used == 2

    def test_stops_at_max_iterations_when_not_converged(self):
        room = make_room(target_lux=300)
        bad = make_simulation_result(avg_lux=100, uniformity=0.1, target_lux=300)
        with self._patch([bad] * 5):
            opt = optimize(room, IES_PATH, max_iterations=5)
        assert opt.converged is False
        assert opt.iterations_used == 5

    def test_returns_optimization_result_instance(self):
        room = make_room()
        good = make_simulation_result(avg_lux=400, uniformity=0.6, target_lux=300)
        with self._patch([good]):
            opt = optimize(room, IES_PATH)
        assert isinstance(opt, OptimizationResult)

    def test_history_length_matches_iterations(self):
        room = make_room()
        bad = make_simulation_result(avg_lux=100, uniformity=0.1, target_lux=300)
        good = make_simulation_result(avg_lux=400, uniformity=0.6, target_lux=300)
        with self._patch([bad, bad, good]):
            opt = optimize(room, IES_PATH, max_iterations=10)
        assert len(opt.history) == 3

    def test_history_entries_have_expected_keys(self):
        room = make_room()
        good = make_simulation_result(avg_lux=400, uniformity=0.6, target_lux=300)
        with self._patch([good]):
            opt = optimize(room, IES_PATH)
        entry = opt.history[0]
        for key in ("iteration", "nx", "ny", "total_luminaires", "avg_lux", "uniformity", "passes"):
            assert key in entry

    def test_final_result_is_simulation_result(self):
        room = make_room()
        good = make_simulation_result(avg_lux=400, uniformity=0.6, target_lux=300)
        with self._patch([good]):
            opt = optimize(room, IES_PATH)
        assert isinstance(opt.final_result, SimulationResult)

    def test_final_check_is_lighting_check(self):
        room = make_room()
        good = make_simulation_result(avg_lux=400, uniformity=0.6, target_lux=300)
        with self._patch([good]):
            opt = optimize(room, IES_PATH)
        assert isinstance(opt.final_check, LightingCheck)

    def test_room_name_propagated(self):
        room = make_room()
        good = make_simulation_result(avg_lux=400, uniformity=0.6, target_lux=300)
        with self._patch([good]):
            opt = optimize(room, IES_PATH)
        assert opt.room_name == room.name

    def test_n_est_is_positive(self):
        room = make_room()
        good = make_simulation_result(avg_lux=400, uniformity=0.6, target_lux=300)
        with self._patch([good]):
            opt = optimize(room, IES_PATH)
        assert opt.n_est >= 1

    def test_lumens_per_lamp_matches_mock(self):
        room = make_room()
        good = make_simulation_result(avg_lux=400, uniformity=0.6, target_lux=300)
        with self._patch([good]):
            opt = optimize(room, IES_PATH)
        assert opt.lumens_per_lamp == pytest.approx(10_000.0)

    def test_total_luminaires_equals_nx_times_ny(self):
        room = make_room()
        good = make_simulation_result(avg_lux=400, uniformity=0.6, target_lux=300)
        with self._patch([good]):
            opt = optimize(room, IES_PATH)
        assert opt.total_luminaires == opt.nx * opt.ny

    def test_custom_min_uniformity_respected(self):
        room = make_room(target_lux=300)
        borderline = make_simulation_result(avg_lux=400, uniformity=0.45, target_lux=300)
        good = make_simulation_result(avg_lux=400, uniformity=0.6, target_lux=300)
        with self._patch([borderline, good]):
            opt = optimize(room, IES_PATH, max_iterations=5, min_uniformity=0.5)
        assert opt.converged is True
        assert opt.iterations_used == 2

    def test_max_iterations_one(self):
        room = make_room(target_lux=300)
        bad = make_simulation_result(avg_lux=100, uniformity=0.1, target_lux=300)
        with self._patch([bad]):
            opt = optimize(room, IES_PATH, max_iterations=1)
        assert opt.iterations_used == 1
        assert opt.converged is False
