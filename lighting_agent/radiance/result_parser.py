"""Parse rtrace output and build SimulationResult."""
from __future__ import annotations

from lighting_agent.cad.geometry import bounding_box, point_in_polygon
from lighting_agent.schemas import Luminaire, Room, SimulationResult

# Radiance photometric constant: 1 W/m² white irradiance ≈ 179 lux
_K = 179.0
# CIE luminous efficiency weights for R, G, B channels
_WR, _WG, _WB = 0.265, 0.670, 0.065


def rgb_to_lux(r: float, g: float, b: float) -> float:
    """Convert Radiance R G B irradiance (W/m²/sr per channel) to illuminance (lux)."""
    return _K * (_WR * r + _WG * g + _WB * b)


def parse_rtrace_lines(lines: list[str]) -> list[float]:
    """Parse rtrace output lines ('R G B' per line) into a flat list of lux values."""
    lux_values: list[float] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) != 3:
            raise ValueError(f"Expected 3 values per rtrace line, got: {line!r}")
        r, g, b = float(parts[0]), float(parts[1]), float(parts[2])
        lux_values.append(rgb_to_lux(r, g, b))
    return lux_values


def build_simulation_result(
    room: Room,
    luminaires: list[Luminaire],
    raw_lines: list[str],
    inside_points: list[tuple[float, float]],
    nx: int,
    ny: int,
    grid_resolution: float,
) -> SimulationResult:
    """Build SimulationResult from rtrace output and grid metadata.

    The 2-D illuminance_grid covers the bounding-box (nx × ny cells).
    Points outside the room polygon are stored as 0.0 and excluded from
    statistics.  inside_points and raw_lines must be the same length.
    """
    lux_values = parse_rtrace_lines(raw_lines)
    if len(lux_values) != len(inside_points):
        raise ValueError(
            f"rtrace returned {len(lux_values)} values but "
            f"{len(inside_points)} sensor points were sent"
        )

    # Build lookup: (ix, iy) → lux
    min_x, min_y, _, _ = bounding_box(room.polygon)
    lux_map: dict[tuple[int, int], float] = {}
    for (x, y), lux in zip(inside_points, lux_values):
        ix = round((x - (min_x + grid_resolution / 2)) / grid_resolution)
        iy = round((y - (min_y + grid_resolution / 2)) / grid_resolution)
        lux_map[(ix, iy)] = lux

    # 2-D grid: rows = iy (y-axis), cols = ix (x-axis)
    grid = [
        [lux_map.get((ix, iy), 0.0) for ix in range(nx)]
        for iy in range(ny)
    ]

    # Statistics from inside-polygon points only
    avg_lux = sum(lux_values) / len(lux_values) if lux_values else 0.0
    min_lux = min(lux_values) if lux_values else 0.0
    max_lux = max(lux_values) if lux_values else 0.0
    uniformity = min_lux / avg_lux if avg_lux > 0 else 0.0
    meets_target = avg_lux >= room.target_lux

    return SimulationResult(
        room_name=room.name,
        luminaires=luminaires,
        illuminance_grid=grid,
        grid_resolution=grid_resolution,
        avg_lux=avg_lux,
        min_lux=min_lux,
        max_lux=max_lux,
        uniformity=uniformity,
        meets_target=meets_target,
        target_lux=room.target_lux,
    )
