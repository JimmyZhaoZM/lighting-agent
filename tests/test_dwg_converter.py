import shutil
import pytest
from pathlib import Path
from lighting_agent.cad.dwg_converter import is_dwg, ensure_dxf


def test_is_dwg_returns_true_for_dwg():
    assert is_dwg("plan.dwg") is True
    assert is_dwg(Path("floor.DWG")) is True


def test_is_dwg_returns_false_for_dxf():
    assert is_dwg("plan.dxf") is False
    assert is_dwg(Path("floor.DXF")) is False


def test_ensure_dxf_passthrough_for_dxf(simple_room_dxf):
    dxf_path, was_converted = ensure_dxf(simple_room_dxf)
    assert dxf_path == simple_room_dxf
    assert was_converted is False


def test_ensure_dxf_raises_file_not_found_for_missing_dwg():
    with pytest.raises(FileNotFoundError):
        ensure_dxf(Path("/nonexistent/file.dwg"))


def test_ensure_dxf_raises_if_no_converter(tmp_path, monkeypatch):
    import lighting_agent.cad.dwg_converter as mod
    monkeypatch.setattr(shutil, "which", lambda _cmd: None)
    monkeypatch.setattr(mod, "_oda_available", lambda: False)
    fake_dwg = tmp_path / "test.dwg"
    fake_dwg.write_bytes(b"fake")
    with pytest.raises(RuntimeError, match="No DWG converter found"):
        ensure_dxf(fake_dwg)
