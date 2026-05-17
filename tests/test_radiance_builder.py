"""Unit tests for Phase 2 — Radiance model building and simulation.

All tests that invoke oconv / rtrace use monkeypatching so they pass
without Radiance being installed.
"""
from __future__ import annotations

import math
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lighting_agent.radiance.materials import (
    CEILING_MAT,
    CEILING_REFLECTANCE,
    FLOOR_MAT,
    FLOOR_REFLECTANCE,
    WALL_MAT,
    WALL_REFLECTANCE,
    materials_rad,
)
from lighting_agent.radiance.model_builder import (
    _polygon,
    _sphere_light,
    write_materials,
    write_scene,
)
from lighting_agent.radiance.result_parser import (
    build_simulation_result,
    parse_rtrace_lines,
    rgb_to_lux,
)
from lighting_agent.radiance.runner import make_sensor_grid, run_simulation, write_sensors_pts
from lighting_agent.schemas import Luminaire, Room, SimulationResult


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def simple_room() -> Room:
    """4 m x 3 m rectangular room, 3 m high, target 300 lux."""
    return Room(
        name="test_room",
        polygon=[(0.0, 0.0), (4.0, 0.0), (4.0, 3.0), (0.0, 3.0)],
        height=3.0,
        work_plane_height=0.0,
        target_lux=300.0,
        mount_height=3.0,
    )


@pytest.fixture()
def single_luminaire() -> Luminaire:
    return Luminaire(ies_path="placeholder.ies", x=2.0, y=1.5, z=3.0)


# ---------------------------------------------------------------------------
# 2.1  materials.py
# ---------------------------------------------------------------------------

class TestMaterials:
    def test_materials_rad_contains_all_three(self):
        rad = materials_rad()
        assert FLOOR_MAT in rad
        assert WALL_MAT in rad
        assert CEILING_MAT in rad

    def test_floor_reflectance_value(self):
        rad = materials_rad()
        assert str(FLOOR_REFLECTANCE) in rad

    def test_wall_reflectance_value(self):
        rad = materials_rad()
        assert str(WALL_REFLECTANCE) in rad

    def test_ceiling_reflectance_value(self):
        rad = materials_rad()
        assert str(CEILING_REFLECTANCE) in rad

    def test_plastic_keyword_present(self):
        assert "void plastic" in materials_rad()

    def test_write_materials_creates_file(self, tmp_path: Path):
        path = write_materials(tmp_path)
        assert path.exists()
        assert path.suffix == ".rad"
        assert FLOOR_MAT in path.read_text()


# ---------------------------------------------------------------------------
# 2.2  model_builder.py
# ---------------------------------------------------------------------------

class TestModelBuilder:
    def test_polygon_helper_vertex_count(self):
        verts = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)]
        rad = _polygon("test", "floor_mat", verts)
        assert "12\n" in rad  # 4 vertices x 3 coords

    def test_polygon_helper_name(self):
        rad = _polygon("my_floor", "floor_mat", [(0, 0, 0), (1, 0, 0), (0, 1, 0)])
        assert "my_floor" in rad

    def test_sphere_light_contains_position(self, single_luminaire: Luminaire):
        rad = _sphere_light("lum_0", single_luminaire)
        assert "2.0000" in rad
        assert "1.5000" in rad
        assert "3.0000" in rad

    def test_sphere_light_contains_void_light(self, single_luminaire: Luminaire):
        rad = _sphere_light("lum_0", single_luminaire)
        assert "void light" in rad

    def test_write_scene_creates_file(self, tmp_path: Path, simple_room: Room, single_luminaire: Luminaire):
        path = write_scene(simple_room, [single_luminaire], tmp_path)
        assert path.exists()

    def test_write_scene_contains_floor_and_ceiling(
        self, tmp_path: Path, simple_room: Room, single_luminaire: Luminaire
    ):
        content = write_scene(simple_room, [single_luminaire], tmp_path).read_text()
        assert "floor" in content
        assert "ceiling" in content

    def test_write_scene_wall_count(
        self, tmp_path: Path, simple_room: Room, single_luminaire: Luminaire
    ):
        content = write_scene(simple_room, [single_luminaire], tmp_path).read_text()
        # 4-vertex polygon -> 4 walls; each wall polygon is named "_wall_<i>"
        assert content.count("_wall_") == 4

    def test_write_scene_luminaire_present(
        self, tmp_path: Path, simple_room: Room, single_luminaire: Luminaire
    ):
        content = write_scene(simple_room, [single_luminaire], tmp_path).read_text()
        assert "lum_0" in content


