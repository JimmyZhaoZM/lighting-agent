"""Write luminaire layout back to a DXF file on the LIGHT_LAYOUT layer.

Each luminaire is drawn as:
  - A circle (radius = 0.3 m) representing the fixture body
  - A cross (+) for the centre point
  - A text label showing the room name and sequence number

A summary block of TEXT entities at the room centroid reports:
  total count, avg lux, uniformity, and compliance status.

All entities are written to the LIGHT_LAYOUT layer so they can be toggled
independently of the original CAD geometry.
"""
from __future__ import annotations

import math
from pathlib import Path

import ezdxf
from ezdxf.enums import TextEntityAlignment

from lighting_agent.cad.geometry import bounding_box
from lighting_agent.optimizer.optimizer import OptimizationResult
from lighting_agent.schemas import Room

LAYOUT_LAYER = "LIGHT_LAYOUT"
_CIRCLE_RADIUS_M = 0.3   # fixture symbol radius in metres
_CROSS_HALF = 0.2        # half-size of cross arm in metres
_TEXT_HEIGHT = 0.5       # text height in metres


def write_layout(
    dxf_path: Path,
    rooms: list[Room],
    results: list[OptimizationResult],
    output_path: Path | None = None,
) -> Path:
    """Add LIGHT_LAYOUT entities to *dxf_path* and save to *output_path*.

    If *output_path* is None, overwrites *dxf_path* in place.

    Args:
        dxf_path:    Source DXF file (must be readable by ezdxf).
        rooms:       Room definitions (same order as results).
        results:     OptimizationResult per room.
        output_path: Destination DXF.  None → same as dxf_path.

    Returns:
        Path to the written DXF file.
    """
    output_path = Path(output_path) if output_path else Path(dxf_path)
    doc = ezdxf.readfile(str(dxf_path))
    msp = doc.modelspace()

    # Ensure LIGHT_LAYOUT layer exists (cyan, so it stands out)
    if LAYOUT_LAYER not in doc.layers:
        doc.layers.add(LAYOUT_LAYER, color=4)   # ezdxf colour index 4 = cyan

    for room, opt in zip(rooms, results):
        sim = opt.final_result
        _draw_luminaires(msp, opt, room)
        _draw_room_summary(msp, room, opt)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(str(output_path))
    return output_path


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _draw_luminaires(msp, opt: OptimizationResult, room: Room) -> None:
    """Draw circle + cross for every luminaire."""
    for idx, lum in enumerate(opt.final_result.luminaires):
        cx, cy = lum.x, lum.y

        # Circle (fixture body)
        msp.add_circle(
            center=(cx, cy, 0),
            radius=_CIRCLE_RADIUS_M,
            dxfattribs={"layer": LAYOUT_LAYER},
        )

        # Cross arms
        msp.add_line(
            start=(cx - _CROSS_HALF, cy, 0),
            end=(cx + _CROSS_HALF, cy, 0),
            dxfattribs={"layer": LAYOUT_LAYER},
        )
        msp.add_line(
            start=(cx, cy - _CROSS_HALF, 0),
            end=(cx, cy + _CROSS_HALF, 0),
            dxfattribs={"layer": LAYOUT_LAYER},
        )


def _draw_room_summary(msp, room: Room, opt: OptimizationResult) -> None:
    """Write a summary text block near the room centroid."""
    sim = opt.final_result
    min_x, min_y, max_x, max_y = bounding_box(room.polygon)
    cx = (min_x + max_x) / 2
    cy = (min_y + max_y) / 2

    status = "PASS" if sim.meets_target else "FAIL"
    lines = [
        f"[{room.name}]",
        f"灯具: {opt.nx}列×{opt.ny}行={opt.total_luminaires}盏",
        f"均值: {sim.avg_lux:.0f} lux  目标: {room.target_lux:.0f} lux",
        f"均匀度: {sim.uniformity:.3f}  [{status}]",
    ]

    # Stack lines upward from the centroid
    line_gap = _TEXT_HEIGHT * 1.6
    for i, line in enumerate(lines):
        msp.add_text(
            line,
            dxfattribs={
                "layer": LAYOUT_LAYER,
                "height": _TEXT_HEIGHT,
                "insert": (cx, cy + i * line_gap, 0),
            },
        )
