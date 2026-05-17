"""Standard Radiance material definitions.

Default surface reflectances:
  floor   0.20  (concrete / dark tile)
  wall    0.50  (painted plaster)
  ceiling 0.70  (white / light plaster)
"""
from __future__ import annotations

FLOOR_REFLECTANCE: float = 0.2
WALL_REFLECTANCE: float = 0.5
CEILING_REFLECTANCE: float = 0.7

FLOOR_MAT = "floor_mat"
WALL_MAT = "wall_mat"
CEILING_MAT = "ceiling_mat"


def _plastic(name: str, reflectance: float) -> str:
    r = reflectance
    return f"void plastic {name}\n0\n0\n5 {r} {r} {r} 0 0\n"


def materials_rad() -> str:
    """Return the standard materials block as a Radiance .rad string."""
    return (
        _plastic(FLOOR_MAT, FLOOR_REFLECTANCE)
        + "\n"
        + _plastic(WALL_MAT, WALL_REFLECTANCE)
        + "\n"
        + _plastic(CEILING_MAT, CEILING_REFLECTANCE)
    )
