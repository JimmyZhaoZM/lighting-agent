"""Build Radiance scene files from Room + Luminaire data, then compile .oct."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

_RADIANCE_BIN = Path("/usr/local/radiance/bin")
_RADIANCE_LIB = Path("/usr/local/radiance/lib")


def _radiance_env() -> dict:
    env = os.environ.copy()
    env["PATH"] = f"{_RADIANCE_BIN}:{env.get('PATH', '')}"
    existing = env.get("RAYPATH", "")
    env["RAYPATH"] = f"{_RADIANCE_LIB}:{existing}" if existing else str(_RADIANCE_LIB)
    return env

from lighting_agent.radiance.materials import CEILING_MAT, FLOOR_MAT, WALL_MAT, materials_rad
from lighting_agent.schemas import Luminaire, Room

# Nominal radiance (W/m²/sr) for a small sphere placeholder light.
# Gives roughly the right order-of-magnitude illuminance for a 75W-class lamp.
# Phase 3 will replace this with ies2rad-generated sources.
_PLACEHOLDER_RADIANCE = 300_000.0
_SPHERE_RADIUS = 0.05  # metres


def write_materials(work_dir: Path) -> Path:
    """Write standard materials.rad into work_dir. Returns the file path."""
    path = work_dir / "materials.rad"
    path.write_text(materials_rad(), encoding="utf-8")
    return path


def write_scene(room: Room, luminaires: list[Luminaire], work_dir: Path) -> Path:
    """Write scene.rad for room geometry + luminaire spheres into work_dir."""
    blocks: list[str] = []

    # Floor — polygon at z = work_plane_height
    blocks.append(_polygon(
        f"{room.name}_floor",
        FLOOR_MAT,
        [(x, y, room.work_plane_height) for x, y in room.polygon],
    ))

    # Ceiling — reversed winding so outward normal faces downward into room
    blocks.append(_polygon(
        f"{room.name}_ceiling",
        CEILING_MAT,
        [(x, y, room.height) for x, y in reversed(room.polygon)],
    ))

    # Walls — one rectangle per polygon edge
    pts = room.polygon
    for i, (x1, y1) in enumerate(pts):
        x2, y2 = pts[(i + 1) % len(pts)]
        wall_verts = [
            (x1, y1, room.work_plane_height),
            (x2, y2, room.work_plane_height),
            (x2, y2, room.height),
            (x1, y1, room.height),
        ]
        blocks.append(_polygon(f"{room.name}_wall_{i}", WALL_MAT, wall_verts))

    # Luminaires — small sphere light sources (placeholder until Phase 3 IES)
    for idx, lum in enumerate(luminaires):
        blocks.append(_sphere_light(f"lum_{idx}", lum))

    path = work_dir / "scene.rad"
    path.write_text("\n".join(blocks), encoding="utf-8")
    return path


def compile_oct(work_dir: Path, *rad_files: Path) -> Path:
    """Call oconv to compile .rad files into a .oct octree. Returns .oct path."""
    oct_path = work_dir / "scene.oct"
    result = subprocess.run(
        ["oconv"] + [str(f) for f in rad_files],
        capture_output=True,
        check=True,
        env=_radiance_env(),
    )
    oct_path.write_bytes(result.stdout)
    return oct_path


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _polygon(
    name: str,
    material: str,
    vertices: list[tuple[float, float, float]],
) -> str:
    n = len(vertices)
    coord_str = "  ".join(f"{x:.4f} {y:.4f} {z:.4f}" for x, y, z in vertices)
    return f"{material} polygon {name}\n0\n0\n{n * 3}\n{coord_str}\n"


def _sphere_light(name: str, lum: Luminaire) -> str:
    r = _PLACEHOLDER_RADIANCE
    return (
        f"void light {name}_src\n0\n0\n3 {r} {r} {r}\n\n"
        f"{name}_src sphere {name}\n0\n0\n"
        f"4 {lum.x:.4f} {lum.y:.4f} {lum.z:.4f} {_SPHERE_RADIUS}\n"
    )
