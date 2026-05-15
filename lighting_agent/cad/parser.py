from __future__ import annotations

import ezdxf

from .dwg_converter import ensure_dxf
from .geometry import vertices_mm_to_m, validate_polygon, point_in_polygon
from ..schemas import Room

_LAYER = "LIGHT_ZONE"
_DEFAULT_HEIGHT = 3.0
_DEFAULT_TARGET_LUX = 300.0
_DEFAULT_WORK_PLANE = 0.0


def _parse_props(text: str) -> dict[str, str]:
    """'height=9;target=150;mount=9' → {'height': '9', 'target': '150', 'mount': '9'}"""
    props: dict[str, str] = {}
    for part in text.strip().split(";"):
        if "=" in part:
            key, _, val = part.partition("=")
            props[key.strip()] = val.strip()
    return props


def _float_prop(props: dict[str, str], key: str, default: float) -> float:
    try:
        return float(props[key]) if key in props else default
    except ValueError:
        return default


def _extract_polylines(msp) -> list[list[tuple[float, float]]]:
    polys: list[list[tuple[float, float]]] = []
    for entity in msp:
        if entity.dxftype() == "LWPOLYLINE" and entity.dxf.layer == _LAYER:
            verts = [(p[0], p[1]) for p in entity.get_points()]
            if len(verts) >= 3:
                polys.append(verts)
    return polys


def _match_props(
    msp, polygons_mm: list[list[tuple[float, float]]]
) -> list[dict[str, str]]:
    """Assign TEXT/MTEXT on LIGHT_ZONE layer to the polygon that contains it."""
    props_list: list[dict[str, str]] = [{} for _ in polygons_mm]
    for entity in msp:
        if entity.dxf.layer != _LAYER or entity.dxftype() not in ("TEXT", "MTEXT"):
            continue
        insert = entity.dxf.insert
        point = (insert.x, insert.y)
        raw = (
            entity.plain_mtext()
            if entity.dxftype() == "MTEXT"
            else entity.dxf.text
        )
        props = _parse_props(raw)
        if not props:
            continue
        for i, poly in enumerate(polygons_mm):
            if point_in_polygon(point, poly):
                props_list[i].update(props)
                break
    return props_list


def parse_rooms(cad_path: str, tmp_dir: str | None = None) -> list[Room]:
    """Parse a DWG or DXF file; return all LIGHT_ZONE regions as Room objects."""
    dxf_path, was_converted = ensure_dxf(cad_path, tmp_dir=tmp_dir)
    try:
        doc = ezdxf.readfile(str(dxf_path))
        msp = doc.modelspace()
        polys_mm = _extract_polylines(msp)
        if not polys_mm:
            return []
        props_list = _match_props(msp, polys_mm)
        rooms: list[Room] = []
        for i, (verts_mm, props) in enumerate(zip(polys_mm, props_list)):
            validate_polygon(verts_mm)
            verts_m = vertices_mm_to_m(verts_mm)
            height = _float_prop(props, "height", _DEFAULT_HEIGHT)
            target = _float_prop(props, "target", _DEFAULT_TARGET_LUX)
            mount = _float_prop(props, "mount", height)
            work_plane = _float_prop(props, "work_plane", _DEFAULT_WORK_PLANE)
            name = props.get("name", f"zone_{i + 1}")
            rooms.append(
                Room(
                    name=name,
                    polygon=verts_m,
                    height=height,
                    work_plane_height=work_plane,
                    target_lux=target,
                    mount_height=mount,
                )
            )
        return rooms
    finally:
        if was_converted:
            dxf_path.unlink(missing_ok=True)
