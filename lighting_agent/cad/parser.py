from __future__ import annotations

import ezdxf

from .dwg_converter import ensure_dxf
from .geometry import vertices_mm_to_m, validate_polygon, point_in_polygon, polygon_area
from ..schemas import Room
from ..utils.checkpoint import save_phase1_checkpoint

_LAYER_PREFIX = "LIGHT_ZONE"  # matches "LIGHT_ZONE", "LIGHT_ZONE_堆货区", etc.
_DEFAULT_HEIGHT = 3.0
_DEFAULT_TARGET_LUX = 300.0
_DEFAULT_WORK_PLANE = 0.0


def _is_light_zone(layer: str) -> bool:
    return layer.upper().startswith(_LAYER_PREFIX)


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


def _extract_polylines(msp) -> list[tuple[list[tuple[float, float]], str]]:
    """Return list of (vertices, layer_name) for each LIGHT_ZONE* LWPOLYLINE."""
    polys: list[tuple[list[tuple[float, float]], str]] = []
    for entity in msp:
        if entity.dxftype() == "LWPOLYLINE" and _is_light_zone(entity.dxf.layer):
            verts = [(p[0], p[1]) for p in entity.get_points()]
            if len(verts) >= 3:
                polys.append((verts, entity.dxf.layer))
    return polys


def _match_props(
    msp, poly_layers: list[tuple[list[tuple[float, float]], str]]
) -> list[dict[str, str]]:
    """Assign TEXT/MTEXT to the polygon on the same LIGHT_ZONE* layer.

    Layer-name matching is used first (unambiguous even for nested polygons).
    Falls back to point-in-polygon (smallest containing polygon wins) only
    when no same-layer polygon exists.
    """
    props_list: list[dict[str, str]] = [{} for _ in poly_layers]
    layer_to_indices: dict[str, list[int]] = {}
    for i, (_, layer_name) in enumerate(poly_layers):
        layer_to_indices.setdefault(layer_name.upper(), []).append(i)

    # Fallback order: smallest polygon first
    areas = [polygon_area(poly) for poly, _ in poly_layers]
    fallback_order = sorted(range(len(poly_layers)), key=lambda i: areas[i])

    for entity in msp:
        if not _is_light_zone(entity.dxf.layer) or entity.dxftype() not in ("TEXT", "MTEXT"):
            continue
        raw = (
            entity.plain_mtext()
            if entity.dxftype() == "MTEXT"
            else entity.dxf.text
        )
        props = _parse_props(raw)
        if not props:
            continue

        insert = entity.dxf.insert
        point = (insert.x, insert.y)

        # Primary: same layer with only one polygon → unambiguous
        same_layer = layer_to_indices.get(entity.dxf.layer.upper(), [])
        if len(same_layer) == 1:
            props_list[same_layer[0]].update(props)
            continue

        # Fallback: point-in-polygon among candidates (smallest wins)
        candidates = same_layer if same_layer else list(range(len(poly_layers)))
        cand_order = sorted(candidates, key=lambda i: areas[i])
        for i in cand_order:
            poly, _ = poly_layers[i]
            if point_in_polygon(point, poly):
                props_list[i].update(props)
                break
    return props_list


def parse_rooms(cad_path: str, tmp_dir: str | None = None) -> list[Room]:
    """Parse a DWG or DXF file; return all LIGHT_ZONE* regions as Room objects."""
    dxf_path, was_converted = ensure_dxf(cad_path, tmp_dir=tmp_dir)
    try:
        doc = ezdxf.readfile(str(dxf_path))
        msp = doc.modelspace()
        poly_layers = _extract_polylines(msp)
        if not poly_layers:
            return []
        props_list = _match_props(msp, poly_layers)
        rooms: list[Room] = []
        for i, ((verts_mm, layer_name), props) in enumerate(zip(poly_layers, props_list)):
            validate_polygon(verts_mm)
            verts_m = vertices_mm_to_m(verts_mm)
            height = _float_prop(props, "height", _DEFAULT_HEIGHT)
            target = _float_prop(props, "target", _DEFAULT_TARGET_LUX)
            mount = _float_prop(props, "mount", height)
            work_plane = _float_prop(props, "work_plane", _DEFAULT_WORK_PLANE)
            # Use explicit name prop, or layer suffix, or fallback
            suffix = layer_name[len(_LAYER_PREFIX):].lstrip("_") or f"zone_{i + 1}"
            name = props.get("name", suffix)
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
        if rooms:
            checkpoint_data = [
                {
                    "name": r.name,
                    "polygon": r.polygon,
                    "height_m": r.height,
                    "work_plane_height_m": r.work_plane_height,
                    "target_lux": r.target_lux,
                    "mount_height_m": r.mount_height,
                }
                for r in rooms
            ]
            save_phase1_checkpoint(checkpoint_data)
        return rooms
    finally:
        if was_converted:
            dxf_path.unlink(missing_ok=True)