# ---------------------------------------------------------------------------
# 2.3  runner.py  -- sensor grid
# ---------------------------------------------------------------------------

class TestSensorGrid:
    def test_grid_points_inside_polygon(self, simple_room: Room):
        points, nx, ny = make_sensor_grid(simple_room, resolution=1.0)
        for x, y in points:
            assert 0.0 <= x <= 4.0
            assert 0.0 <= y <= 3.0

    def test_grid_point_count_roughly_correct(self, simple_room: Room):
        # 4x3 room with 1 m resolution -> expect ~12 points
        points, nx, ny = make_sensor_grid(simple_room, resolution=1.0)
        assert 8 <= len(points) <= 12

    def test_nx_ny_dimensions(self, simple_room: Room):
        _, nx, ny = make_sensor_grid(simple_room, resolution=1.0)
        assert nx == 4
        assert ny == 3

    def test_half_resolution_more_points(self, simple_room: Room):
        pts1, _, _ = make_sensor_grid(simple_room, resolution=1.0)
        pts2, _, _ = make_sensor_grid(simple_room, resolution=0.5)
        assert len(pts2) > len(pts1)

    def test_write_sensors_pts_format(self, simple_room: Room, tmp_path: Path):
        points, _, _ = make_sensor_grid(simple_room, resolution=1.0)
        path = write_sensors_pts(points, 0.0, tmp_path)
        lines = path.read_text().strip().splitlines()
        assert len(lines) == len(points)
        # Each line: x y z dx dy dz (6 values)
        parts = lines[0].split()
        assert len(parts) == 6
        assert parts[3:] == ["0", "0", "1"]  # upward normal


# ---------------------------------------------------------------------------
# 2.4  result_parser.py
# ---------------------------------------------------------------------------

