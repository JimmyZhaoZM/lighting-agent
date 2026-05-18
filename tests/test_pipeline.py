"""Unit tests for Phase 5: falsecolor, pdf_report, cad/writer, pipeline.

All external I/O (Radiance, optimize) is mocked so the tests run without
installing Radiance or having real DXF/IES files on disk.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from lighting_agent.optimizer.checker import LightingCheck
from lighting_agent.optimizer.optimizer import OptimizationResult
from lighting_agent.pipeline import PipelineResult, run_pipeline
from lighting_agent.reporter.falsecolor import render_heatmap
from lighting_agent.reporter.pdf_report import generate_report
from lighting_agent.schemas import Luminaire, Room, SimulationResult


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

def make_room(name: str = "test_room", target_lux: float = 300.0) -> Room:
    return Room(
        name=name,
        polygon=[(0, 0), (10, 0), (10, 8), (0, 8)],
        height=4.0,
        target_lux=target_lux,
        mount_height=4.0,
    )


def make_luminaire(x: float = 5.0, y: float = 4.0) -> Luminaire:
    return Luminaire(ies_path="/dummy.ies", x=x, y=y, z=4.0)


def make_sim_result(
    room_name: str = "test_room",
    avg_lux: float = 350.0,
    uniformity: float = 0.55,
    target_lux: float = 300.0,
    nx: int = 4,
    ny: int = 4,
) -> SimulationResult:
    grid = [[avg_lux] * nx for _ in range(ny)]
    lums = [make_luminaire(x * 2.5, y * 2.0) for y in range(ny) for x in range(nx)]
    return SimulationResult(
        room_name=room_name,
        luminaires=lums,
        illuminance_grid=grid,
        grid_resolution=0.5,
        avg_lux=avg_lux,
        min_lux=avg_lux * uniformity,
        max_lux=avg_lux * 1.2,
        uniformity=uniformity,
        meets_target=avg_lux >= target_lux,
        target_lux=target_lux,
    )


def make_opt_result(room_name: str = "test_room", target_lux: float = 300.0) -> OptimizationResult:
    sim = make_sim_result(room_name=room_name, target_lux=target_lux)
    check = LightingCheck(
        passes=True, avg_lux=sim.avg_lux, min_lux=sim.min_lux,
        uniformity=sim.uniformity, target_lux=target_lux,
        min_uniformity=0.4, reason="OK",
    )
    return OptimizationResult(
        room_name=room_name, nx=4, ny=4, total_luminaires=16,
        iterations_used=1, converged=True,
        final_result=sim, final_check=check,
        n_est=14, lumens_per_lamp=10_000.0,
        history=[],
    )


# ===========================================================================
# Tests: reporter/falsecolor.py
# ===========================================================================

class TestRenderHeatmap:
    def test_creates_png_file(self, tmp_path):
        result = make_sim_result()
        out = tmp_path / "heatmap.png"
        render_heatmap(result, out)
        assert out.exists()
        assert out.stat().st_size > 0

    def test_creates_parent_dirs(self, tmp_path):
        result = make_sim_result()
        out = tmp_path / "sub" / "deep" / "heatmap.png"
        render_heatmap(result, out)
        assert out.exists()

    def test_returns_output_path(self, tmp_path):
        result = make_sim_result()
        out = tmp_path / "heatmap.png"
        returned = render_heatmap(result, out)
        assert returned == out

    def test_custom_colormap(self, tmp_path):
        result = make_sim_result()
        out = tmp_path / "viridis.png"
        render_heatmap(result, out, colormap="viridis")
        assert out.exists()

    def test_no_luminaires_still_renders(self, tmp_path):
        result = make_sim_result()
        result.luminaires = []
        out = tmp_path / "no_lums.png"
        render_heatmap(result, out)
        assert out.exists()

    def test_failed_room_renders(self, tmp_path):
        result = make_sim_result(avg_lux=100.0, target_lux=300.0)
        result.meets_target = False
        out = tmp_path / "fail.png"
        render_heatmap(result, out)
        assert out.exists()


# ===========================================================================
# Tests: reporter/pdf_report.py
# ===========================================================================

class TestGenerateReport:
    def test_creates_pdf(self, tmp_path):
        room = make_room()
        opt = make_opt_result()
        png = tmp_path / "heatmap.png"
        render_heatmap(opt.final_result, png)
        pdf = tmp_path / "report.pdf"
        generate_report([room], [opt], [png], pdf)
        assert pdf.exists()
        assert pdf.stat().st_size > 0

    def test_pdf_starts_with_magic_bytes(self, tmp_path):
        room = make_room()
        opt = make_opt_result()
        png = tmp_path / "hm.png"
        render_heatmap(opt.final_result, png)
        pdf = tmp_path / "report.pdf"
        generate_report([room], [opt], [png], pdf)
        assert pdf.read_bytes()[:4] == b"%PDF"

    def test_creates_parent_dirs(self, tmp_path):
        room = make_room()
        opt = make_opt_result()
        png = tmp_path / "hm.png"
        render_heatmap(opt.final_result, png)
        pdf = tmp_path / "sub" / "report.pdf"
        generate_report([room], [opt], [png], pdf)
        assert pdf.exists()

    def test_multiple_rooms(self, tmp_path):
        rooms = [make_room("Room A"), make_room("Room B")]
        opts = [make_opt_result("Room A"), make_opt_result("Room B")]
        pngs = []
        for opt in opts:
            p = tmp_path / f"{opt.room_name}.png"
            render_heatmap(opt.final_result, p)
            pngs.append(p)
        pdf = tmp_path / "multi.pdf"
        generate_report(rooms, opts, pngs, pdf)
        assert pdf.exists()

    def test_returns_output_path(self, tmp_path):
        room = make_room()
        opt = make_opt_result()
        png = tmp_path / "hm.png"
        render_heatmap(opt.final_result, png)
        pdf = tmp_path / "r.pdf"
        returned = generate_report([room], [opt], [png], pdf)
        assert returned == pdf

    def test_missing_heatmap_graceful(self, tmp_path):
        room = make_room()
        opt = make_opt_result()
        pdf = tmp_path / "no_img.pdf"
        generate_report([room], [opt], [tmp_path / "nonexistent.png"], pdf)
        assert pdf.exists()


# ===========================================================================
# Tests: cad/writer.py
# ===========================================================================

class TestWriteLayout:
    def _make_dxf(self, tmp_path) -> Path:
        import ezdxf
        doc = ezdxf.new("R2010")
        msp = doc.modelspace()
        pts = [(0, 0), (10, 0), (10, 8), (0, 8)]
        msp.add_lwpolyline(pts, close=True, dxfattribs={"layer": "LIGHT_ZONE"})
        p = tmp_path / "base.dxf"
        doc.saveas(str(p))
        return p

    def test_creates_output_file(self, tmp_path):
        from lighting_agent.cad.writer import write_layout
        dxf_in = self._make_dxf(tmp_path)
        out = tmp_path / "layout.dxf"
        write_layout(dxf_in, [make_room()], [make_opt_result()], out)
        assert out.exists()

    def test_light_layout_layer_created(self, tmp_path):
        import ezdxf as _ezdxf
        from lighting_agent.cad.writer import write_layout, LAYOUT_LAYER
        dxf_in = self._make_dxf(tmp_path)
        out = tmp_path / "layout.dxf"
        write_layout(dxf_in, [make_room()], [make_opt_result()], out)
        doc = _ezdxf.readfile(str(out))
        assert LAYOUT_LAYER in doc.layers

    def test_circles_added_for_each_luminaire(self, tmp_path):
        import ezdxf as _ezdxf
        from lighting_agent.cad.writer import write_layout, LAYOUT_LAYER
        dxf_in = self._make_dxf(tmp_path)
        out = tmp_path / "layout.dxf"
        opt = make_opt_result()
        write_layout(dxf_in, [make_room()], [opt], out)
        doc = _ezdxf.readfile(str(out))
        msp = doc.modelspace()
        circles = [e for e in msp if e.dxftype() == "CIRCLE" and e.dxf.layer == LAYOUT_LAYER]
        assert len(circles) == opt.total_luminaires

    def test_text_annotations_added(self, tmp_path):
        import ezdxf as _ezdxf
        from lighting_agent.cad.writer import write_layout, LAYOUT_LAYER
        dxf_in = self._make_dxf(tmp_path)
        out = tmp_path / "layout.dxf"
        write_layout(dxf_in, [make_room()], [make_opt_result()], out)
        doc = _ezdxf.readfile(str(out))
        msp = doc.modelspace()
        texts = [e for e in msp if e.dxftype() == "TEXT" and e.dxf.layer == LAYOUT_LAYER]
        assert len(texts) >= 1

    def test_returns_output_path(self, tmp_path):
        from lighting_agent.cad.writer import write_layout
        dxf_in = self._make_dxf(tmp_path)
        out = tmp_path / "layout.dxf"
        returned = write_layout(dxf_in, [make_room()], [make_opt_result()], out)
        assert returned == out


# ===========================================================================
# Tests: pipeline.py
# ===========================================================================

class TestRunPipeline:
    def _patches(self, tmp_path, rooms=None, opt=None):
        from contextlib import ExitStack
        if rooms is None:
            rooms = [make_room()]
        if opt is None:
            opt = make_opt_result()
        stack = ExitStack()
        stack.enter_context(patch("lighting_agent.pipeline.ensure_dxf",
                                  return_value=(Path(tmp_path / "dummy.dxf"), False)))
        stack.enter_context(patch("lighting_agent.pipeline.parse_rooms",
                                  return_value=rooms))
        stack.enter_context(patch("lighting_agent.pipeline.optimize",
                                  return_value=opt))
        stack.enter_context(patch("lighting_agent.pipeline.write_layout",
                                  return_value=Path(tmp_path / "layout.dxf")))
        stack.enter_context(patch("lighting_agent.pipeline.save_phase4_checkpoint"))
        return stack

    def test_returns_pipeline_result(self, tmp_path):
        with self._patches(tmp_path):
            result = run_pipeline("dummy.dxf", "dummy.ies", tmp_path)
        assert isinstance(result, PipelineResult)

    def test_pdf_created(self, tmp_path):
        with self._patches(tmp_path):
            result = run_pipeline("dummy.dxf", "dummy.ies", tmp_path)
        assert result.pdf_path.exists()
        assert result.pdf_path.suffix == ".pdf"

    def test_heatmap_created(self, tmp_path):
        with self._patches(tmp_path):
            result = run_pipeline("dummy.dxf", "dummy.ies", tmp_path)
        assert len(result.heatmap_paths) == 1
        for p in result.heatmap_paths:
            assert p.exists()

    def test_output_dir_created(self, tmp_path):
        out = tmp_path / "new_output"
        with self._patches(tmp_path):
            result = run_pipeline("dummy.dxf", "dummy.ies", out)
        assert out.exists()

    def test_no_rooms_raises(self, tmp_path):
        with patch("lighting_agent.pipeline.ensure_dxf",
                   return_value=(Path(tmp_path / "d.dxf"), False)):
            with patch("lighting_agent.pipeline.parse_rooms", return_value=[]):
                with pytest.raises(ValueError, match="No LIGHT_ZONE"):
                    run_pipeline("dummy.dxf", "dummy.ies", tmp_path)

    def test_result_fields_populated(self, tmp_path):
        with self._patches(tmp_path):
            result = run_pipeline("dummy.dxf", "dummy.ies", tmp_path,
                                  project_name="Test Project")
        assert result.rooms
        assert result.optimization_results
        assert result.layout_dxf_path is not None
        assert result.output_dir == tmp_path

    def test_multiple_rooms(self, tmp_path):
        rooms = [make_room("R1"), make_room("R2")]
        opts = [make_opt_result("R1"), make_opt_result("R2")]
        with patch("lighting_agent.pipeline.ensure_dxf",
                   return_value=(Path(tmp_path / "d.dxf"), False)):
            with patch("lighting_agent.pipeline.parse_rooms", return_value=rooms):
                with patch("lighting_agent.pipeline.optimize", side_effect=opts):
                    with patch("lighting_agent.pipeline.write_layout",
                               return_value=Path(tmp_path / "l.dxf")):
                        with patch("lighting_agent.pipeline.save_phase4_checkpoint"):
                            result = run_pipeline("dummy.dxf", "dummy.ies", tmp_path)
        assert len(result.rooms) == 2
        assert len(result.heatmap_paths) == 2
