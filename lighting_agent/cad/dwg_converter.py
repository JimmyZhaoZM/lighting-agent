"""
DWG → DXF conversion.

Priority:
  1. ODA File Converter (/Applications/ODAFileConverter.app) — supports AC1018+
  2. dwg2dxf (LibreDWG) — fallback if ODA not installed

Install ODA: https://www.opendesign.com/guestfiles/oda_file_converter
Install LibreDWG: brew install libredwg (if available on your platform)
"""
import subprocess
import shutil
from pathlib import Path

_ODA_BINARY = Path("/Applications/ODAFileConverter.app/Contents/MacOS/ODAFileConverter")


def is_dwg(path: str | Path) -> bool:
    return Path(path).suffix.lower() == ".dwg"


def _oda_available() -> bool:
    return _ODA_BINARY.exists()


def _dwg2dxf_available() -> bool:
    return shutil.which("dwg2dxf") is not None


def _convert_with_oda(dwg_path: Path, out_dir: Path) -> Path:
    """Convert using ODA File Converter (batch mode)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [
            str(_ODA_BINARY),
            str(dwg_path.parent),   # input folder
            str(out_dir),           # output folder
            "ACAD2010",             # output DWG version (ignored for DXF output)
            "DXF",                  # output format
            "0",                    # recurse subdirs: no
            "1",                    # audit: yes
            dwg_path.name,          # specific file to convert
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    dxf_path = out_dir / dwg_path.with_suffix(".dxf").name
    if not dxf_path.exists():
        raise RuntimeError(
            f"ODA converter ran but output not found: {dxf_path}\n"
            f"stderr: {result.stderr}"
        )
    return dxf_path


def _convert_with_dwg2dxf(dwg_path: Path, out_dir: Path) -> Path:
    """Convert using LibreDWG dwg2dxf."""
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
        raise RuntimeError(f"dwg2dxf ran but output not found: {dxf_path}")
    return dxf_path


def dwg_to_dxf(dwg_path: str | Path, output_dir: str | Path | None = None) -> Path:
    """Convert a DWG file to DXF.

    Tries ODA File Converter first, then dwg2dxf (LibreDWG).
    Returns the path to the generated DXF file.
    """
    dwg_path = Path(dwg_path).resolve()
    if not dwg_path.exists():
        raise FileNotFoundError(f"DWG file not found: {dwg_path}")

    out_dir = Path(output_dir).resolve() if output_dir else dwg_path.parent

    if _oda_available():
        return _convert_with_oda(dwg_path, out_dir)

    if _dwg2dxf_available():
        return _convert_with_dwg2dxf(dwg_path, out_dir)

    raise RuntimeError(
        "No DWG converter found. Install one of:\n"
        "  ODA File Converter: https://www.opendesign.com/guestfiles/oda_file_converter\n"
        "  LibreDWG: brew install libredwg"
    )


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
