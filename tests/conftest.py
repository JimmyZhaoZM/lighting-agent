import pytest
import ezdxf


def _make_dxf_with_zone(tmp_path, filename, polygons_mm, prop_texts=None):
    doc = ezdxf.new()
    doc.layers.add("LIGHT_ZONE", color=3)
    msp = doc.modelspace()
    prop_texts = prop_texts or [None] * len(polygons_mm)
    for pts, prop_text in zip(polygons_mm, prop_texts):
        msp.add_lwpolyline(pts, close=True, dxfattribs={"layer": "LIGHT_ZONE"})
        if prop_text:
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            cx = (min(xs) + max(xs)) / 2
            cy = (min(ys) + max(ys)) / 2
            msp.add_text(
                prop_text,
                dxfattribs={"layer": "LIGHT_ZONE", "insert": (cx, cy), "height": 200},
            )
    path = tmp_path / filename
    doc.saveas(str(path))
    return path


@pytest.fixture
def simple_room_dxf(tmp_path):
    """One 10×10 m room (10 000×10 000 mm) with height=9, target=150, mount=9."""
    return _make_dxf_with_zone(
        tmp_path,
        "simple_room.dxf",
        [[(0, 0), (10000, 0), (10000, 10000), (0, 10000)]],
        ["height=9;target=150;mount=9"],
    )


@pytest.fixture
def two_rooms_dxf(tmp_path):
    """Two rooms: 10×10 m (target=150) and 5×8 m (target=300)."""
    return _make_dxf_with_zone(
        tmp_path,
        "two_rooms.dxf",
        [
            [(0, 0), (10000, 0), (10000, 10000), (0, 10000)],
            [(12000, 0), (17000, 0), (17000, 8000), (12000, 8000)],
        ],
        ["height=9;target=150;mount=9", "height=4;target=300;mount=3.5"],
    )


@pytest.fixture
def no_props_dxf(tmp_path):
    """LIGHT_ZONE polygon with no TEXT — parser must use defaults."""
    return _make_dxf_with_zone(
        tmp_path,
        "no_props.dxf",
        [[(0, 0), (6000, 0), (6000, 6000), (0, 6000)]],
        [None],
    )


@pytest.fixture
def empty_dxf(tmp_path):
    """DXF with no LIGHT_ZONE entities."""
    doc = ezdxf.new()
    path = tmp_path / "empty.dxf"
    doc.saveas(str(path))
    return path
