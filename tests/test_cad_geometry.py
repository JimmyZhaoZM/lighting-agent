import pytest
from lighting_agent.cad.geometry import (
    mm_to_m,
    vertices_mm_to_m,
    validate_polygon,
    polygon_area,
    point_in_polygon,
    bounding_box,
)


def test_mm_to_m_converts_correctly():
    assert mm_to_m(1000.0) == pytest.approx(1.0)
    assert mm_to_m(0.0) == 0.0
    assert mm_to_m(500.0) == pytest.approx(0.5)


def test_vertices_mm_to_m():
    verts_mm = [(0, 0), (10000, 0), (10000, 10000), (0, 10000)]
    result = vertices_mm_to_m(verts_mm)
    assert result == [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]


def test_validate_polygon_accepts_triangle():
    validate_polygon([(0, 0), (1, 0), (0, 1)])  # must not raise


def test_validate_polygon_rejects_two_points():
    with pytest.raises(ValueError, match="at least 3"):
        validate_polygon([(0, 0), (1, 0)])


def test_polygon_area_square():
    square = [(0, 0), (10, 0), (10, 10), (0, 10)]
    assert polygon_area(square) == pytest.approx(100.0)


def test_polygon_area_triangle():
    tri = [(0, 0), (4, 0), (0, 3)]
    assert polygon_area(tri) == pytest.approx(6.0)


def test_point_in_polygon_inside():
    square = [(0, 0), (10, 0), (10, 10), (0, 10)]
    assert point_in_polygon((5.0, 5.0), square) is True


def test_point_in_polygon_outside():
    square = [(0, 0), (10, 0), (10, 10), (0, 10)]
    assert point_in_polygon((15.0, 5.0), square) is False


def test_bounding_box():
    verts = [(1, 2), (5, 3), (2, 8)]
    assert bounding_box(verts) == (1, 2, 5, 8)
