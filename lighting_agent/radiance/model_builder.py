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

# Sphere placeholder: used only when no valid IES file is available.
# The radiance value is arbitrary; real simulations should always supply an IES path.
_PLACEHOLDER_RADIANCE = 300_000.0
_SPHERE_RADIUS = 0.05  # metres


def write_materials(work_dir: Path) -> Path:
    """Write standard materials.rad into work_dir. Returns the file path."""
    path = work_dir / "materials.rad"
    path.write_text(materials_rad(), encoding="utf-8")
    return path


def write_scene(room: Room, luminaires: list[Luminaire], work_dir: Path) -> Path:
    """Write scene.rad for room geometry + luminaire sources into work_dir.

    Each luminaire is represented by its IES-converted Radiance source when
    *lum.ies_path* points to a valid IES file; otherwise falls back to a
    sphere placeholder so the scene remains renderable.
    """
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

    # Luminaires — use IES sources when available, else sphere placeholder
    _ies_cache: dict[str, object] = {}  # ies_path → RadSource | None
    for idx, lum in enumerate(luminaires):
        ies_src = _load_ies_source(lum.ies_path, work_dir, _ies_cache)
        if ies_src is not None:
            blocks.append(_xform_ies_source(f"lum_{idx}", lum, ies_src))
        else:
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


def _load_ies_source(
    ies_path: str | None,
    work_dir: Path,
    cache: dict,
) -> object | None:
    """Convert *ies_path* to a RadSource, caching results.  Returns None on failure."""
    if not ies_path:
        return None
    if ies_path in cache:
        return cache[ies_path]
    try:
        from lighting_agent.ies.converter import convert_ies
        from lighting_agent.ies.loader import parse_ies
        ies_data = parse_ies(ies_path)
        ies_subdir = work_dir / "ies"
        src = convert_ies(ies_data, ies_subdir)
        cache[ies_path] = src
    except Exception:
        cache[ies_path] = None
    return cache[ies_path]


def _xform_ies_source(name: str, lum: Luminaire, source: object) -> str:
    """Return a Radiance !xform line that places the IES source at (x, y, z).

    ies2rad centers the luminaire at the origin.  We translate it to the
    mount position and apply an optional azimuth rotation (rz).
    The !xform directive is expanded by oconv when building the .oct file.
    """
    rot = f"-rz {lum.rotation_deg:.1f} " if lum.rotation_deg else ""
    rad_path = source.rad_path  # type: ignore[attr-defined]
    return (
        f"# {name}: IES source from {rad_path.name}\n"
        f"!xform -t {lum.x:.4f} {lum.y:.4f} {lum.z:.4f} {rot}"
        f'"{rad_path}"\n'
    )
