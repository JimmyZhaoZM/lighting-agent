"""Validate a SimulationResult against photometric compliance criteria."""
from __future__ import annotations

from dataclasses import dataclass

from lighting_agent.schemas import SimulationResult


@dataclass
class LightingCheck:
    passes: bool
    avg_lux: float
    min_lux: float
    uniformity: float          # Emin / Eave
    target_lux: float
    min_uniformity: float
    reason: str                # "OK" or human-readable failure description


def check_compliance(
    result: SimulationResult,
    min_uniformity: float = 0.4,
) -> LightingCheck:
    """Check whether *result* meets the room's illuminance requirements.

    Criteria (matching GB 50034 / IESNA RP-1 practice):
    - Average illuminance >= target_lux
    - Uniformity (Emin / Eave) >= min_uniformity

    Returns a LightingCheck with passes=True only when both criteria are met.
    """
    failures: list[str] = []

    if result.avg_lux < result.target_lux:
        failures.append(
            f"avg {result.avg_lux:.1f} lux < target {result.target_lux:.0f} lux"
        )

    if result.uniformity < min_uniformity:
        failures.append(
            f"uniformity {result.uniformity:.3f} < {min_uniformity}"
        )

    passes = len(failures) == 0
    reason = "OK" if passes else "; ".join(failures)

    return LightingCheck(
        passes=passes,
        avg_lux=result.avg_lux,
        min_lux=result.min_lux,
        uniformity=result.uniformity,
        target_lux=result.target_lux,
        min_uniformity=min_uniformity,
        reason=reason,
    )
