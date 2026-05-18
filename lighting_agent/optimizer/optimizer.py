"""Iterative luminaire placement optimizer.

Strategy:
1. Use the lumen method to estimate the required luminaire count (n_est).
2. Generate candidate (nx, ny) grids spanning 50 %–250 % of n_est in ascending
   luminaire-count order so we find the *minimum* compliant layout first.
3. Simulate each candidate with Radiance and stop on the first pass.
4. Hard cap: max_iterations simulation runs.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from lighting_agent.optimizer.checker import LightingCheck, check_compliance
from lighting_agent.optimizer.grid import (
    candidate_layouts_from_estimate,
    estimate_luminaire_count,
    generate_grid,
)
from lighting_agent.radiance.runner import run_simulation
from lighting_agent.schemas import Luminaire, Room, SimulationResult

logger = logging.getLogger(__name__)

# Fallback lumens when the IES file cannot be read (keeps the optimizer alive)
_FALLBACK_LUMENS = 1_000.0


@dataclass
class OptimizationResult:
    """Outcome of a single room optimisation run."""
    room_name: str
    nx: int
    ny: int
    total_luminaires: int
    iterations_used: int
    converged: bool                          # True if a compliant layout was found
    final_result: SimulationResult
    final_check: LightingCheck
    n_est: int                               # lumen-method estimate (informational)
    lumens_per_lamp: float                   # luminous flux used for estimate
    history: list[dict] = field(default_factory=list)  # per-iteration snapshots


def optimize(
    room: Room,
    ies_path: str,
    *,
    max_iterations: int = 10,
    min_uniformity: float = 0.4,
    grid_resolution: float = 0.5,
    work_dir: Path | None = None,
    rtrace_args: list[str] | None = None,
) -> OptimizationResult:
    """Find the minimum-count luminaire layout that satisfies *room*'s requirements.

    Steps:
    1. Parse IES file to get lumens per lamp.
    2. Estimate required count (lumen method: n = E·A / Φ·CU·MF).
    3. Generate candidates: 50 %–250 % of estimate, ascending, deduplicated.
    4. Simulate each; stop on first compliant result or when max_iterations hit.

    Args:
        room:            Room definition (polygon, target_lux, mount_height …).
        ies_path:        Path to the IES file for all luminaires in this room.
        max_iterations:  Hard cap on simulation runs (default 10).
        min_uniformity:  Minimum Emin/Eave ratio required (default 0.4).
        grid_resolution: Sensor grid spacing for simulation (metres, default 0.5).
        work_dir:        Directory for Radiance scratch files (temp dir if None).
        rtrace_args:     Override default rtrace quality parameters.

    Returns:
        OptimizationResult with the best (or last) layout found.
    """
    # ── Step 1: get luminaire flux ────────────────────────────────────────────
    lumens = _load_lumens(ies_path)

    # ── Step 2: lumen-method estimate ─────────────────────────────────────────
    n_est = estimate_luminaire_count(room, lumens)
    logger.info(
        "Room '%s': lumen estimate = %d luminaires "
        "(Φ=%.0f lm, target=%.0f lux, area=%.0f m²)",
        room.name, n_est, lumens, room.target_lux,
        _room_area(room),
    )

    # ── Step 3: build candidate list ──────────────────────────────────────────
    candidates = candidate_layouts_from_estimate(room, n_est, max_iterations)
    if not candidates:
        candidates = [(1, 1)]

    # ── Step 4: simulate each candidate ──────────────────────────────────────
    history: list[dict] = []
    last_result: SimulationResult | None = None
    last_check: LightingCheck | None = None
    last_nx = last_ny = 1

    for iteration, (nx, ny) in enumerate(candidates, start=1):
        luminaires = generate_grid(room, ies_path, nx, ny)
        logger.info(
            "Iteration %d/%d: trying %d×%d grid (%d luminaires) for room '%s'",
            iteration, len(candidates), nx, ny, len(luminaires), room.name,
        )

        result = run_simulation(
            room=room,
            luminaires=luminaires,
            work_dir=work_dir,
            grid_resolution=grid_resolution,
            rtrace_args=rtrace_args,
        )
        check = check_compliance(result, min_uniformity=min_uniformity)

        history.append({
            "iteration": iteration,
            "nx": nx,
            "ny": ny,
            "total_luminaires": len(luminaires),
            "avg_lux": round(result.avg_lux, 1),
            "min_lux": round(result.min_lux, 1),
            "uniformity": round(result.uniformity, 3),
            "passes": check.passes,
            "reason": check.reason,
        })

        last_result, last_check, last_nx, last_ny = result, check, nx, ny

        if check.passes:
            logger.info(
                "Room '%s' converged at iteration %d: %d×%d (%d luminaires), "
                "avg=%.0f lux, uniformity=%.3f",
                room.name, iteration, nx, ny, len(luminaires),
                result.avg_lux, result.uniformity,
            )
            break
    else:
        logger.warning(
            "Room '%s' did not converge within %d iterations. "
            "Last result: avg=%.0f lux, uniformity=%.3f. "
            "Consider using a higher-output luminaire or increasing max_iterations.",
            room.name, max_iterations,
            last_result.avg_lux, last_result.uniformity,
        )

    return OptimizationResult(
        room_name=room.name,
        nx=last_nx,
        ny=last_ny,
        total_luminaires=last_nx * last_ny,
        iterations_used=len(history),
        converged=last_check.passes,
        final_result=last_result,
        final_check=last_check,
        n_est=n_est,
        lumens_per_lamp=lumens,
        history=history,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_lumens(ies_path: str) -> float:
    """Return lumens from *ies_path*, falling back to _FALLBACK_LUMENS on error."""
    try:
        from lighting_agent.ies.loader import parse_ies
        return parse_ies(ies_path).lumens
    except Exception as exc:
        logger.warning("Could not read lumens from '%s' (%s); using fallback %.0f lm",
                       ies_path, exc, _FALLBACK_LUMENS)
        return _FALLBACK_LUMENS


def _room_area(room: Room) -> float:
    from lighting_agent.cad.geometry import polygon_area
    return polygon_area(room.polygon)
