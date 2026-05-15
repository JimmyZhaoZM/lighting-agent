"""
DWG → DXF conversion via LibreDWG's dwg2dxf command.

Install: brew install libredwg
"""
import subprocess
import shutil
from pathlib import Path


def is_dwg(path: str | Path) -> bool:
    return Path(path).suffix.lower() == ".dwg"


def dwg_to_dxf(dwg_path: str | Path, output_dir: str | Path | None = None) -> Path:
    """Convert a DWG file to DXF using dwg2dxf.

    Returns the path to the generated DXF file.
    The caller is responsible for deleting it when done.
    """
    dwg_path = Path(dwg_path).resolve()
    if not dwg_path.exists():
        raise FileNotFoundError(f"DWG file not found: {dwg_path}")

    if not shutil.which("dwg2dxf"):
        raise RuntimeError(
            "dwg2dxf not found. Run ./install.sh to install LibreDWG."
        )

    out_dir = Path(output_dir).resolve() if output_dir else dwg_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    dxf_path = out_dir / dwg_path.with_suffix(".dxf").name

    result = subprocess.run(
        ["dwg2dxf", "-o", str(dxf_path), str(dwg_path)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"dwg2dxf failed (exit {result.returncode}):\n{result.stderr}"
        )
    if not dxf_path.exists():
        raise RuntimeError(f"dwg2dxf ran but output file not found: {dxf_path}")

    return dxf_path


def ensure_dxf(cad_path: str | Path, tmp_dir: str | Path | None = None) -> tuple[Path, bool]:
    """Return a DXF path for any CAD input (DWG or DXF).

    Returns (dxf_path, was_converted).
    If was_converted is True, the caller should delete dxf_path after use.
    """
    cad_path = Path(cad_path)
    if is_dwg(cad_path):
        dxf_path = dwg_to_dxf(cad_path, output_dir=tmp_dir)
        return dxf_path, True
    return cad_path, False
