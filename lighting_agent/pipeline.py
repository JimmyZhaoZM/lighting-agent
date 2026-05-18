"""End-to-end lighting design pipeline.

Orchestrates all phases in sequence:
  1. DWG/DXF → list[Room]          (cad/parser)
  2. Optimise each room             (optimizer/optimizer)
  3. Render false-colour heatmaps   (reporter/falsecolor)
  4. Generate PDF report            (reporter/pdf_report)
  5. Write layout back to DXF       (cad/writer)

Returns a PipelineResult dataclass with paths to all output artefacts.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from lighting_agent.cad.dwg_converter import ensure_dxf
from lighting_agent.cad.parser import parse_rooms
from lighting_agent.cad.writer import write_layout
from lighting_agent.optimizer.optimizer import OptimizationResult, optimize
from lighting_agent.reporter.falsecolor import render_heatmap
from lighting_agent.reporter.pdf_report import generate_report
from lighting_agent.schemas import Room
from lighting_agent.utils.checkpoint import save_phase4_checkpoint

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """All artefacts produced by run_pipeline()."""
    rooms: list[Room]
    optimization_results: list[OptimizationResult]
    heatmap_paths: list[Path]
    pdf_path: Path
    layout_dxf_path: Path
    output_dir: Path


def run_pipeline(
    cad_path: str | Path,
    ies_path: str | Path,
    output_dir: str | Path,
    *,
    project_name: str = "照度计算报告",
    max_iterations: int = 10,
    min_uniformity: float = 0.4,
    grid_resolution: float = 0.5,
    rtrace_args: list[str] | None = None,
) -> PipelineResult:
    """Run the full lighting design pipeline from CAD + IES to reports.

    Args:
        cad_path:        Path to .dwg or .dxf input file.
        ies_path:        Path to the IES file for luminaires.
        output_dir:      Directory for all output files (created if needed).
        project_name:    Title used on the PDF cover page.
        max_iterations:  Max optimisation iterations per room (default 10).
        min_uniformity:  Required Emin/Eave ratio (default 0.4).
        grid_resolution: Sensor grid spacing in metres (default 0.5).
        rtrace_args:     Override rtrace quality params (None = high quality).

    Returns:
        PipelineResult with paths to all generated files.
    """
    cad_path = Path(cad_path)
    ies_path = str(ies_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # ── Step 1: CAD → rooms ────────────────────────────────────────────────
    logger.info("Step 1: Parsing CAD file: %s", cad_path)
    dxf_path, _was_converted = ensure_dxf(cad_path)
    rooms = parse_rooms(str(dxf_path))
    logger.info("Found %d room(s): %s", len(rooms), [r.name for r in rooms])

    if not rooms:
        raise ValueError(f"No LIGHT_ZONE rooms found in {cad_path}")

    # ── Step 2: Optimise each room ─────────────────────────────────────────
    logger.info("Step 2: Optimising luminaire layout (%d rooms)…", len(rooms))
    opt_results: list[OptimizationResult] = []
    for room in rooms:
        logger.info("  Optimising room: %s", room.name)
        opt = optimize(
            room=room,
            ies_path=ies_path,
            max_iterations=max_iterations,
            min_uniformity=min_uniformity,
            grid_resolution=grid_resolution,
            rtrace_args=rtrace_args,
        )
        opt_results.append(opt)
        logger.info(
            "  → %s: %d luminaires, avg %.0f lux, U₀=%.3f, converged=%s",
            room.name, opt.total_luminaires,
            opt.final_result.avg_lux, opt.final_result.uniformity,
            opt.converged,
        )

    # Save phase-4 checkpoint (optimisation results)
    save_phase4_checkpoint([
        {
            "room": r.name,
            "nx": o.nx, "ny": o.ny,
            "total": o.total_luminaires,
            "avg_lux": round(o.final_result.avg_lux, 1),
            "uniformity": round(o.final_result.uniformity, 3),
            "converged": o.converged,
        }
        for r, o in zip(rooms, opt_results)
    ])

    # ── Step 3: Heatmaps ───────────────────────────────────────────────────
    logger.info("Step 3: Rendering heatmaps…")
    heatmap_dir = output_dir / "heatmaps"
    heatmap_paths: list[Path] = []
    for room, opt in zip(rooms, opt_results):
        safe_name = room.name.replace("/", "_").replace(" ", "_")
        png_path = heatmap_dir / f"{safe_name}_heatmap.png"
        render_heatmap(opt.final_result, png_path)
        heatmap_paths.append(png_path)
        logger.info("  Saved heatmap: %s", png_path)

    # ── Step 4: PDF report ─────────────────────────────────────────────────
    logger.info("Step 4: Generating PDF report…")
    pdf_path = output_dir / "lighting_report.pdf"
    generate_report(
        rooms=rooms,
        results=opt_results,
        heatmap_paths=heatmap_paths,
        output_path=pdf_path,
        project_name=project_name,
    )
    logger.info("  Saved report: %s", pdf_path)

    # ── Step 5: Write layout to DXF ────────────────────────────────────────
    logger.info("Step 5: Writing luminaire layout to DXF…")
    layout_dxf_path = output_dir / (cad_path.stem + "_LIGHT_LAYOUT.dxf")
    write_layout(
        dxf_path=dxf_path,
        rooms=rooms,
        results=opt_results,
        output_path=layout_dxf_path,
    )
    logger.info("  Saved layout DXF: %s", layout_dxf_path)

    logger.info("Pipeline complete. Output directory: %s", output_dir)
    return PipelineResult(
        rooms=rooms,
        optimization_results=opt_results,
        heatmap_paths=heatmap_paths,
        pdf_path=pdf_path,
        layout_dxf_path=layout_dxf_path,
        output_dir=output_dir,
    )
