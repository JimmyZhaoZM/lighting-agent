"""Unit tests for Phase 3 — IES file loading and conversion.

Loader tests use the real IES fixture (no subprocess needed).
Converter tests mock ies2rad so they pass without Radiance installed.
"""
from __future__ import annotations

import math
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lighting_agent.ies.converter import RadSource, _fix_dimensions, _safe_stem, convert_ies
from lighting_agent.ies.loader import IESData, parse_ies, scan_ies_dir

FIXTURE_IES = Path(__file__).parent / "fixtures" / "飞碟灯-75W.ies"


# ---------------------------------------------------------------------------
# 3.1  loader.py
# ---------------------------------------------------------------------------

class TestParseIES:
    def test_lumens_parsed_correctly(self):
        data = parse_ies(FIXTURE_IES)
        # n_lamps=1, lumens_per_lamp=13000, candela_mult=1.0
        assert math.isclose(data.lumens, 13000.0, rel_tol=1e-3)

    def test_watts_parsed_correctly(self):
        data = parse_ies(FIXTURE_IES)
        assert math.isclose(data.watts, 74.28, rel_tol=1e-3)

    def test_name_is_filename_stem(self):
        data = parse_ies(FIXTURE_IES)
        assert data.name == "飞碟灯-75W"

    def test_path_is_absolute(self):
        data = parse_ies(FIXTURE_IES)
        assert data.path.is_absolute()

    def test_description_extracted(self):
        data = parse_ies(FIXTURE_IES)
        # [LUMINAIRE] field contains the lamp name (may be encoded)
        assert isinstance(data.description, str)
        assert len(data.description) > 0

    def test_returns_ies_data_instance(self):
        assert isinstance(parse_ies(FIXTURE_IES), IESData)

    def test_missing_tilt_raises(self, tmp_path: Path):
        bad_ies = tmp_path / "bad.ies"
        bad_ies.write_text("IESNA:LM-63-2002\n[LUMINAIRE] Test\n", encoding="latin-1")
        with pytest.raises(ValueError, match="TILT"):
            parse_ies(bad_ies)


class TestScanIESDir:
    def test_finds_fixture_file(self):
        results = scan_ies_dir(FIXTURE_IES.parent)
        names = [d.name for d in results]
        assert "飞碟灯-75W" in names

    def test_returns_list_of_ies_data(self):
        results = scan_ies_dir(FIXTURE_IES.parent)
        assert all(isinstance(d, IESData) for d in results)

    def test_empty_dir_returns_empty_list(self, tmp_path: Path):
        assert scan_ies_dir(tmp_path) == []

    def test_skips_malformed_files(self, tmp_path: Path):
        bad = tmp_path / "bad.ies"
        bad.write_text("not a real ies file", encoding="latin-1")
        # Should not raise, just skip
        result = scan_ies_dir(tmp_path)
        assert result == []

    def test_sorted_by_name(self, tmp_path: Path):
        # Create two minimal valid IES files
        for name, lumens in [("lamp_b", 5000), ("lamp_a", 3000)]:
            _write_minimal_ies(tmp_path / f"{name}.ies", lumens=lumens, watts=50.0)
        results = scan_ies_dir(tmp_path)
        assert [d.name for d in results] == ["lamp_a", "lamp_b"]


# ---------------------------------------------------------------------------
# 3.2  converter.py — dimension fix helper (no subprocess)
# ---------------------------------------------------------------------------

class TestFixDimensions:
    def _make_ies(self, w: float, l: float) -> str:
        return (
            "IESNA:LM-63-2002\n"
            "TILT=NONE\n"
            f"1 5000.0 1.0 10 10 1 2 {w} {l} 0.1\n"
            "1.0 1.0 50.0\n"
        )

    def test_zero_width_fixed(self):
        fixed = _fix_dimensions(self._make_ies(0.0, 0.0))
        parts = fixed.splitlines()[2].split()
        assert float(parts[7]) > 0.0

    def test_zero_length_fixed(self):
        fixed = _fix_dimensions(self._make_ies(0.0, 0.0))
        parts = fixed.splitlines()[2].split()
        assert float(parts[8]) > 0.0

    def test_nonzero_dimensions_unchanged(self):
        fixed = _fix_dimensions(self._make_ies(0.5, 0.3))
        parts = fixed.splitlines()[2].split()
        assert math.isclose(float(parts[7]), 0.5)
        assert math.isclose(float(parts[8]), 0.3)


