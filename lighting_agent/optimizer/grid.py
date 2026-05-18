"""Generate candidate luminaire layouts as uniform nx×ny grids."""
from __future__ import annotations

import math

from lighting_agent.cad.geometry import bounding_box, polygon_area
from lighting_agent.schemas import Luminaire, Room


def generate_grid(
    room: Room,
    ies_path: str,
    nx: int,
    ny: int,
) -> list[Luminaire]:
    """Place nx×ny luminaires in a uniform grid inside the room bounding box.

    Luminaires are centered within each cell so the spacing from the wall
    equals half the inter-luminaire spacing.  All luminaires are placed at
    room.mount_height.
    """
    if nx < 1 or ny < 1:
        raise ValueError(f"nx and ny must be >= 1, got nx={nx} ny={ny}")

    min_x, min_y, max_x, max_y = bounding_box(room.polygon)
    width = max_x - min_x
    depth = max_y - min_y
    z = room.mount_height  # __post_init__ ensures this is never None

    # cell-centre positions: divide [min, max] into n equal cells
    xs = [min_x + (i + 0.5) * width / nx for i in range(nx)]
    ys = [min_y + (j + 0.5) * depth / ny for j in range(ny)]

    return [
        Luminaire(ies_path=ies_path, x=x, y=y, z=z)
        for y in ys
        for x in xs
    ]


def best_layout_for_count(room: Room, total_n: int) -> tuple[int, int]:
    """Choose (nx, ny) whose aspect ratio best matches the room's bounding box.

    For a given total luminaire count, iterate over all integer factorisations
    and pick the one whose nx/ny ratio is closest to room_width/room_depth.
    Returns (nx, ny) with nx >= 1, ny >= 1, nx*ny == total_n (or nearest above).
    """
    if total_n < 1:
        raise ValueError(f"total_n must be >= 1, got {total_n}")

    min_x, min_y, max_x, max_y = bounding_box(room.polygon)
    width = max_x - min_x
    depth = max_y - min_y
    # Target aspect ratio (width per depth column); default 1.0 for degenerate rooms
    target_ratio = (width / depth) if depth > 1e-9 else 1.0

    best_nx, best_ny = 1, total_n
    best_score = float("inf")

    for nx in range(1, total_n + 1):
        ny = math.ceil(total_n / nx)
        actual_ratio = nx / ny if ny else nx
        score = abs(actual_ratio - target_ratio)
        if score < best_score:
            best_score = score
            best_nx, best_ny = nx, ny

    return best_nx, best_ny


def estimate_luminaire_count(
    room: Room,
    lumens: float,
    cu: float = 0.5,
    mf: float = 0.8,
) -> int:
    """Estimate minimum luminaire count using the lumen method.

    Formula: n = (E_target × A) / (Φ × CU × MF)

        E_target  target illuminance (lux)
        A         floor area (m²)
        Φ         luminous flux per luminaire (lm)
        CU        coefficient of utilization — default 0.5 (conservative for
                  open industrial spaces; real value depends on room geometry
                  and reflectances, typically 0.4–0.7)
        MF        maintenance factor — default 0.8 (accounts for lamp ageing
                  and dirt accumulation)

    Result is rounded up and used as the starting point for iterative search,
    so it does not need to be exact.
    """
    area = polygon_area(room.polygon)
    if area <= 0 or lumens <= 0:
        return 1
    n = (room.target_lux * area) / (lumens * cu * mf)
    return max(1, math.ceil(n))


def candidate_layouts_from_estimate(
    room: Room,
    n_est: int,
    max_iterations: int = 10,
) -> list[tuple[int, int]]:
    """Return up to *max_iterations* candidate (nx, ny) pairs centred on *n_est*.

    Searches from 50 % to 250 % of the lumen-method estimate in ascending
    luminaire-count order so the optimizer finds the minimum compliant layout
    first.  Duplicate (nx, ny) pairs are skipped.
    """
    # Fixed fractional multipliers — ascending so smallest count is tried first.
    # Range 0.5–2.5× covers typical CU and MF uncertainty.
    _FRACS = [0.50, 0.60, 0.70, 0.80, 0.90, 1.00, 1.20, 1.50, 2.00, 2.50]

    seen: set[tuple[int, int]] = set()
    result: list[tuple[int, int]] = []
    for frac in _FRACS:
        n = max(1, round(n_est * frac))
        nx, ny = best_layout_for_count(room, n)
        key = (nx, ny)
        if key not in seen:
            seen.add(key)
            result.append(key)
        if len(result) >= max_iterations:
            break
    return result


def candidate_layouts(room: Room, max_count: int = 30) -> list[tuple[int, int]]:
    """Return a list of (nx, ny) pairs in ascending order of total luminaire count.

    Covers totals 1, 2, 4, 6, 9, 12, 16, 20, 25 up to max_count, plus
    intermediate steps chosen to match the room aspect ratio.
    Duplicates (same nx, ny) are removed.
    """
    counts = [1, 2, 4, 6, 9, 12, 16, 20, 25, 30, 36, 42, 49, 56, 64]
    seen: set[tuple[int, int]] = set()
    result: list[tuple[int, int]] = []
    for n in counts:
        if n > max_count:
            break
        nx, ny = best_layout_for_count(room, n)
        key = (nx, ny)
        if key not in seen:
            seen.add(key)
            result.append(key)
    return result
