"""IES file scanning and metadata parsing.

Supports IESNA LM-63 format (1986, 1991, 1995, 2002 revisions).
Extracts lumens, watts, and description without a full photometric parse.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class IESData:
    path: Path          # absolute path to the .ies file
    name: str           # filename stem (no extension)
    lumens: float       # total luminous flux (lm) = n_lamps × lumens_per_lamp × candela_mult
    watts: float        # input power (W)
    description: str    # value of [LUMINAIRE] keyword, or filename if absent


def scan_ies_dir(ies_dir: Path | str) -> list[IESData]:
    """Scan *ies_dir* for .ies files and return parsed metadata, sorted by name."""
    ies_dir = Path(ies_dir)
    results = []
    for p in sorted(ies_dir.glob("*.ies")) + sorted(ies_dir.glob("*.IES")):
        try:
            results.append(parse_ies(p))
        except (ValueError, IndexError):
            pass  # skip malformed files silently
    # deduplicate (glob may return same file twice on case-insensitive FS)
    seen: set[Path] = set()
    unique = []
    for d in results:
        if d.path not in seen:
            seen.add(d.path)
            unique.append(d)
    return sorted(unique, key=lambda d: d.name.lower())


def parse_ies(path: Path) -> IESData:
    """Parse a single IES file and return its photometric metadata.

    Raises ValueError if the file does not contain the required data block.
    """
    path = Path(path)
    text = path.read_text(encoding="latin-1")
    lines = [ln.rstrip() for ln in text.splitlines()]

    description = _extract_keyword(lines, "LUMINAIRE") or path.stem

    # Locate the TILT= line; the two data lines follow immediately after it
    tilt_idx = _find_tilt(lines)
    if tilt_idx is None:
        raise ValueError(f"{path.name}: TILT line not found")

    # Line after TILT= (or after TILT data if TILT≠NONE) is the lamp descriptor
    lamp_line = _next_data_line(lines, tilt_idx + 1)
    if lamp_line is None:
        raise ValueError(f"{path.name}: lamp descriptor line not found")

    lamp_parts = lamp_line.split()
    if len(lamp_parts) < 10:
        raise ValueError(f"{path.name}: lamp descriptor has too few fields")

    n_lamps = int(float(lamp_parts[0]))
    lumens_per_lamp = float(lamp_parts[1])
    candela_mult = float(lamp_parts[2])
    lumens = n_lamps * lumens_per_lamp * candela_mult

    # Next data line: ballast_factor  future_use  input_watts
    watts_line = _next_data_line(lines, lines.index(lamp_line) + 1)
    if watts_line is None:
        raise ValueError(f"{path.name}: watts line not found")

    watts_parts = watts_line.split()
    if len(watts_parts) < 3:
        raise ValueError(f"{path.name}: watts line has too few fields")

    watts = float(watts_parts[2])

    return IESData(
        path=path.resolve(),
        name=path.stem,
        lumens=lumens,
        watts=watts,
        description=description,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _extract_keyword(lines: list[str], keyword: str) -> str | None:
    """Return the value of an IESNA keyword line like '[LUMINAIRE] foo bar'."""
    prefix = f"[{keyword}]"
    for line in lines:
        if line.upper().startswith(prefix.upper()):
            return line[len(prefix):].strip() or None
    return None


def _find_tilt(lines: list[str]) -> int | None:
    """Return the index of the TILT= line."""
    for i, line in enumerate(lines):
        if line.strip().upper().startswith("TILT"):
            return i
    return None


def _next_data_line(lines: list[str], start: int) -> str | None:
    """Return the next non-empty, non-comment line at or after *start*."""
    for line in lines[start:]:
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return stripped
    return None
