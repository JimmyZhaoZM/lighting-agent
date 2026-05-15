import pytest
from lighting_agent.cad.parser import parse_rooms
from lighting_agent.schemas import Room


def test_parse_single_room_count(simple_room_dxf):
    rooms = parse_rooms(str(simple_room_dxf))
    assert len(rooms) == 1


def test_parse_single_room_type(simple_room_dxf):
    rooms = parse_rooms(str(simple_room_dxf))
    assert isinstance(rooms[0], Room)


def test_parse_single_room_properties(simple_room_dxf):
    room = parse_rooms(str(simple_room_dxf))[0]
    assert room.height == pytest.approx(9.0)
    assert room.target_lux == pytest.approx(150.0)
    assert room.mount_height == pytest.approx(9.0)


def test_parse_single_room_mm_to_m_conversion(simple_room_dxf):
    room = parse_rooms(str(simple_room_dxf))[0]
    xs = [p[0] for p in room.polygon]
    assert max(xs) == pytest.approx(10.0)


def test_parse_single_room_polygon_vertex_count(simple_room_dxf):
    room = parse_rooms(str(simple_room_dxf))[0]
    assert len(room.polygon) == 4


def test_parse_two_rooms(two_rooms_dxf):
    rooms = parse_rooms(str(two_rooms_dxf))
    assert len(rooms) == 2


def test_parse_two_rooms_different_properties(two_rooms_dxf):
    rooms = parse_rooms(str(two_rooms_dxf))
    targets = {r.target_lux for r in rooms}
    assert targets == {150.0, 300.0}


def test_parse_no_props_uses_defaults(no_props_dxf):
    room = parse_rooms(str(no_props_dxf))[0]
    assert room.height == pytest.approx(3.0)
    assert room.target_lux == pytest.approx(300.0)


def test_parse_no_props_mount_defaults_to_height(no_props_dxf):
    room = parse_rooms(str(no_props_dxf))[0]
    assert room.mount_height == pytest.approx(room.height)


def test_parse_empty_dxf_returns_empty_list(empty_dxf):
    assert parse_rooms(str(empty_dxf)) == []