# ---------------------------------------------------------------------------
# 3.3  converter.py — convert_ies (ies2rad mocked)
# ---------------------------------------------------------------------------

class TestConvertIES:
    def _fake_ies2rad(self, ies_data: IESData, work_dir: Path) -> RadSource:
        """Simulate ies2rad by writing stub .rad and .dat files."""
        rad = work_dir / f"{ies_data.name}.rad"
        dat = work_dir / f"{ies_data.name}.dat"
        rad.write_text(f"# stub rad for {ies_data.name}\n")
        dat.write_text("stub dat\n")

    def test_convert_returns_rad_source(self, tmp_path: Path):
        ies_data = parse_ies(FIXTURE_IES)

        def fake_run(cmd, **kwargs):
            # Simulate ies2rad creating the output files
            stem = Path(cmd[cmd.index("-o") + 1])
            (stem.parent / f"{stem.name}.rad").write_text("# stub\n")
            (stem.parent / f"{stem.name}.dat").write_text("stub\n")
            return MagicMock(returncode=0)

        with patch("lighting_agent.ies.converter.subprocess.run", side_effect=fake_run):
            result = convert_ies(ies_data, tmp_path / "out")

        assert isinstance(result, RadSource)
        assert result.rad_path.exists()
        assert result.name == _safe_stem(ies_data.name)

    def test_convert_creates_work_dir(self, tmp_path: Path):
        ies_data = parse_ies(FIXTURE_IES)

        def fake_run(cmd, **kwargs):
            stem = Path(cmd[cmd.index("-o") + 1])
            (stem.parent / f"{stem.name}.rad").write_text("# stub\n")
            (stem.parent / f"{stem.name}.dat").write_text("stub\n")
            return MagicMock(returncode=0)

        wd = tmp_path / "new_dir"
        with patch("lighting_agent.ies.converter.subprocess.run", side_effect=fake_run):
            convert_ies(ies_data, wd)

        assert wd.exists()

    def test_fixed_ies_written_to_work_dir(self, tmp_path: Path):
        ies_data = parse_ies(FIXTURE_IES)

        def fake_run(cmd, **kwargs):
            stem = Path(cmd[cmd.index("-o") + 1])
            (stem.parent / f"{stem.name}.rad").write_text("# stub\n")
            (stem.parent / f"{stem.name}.dat").write_text("stub\n")
            return MagicMock(returncode=0)

        wd = tmp_path / "out"
        with patch("lighting_agent.ies.converter.subprocess.run", side_effect=fake_run):
            convert_ies(ies_data, wd)

        # The dimension-fixed IES copy should exist in work_dir (ASCII-safe name)
        assert (wd / f"{_safe_stem(ies_data.name)}_fixed.ies").exists()


# ---------------------------------------------------------------------------
# 3.4  Real integration test — uses actual ies2rad (skipped if not installed)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not __import__("shutil").which("ies2rad"),
    reason="ies2rad not in PATH",
)
def test_real_convert_ies(tmp_path: Path):
    """End-to-end: convert real IES file with actual ies2rad."""
    ies_data = parse_ies(FIXTURE_IES)
    result = convert_ies(ies_data, tmp_path / "ies_out")
    assert result.rad_path.exists()
    assert result.rad_path.stat().st_size > 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_minimal_ies(path: Path, lumens: float, watts: float) -> None:
    path.write_text(
        "IESNA:LM-63-2002\n"
        "[LUMINAIRE] Test Lamp\n"
        "TILT=NONE\n"
        f"1 {lumens} 1.0 5 5 1 2 0.1 0.1 0.1\n"
        f"1.0 1.0 {watts}\n"
        "0.0 45.0 90.0 135.0 180.0\n"
        "0.0 90.0 180.0 270.0 360.0\n"
        "1000 800 500 200 0\n"
        "1000 800 500 200 0\n"
        "1000 800 500 200 0\n"
        "1000 800 500 200 0\n"
        "1000 800 500 200 0\n",
        encoding="latin-1",
    )