class TestResultParser:
    def test_rgb_to_lux_white(self):
        # White light: R=G=B=1 -> 179*(0.265+0.670+0.065) = 179
        lux = rgb_to_lux(1.0, 1.0, 1.0)
        assert math.isclose(lux, 179.0, rel_tol=1e-6)

    def test_rgb_to_lux_green_dominant(self):
        lux = rgb_to_lux(0.0, 1.0, 0.0)
        assert math.isclose(lux, 179.0 * 0.670, rel_tol=1e-6)

    def test_parse_single_line(self):
        lux = parse_rtrace_lines(["1.0 1.0 1.0"])
        assert math.isclose(lux[0], 179.0, rel_tol=1e-6)

    def test_parse_skips_blank_lines(self):
        lux = parse_rtrace_lines(["", "1.0 1.0 1.0", ""])
        assert len(lux) == 1

    def test_parse_wrong_column_count_raises(self):
        with pytest.raises(ValueError):
            parse_rtrace_lines(["1.0 2.0"])

    def test_build_simulation_result_statistics(self, simple_room: Room, single_luminaire: Luminaire):
        inside_points = [(0.5, 0.5), (1.5, 0.5), (0.5, 1.5), (1.5, 1.5)]
        raw_lines = ["1.0 1.0 1.0"] * 4
        result = build_simulation_result(
            room=simple_room,
            luminaires=[single_luminaire],
            raw_lines=raw_lines,
            inside_points=inside_points,
            nx=2,
            ny=2,
            grid_resolution=1.0,
        )
        assert isinstance(result, SimulationResult)
        assert math.isclose(result.avg_lux, 179.0, rel_tol=1e-6)
        assert math.isclose(result.min_lux, 179.0, rel_tol=1e-6)
        assert math.isclose(result.uniformity, 1.0, rel_tol=1e-6)

    def test_build_simulation_result_meets_target(self, simple_room: Room, single_luminaire: Luminaire):
        inside_points = [(0.5, 0.5)]
        # 179 lux < 300 lux target -> not meeting target
        result = build_simulation_result(
            room=simple_room,
            luminaires=[single_luminaire],
            raw_lines=["1.0 1.0 1.0"],
            inside_points=inside_points,
            nx=1,
            ny=1,
            grid_resolution=1.0,
        )
        assert result.meets_target is False

    def test_build_simulation_result_grid_shape(self, simple_room: Room, single_luminaire: Luminaire):
        inside_points = [(0.5, 0.5), (1.5, 0.5), (0.5, 1.5), (1.5, 1.5)]
        raw_lines = ["1.0 1.0 1.0"] * 4
        result = build_simulation_result(
            room=simple_room,
            luminaires=[single_luminaire],
            raw_lines=raw_lines,
            inside_points=inside_points,
            nx=2,
            ny=2,
            grid_resolution=1.0,
        )
        assert len(result.illuminance_grid) == 2       # ny rows
        assert len(result.illuminance_grid[0]) == 2   # nx cols

    def test_mismatch_raises(self, simple_room: Room, single_luminaire: Luminaire):
        with pytest.raises(ValueError):
            build_simulation_result(
                room=simple_room,
                luminaires=[single_luminaire],
                raw_lines=["1.0 1.0 1.0", "2.0 2.0 2.0"],
                inside_points=[(0.5, 0.5)],  # 1 point but 2 lines
                nx=1,
                ny=1,
                grid_resolution=1.0,
            )


# ---------------------------------------------------------------------------
# 2.5  run_simulation -- integration (subprocess mocked)
# ---------------------------------------------------------------------------

class TestRunSimulation:
    def _make_fake_rtrace_output(self, n_points: int) -> bytes:
        return ("\n".join(["1.0 1.0 1.0"] * n_points) + "\n").encode()

    def test_run_simulation_returns_simulation_result(
        self, tmp_path: Path, simple_room: Room, single_luminaire: Luminaire
    ):
        points, _, _ = make_sensor_grid(simple_room, resolution=1.0)
        fake_oct = b"\x00" * 16

        def fake_run(cmd, **kwargs):
            m = MagicMock()
            if cmd[0] == "oconv":
                m.stdout = fake_oct
            else:
                m.stdout = self._make_fake_rtrace_output(len(points))
            return m

        with patch("lighting_agent.radiance.model_builder.subprocess.run", side_effect=fake_run):
            with patch("lighting_agent.radiance.runner.subprocess.run", side_effect=fake_run):
                result = run_simulation(
                    room=simple_room,
                    luminaires=[single_luminaire],
                    work_dir=tmp_path / "sim",
                    grid_resolution=1.0,
                )

        assert isinstance(result, SimulationResult)
        assert result.room_name == "test_room"
        assert result.avg_lux > 0
        assert result.grid_resolution == 1.0

    def test_run_simulation_work_dir_created(
        self, tmp_path: Path, simple_room: Room, single_luminaire: Luminaire
    ):
        points, _, _ = make_sensor_grid(simple_room, resolution=1.0)

        def fake_run(cmd, **kwargs):
            m = MagicMock()
            if cmd[0] == "oconv":
                m.stdout = b"\x00" * 16
            else:
                m.stdout = self._make_fake_rtrace_output(len(points))
            return m

        wd = tmp_path / "my_sim"
        with patch("lighting_agent.radiance.model_builder.subprocess.run", side_effect=fake_run):
            with patch("lighting_agent.radiance.runner.subprocess.run", side_effect=fake_run):
                run_simulation(simple_room, [single_luminaire], work_dir=wd, grid_resolution=1.0)

        assert wd.exists()
        assert (wd / "materials.rad").exists()
        assert (wd / "scene.rad").exists()
