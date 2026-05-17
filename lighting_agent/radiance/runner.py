"""Orchestrate a full Radiance simulation: Room + Luminaires → SimulationResult."""
from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

from lighting_agent.cad.geometry import bounding_box, point_in_polygon
from lighting_agent.radiance.model_builder import compile_oct, write_materials, write_scene
from lighting_agent.radiance.result_parser import build_simulation_result, parse_rtrace_lines
from lighting_agent.schemas import Luminaire, Room, SimulationResult

# rtrace parameters: -I irradiance, -h- suppress header, -fa ASCII output
_RTRACE_ARGS = ["-I", "-h-", "-fa", "-ab", "2", "-ad", "512", "-as", "256"]

# Radiance library path — needed for rayinit.cal and other .cal files
_RADIANCE_LIB = Path("/usr/local/radiance/lib")
_RADIANCE_BIN = Path("/usr/local/radiance/bin")


def _radiance_env() -> dict:
    """Return an environment dict with RAYPATH and PATH set for Radiance tools."""
    env = os.environ.copy()
    # Prepend Radiance bin so tools are found even if not in the user's PATH
    env["PATH"] = f"{_RADIANCE_BIN}:{env.get('PATH', '')}"
    # RAYPATH tells Radiance where to find .cal library files
    existing_raypath = env.get("RAYPATH", "")
    env["RAYPATH"] = f"{_RADIANCE_LIB}:{existing_raypath}" if existing_raypath else str(_RADIANCE_LIB)
    return env


def make_sensor_grid(
    room: Room,
    resolution: float = 0.5,
) -> tuple[list[tuple[float, float]], int, int]:
    """Return sensor points inside room polygon at work-plane height.

    Returns:
        (points, nx, ny) where points is list of (x, y) inside the polygon,
        and nx, ny are the bounding-box grid dimensions (used to reconstruct
        a 2-D illuminance grid later).
    """
    min_x, min_y, max_x, max_y = bounding_box(room.polygon)
    xs = _frange(min_x + resolution / 2, max_x, resolution)
    ys = _frange(min_y + resolution / 2, max_y, resolution)
    nx, ny = len(xs), len(ys)
    points = [
        (x, y)
        for y in ys
        for x in xs
        if point_in_polygon((x, y), room.polygon)
    ]
    return points, nx, ny


def write_sensors_pts(
    points: list[tuple[float, float]],
    work_plane_z: float,
    work_dir: Path,
) -> Path:
    """Write sensor grid to sensors.pts. Returns file path."""
    path = work_dir / "sensors.pts"
    lines = [f"{x:.4f} {y:.4f} {work_plane_z:.4f}  0 0 1" for x, y in points]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def run_rtrace(oct_path: Path, sensors_path: Path) -> list[str]:
    """Call rtrace and return raw output lines (one 'R G B' per sensor)."""
    with open(sensors_path, "rb") as sensors_file:
        result = subprocess.run(
            ["rtrace"] + _RTRACE_ARGS + [str(oct_path)],
            stdin=sensors_file,
            capture_output=True,
            check=True,
            env=_radiance_env(),
        )
    return result.stdout.decode("utf-8").splitlines()


def run_simulation(
    room: Room,
    luminaires: list[Luminaire],
    work_dir: Path | None = None,
    grid_resolution: float = 0.5,
) -> SimulationResult:
    """Full pipeline: Room + Luminaires → SimulationResult.

    Creates temporary files in work_dir (or a temp directory if None).
    """
    def _run(wd: Path) -> SimulationResult:
        mat_path = write_materials(wd)
        scene_path = write_scene(room, luminaires, wd)
        oct_path = compile_oct(wd, mat_path, scene_path)

        points, nx, ny = make_sensor_grid(room, grid_resolution)
        if not points:
            raise ValueError(f"No sensor points generated for room '{room.name}'")

        sensors_path = write_sensors_pts(points, room.work_plane_height, wd)
        raw_lines = run_rtrace(oct_path, sensors_path)

        return build_simulation_result(
            room=room,
            luminaires=luminaires,
            raw_lines=raw_lines,
            inside_points=points,
            nx=nx,
            ny=ny,
            grid_resolution=grid_resolution,
        )

    if work_dir is not None:
        work_dir.mkdir(parents=True, exist_ok=True)
        return _run(work_dir)

    with tempfile.TemporaryDirectory() as tmp:
        return _run(Path(tmp))


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------

def _frange(start: float, stop: float, step: float) -> list[float]:
    """Float range from start to stop (exclusive) with given step."""
    values: list[float] = []
    v = start
    while v < stop - step * 1e-6:
        values.append(v)
        v += step
    return values
