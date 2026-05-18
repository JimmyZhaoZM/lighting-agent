"""Convert IES files to Radiance light sources via ies2rad.

ies2rad produces two files:
  <name>.rad  — Radiance material + geometry definition
  <name>.dat  — photometric data referenced by the .rad brightdata modifier

Both files must stay in the same directory.

Known issue: ies2rad fails with "illegal source dimensions" when a luminaire
has zero width AND zero length (common for downlights/disc fixtures).
We preprocess the IES file to replace (0, 0) with (0.01, 0.01) metres.
"""
from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from lighting_agent.ies.loader import IESData

_RADIANCE_BIN = Path("/usr/local/radiance/bin")
_RADIANCE_LIB = Path("/usr/local/radiance/lib")
# Minimum non-zero luminous opening dimension used to fix degenerate sources
_MIN_DIM = 0.010  # metres


@dataclass
class RadSource:
    rad_path: Path   # .rad file (Radiance material + geometry)
    dat_path: Path   # .dat file (photometric data)
    name: str        # base name (stem used for ies2rad -o)


def convert_ies(ies_data: IESData, work_dir: Path) -> RadSource:
    """Convert an IES file to a Radiance source in *work_dir*.

    Runs ies2rad with a preprocessed copy of the IES file to handle
    degenerate luminous-opening dimensions (width=0 or length=0).
    Returns a RadSource with paths to the generated .rad and .dat files.
    """
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    # Use an ASCII-safe stem: ies2rad embeds the output name in the .rad file;
    # non-ASCII characters cause garbled references to the .dat photometric file.
    name = _safe_stem(ies_data.name)
    fixed_ies = work_dir / f"{name}_fixed.ies"
    out_stem = str(work_dir / name)

    # Write dimension-corrected IES to work_dir
    original = Path(ies_data.path).read_text(encoding="latin-1")
    fixed_ies.write_text(_fix_dimensions(original), encoding="latin-1")

    subprocess.run(
        ["ies2rad", "-o", out_stem, str(fixed_ies)],
        capture_output=True,
        check=True,
        env=_radiance_env(),
    )

    rad_path = work_dir / f"{name}.rad"
    dat_path = work_dir / f"{name}.dat"

    if not rad_path.exists():
        raise FileNotFoundError(
            f"ies2rad did not produce {rad_path}; "
            "check that the IES file is valid IESNA LM-63 format"
        )

    return RadSource(rad_path=rad_path, dat_path=dat_path, name=name)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _safe_stem(name: str) -> str:
    """Return an ASCII-safe filename stem for ies2rad -o output.

    Strips non-ASCII characters then replaces any remaining non-word characters
    (except hyphens) with underscores.  Falls back to 'ies_source' if the result
    is empty.
    """
    ascii_only = name.encode("ascii", "ignore").decode("ascii")
    safe = re.sub(r"[^\w\-]", "_", ascii_only).strip("_")
    return safe if safe else "ies_source"


def _fix_dimensions(ies_text: str) -> str:
    """Replace zero width/length in the lamp descriptor line with _MIN_DIM."""
    lines = ies_text.splitlines()
    for i, line in enumerate(lines):
        if line.strip().upper().startswith("TILT"):
            j = _next_data_idx(lines, i + 1)
            if j is None:
                break
            parts = lines[j].split()
            if len(parts) >= 10:
                changed = False
                if float(parts[7]) == 0.0:
                    parts[7] = str(_MIN_DIM)
                    changed = True
                if float(parts[8]) == 0.0:
                    parts[8] = str(_MIN_DIM)
                    changed = True
                if changed:
                    lines[j] = " ".join(parts)
            break
    return "\n".join(lines)


def _next_data_idx(lines: list[str], start: int) -> int | None:
    for i in range(start, len(lines)):
        s = lines[i].strip()
        if s and not s.startswith("#"):
            return i
    return None


def _radiance_env() -> dict:
    env = os.environ.copy()
    env["PATH"] = f"{_RADIANCE_BIN}:{env.get('PATH', '')}"
    existing = env.get("RAYPATH", "")
    env["RAYPATH"] = f"{_RADIANCE_LIB}:{existing}" if existing else str(_RADIANCE_LIB)
    return env
