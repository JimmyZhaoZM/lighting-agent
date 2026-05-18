"""Generate a PDF lighting design report using reportlab.

One report covers all rooms in a project.  Each room section contains:
- Design parameters (area, target, mount height, luminaire count)
- Photometric results table (avg / min / max lux, uniformity, compliance)
- Embedded false-colour heatmap PNG
- Luminaire coordinate table (first 50 rows; note if truncated)
"""
from __future__ import annotations

import math
from datetime import date
from pathlib import Path

from lighting_agent.cad.geometry import polygon_area
from lighting_agent.optimizer.optimizer import OptimizationResult
from lighting_agent.schemas import Room

# ---------------------------------------------------------------------------
# CJK font registration
# ---------------------------------------------------------------------------

def _register_cjk_fonts() -> tuple[str, str]:
    """Register CJK-compatible fonts with reportlab.

    Returns (regular_name, bold_name).  Falls back to Helvetica if no CJK
    font is found (Chinese will appear as boxes).
    """
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    # (font_name, file_path, is_ttc)
    candidates: list[tuple[str, str, str, str]] = [
        # macOS system fonts
        ("CJKRegular", "/System/Library/Fonts/STHeiti Light.ttc",
         "CJKBold",   "/System/Library/Fonts/STHeiti Medium.ttc"),
    ]
    fallback_singles = [
        ("CJKRegular", "/Library/Fonts/Arial Unicode.ttf"),
        ("CJKRegular", "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
    ]

    # Try paired regular+bold first
    for reg_name, reg_path, bold_name, bold_path in candidates:
        try:
            pdfmetrics.registerFont(TTFont(reg_name, reg_path, subfontIndex=0))
            pdfmetrics.registerFont(TTFont(bold_name, bold_path, subfontIndex=0))
            return reg_name, bold_name
        except Exception:
            continue

    # Single-file fallback (no bold variant)
    for name, path in fallback_singles:
        if Path(path).exists():
            try:
                pdfmetrics.registerFont(TTFont(name, path))
                return name, name
            except Exception:
                continue

    return "Helvetica", "Helvetica-Bold"


_CJK_REG, _CJK_BOLD = _register_cjk_fonts()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_report(
    rooms: list[Room],
    results: list[OptimizationResult],
    heatmap_paths: list[Path],
    output_path: Path,
    *,
    project_name: str = "照度计算报告",
) -> Path:
    """Write a PDF report to *output_path*.

    Args:
        rooms:          Room definitions (same order as results).
        results:        OptimizationResult per room (from optimizer.optimize).
        heatmap_paths:  False-colour PNG per room (same order).
        output_path:    Destination .pdf file.
        project_name:   Title shown on the cover page.

    Returns:
        output_path (for chaining).
    """
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
    )

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    W, H = A4
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=2 * cm, bottomMargin=2 * cm,
    )

    styles = getSampleStyleSheet()
    style_title = ParagraphStyle(
        "ReportTitle", parent=styles["Title"], fontSize=18, spaceAfter=6,
        fontName=_CJK_BOLD,
    )
    style_h2 = ParagraphStyle(
        "RoomHeading", parent=styles["Heading2"], fontSize=13, spaceAfter=4,
        textColor=colors.HexColor("#1a5276"), fontName=_CJK_BOLD,
    )
    style_normal = ParagraphStyle(
        "CJKNormal", parent=styles["Normal"], fontName=_CJK_REG,
    )
    style_small = ParagraphStyle(
        "Small", parent=styles["Normal"], fontSize=8, leading=11,
        fontName=_CJK_REG,
    )

    story = []

    # ── Cover ─────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 2 * cm))
    story.append(Paragraph(project_name, style_title))
    story.append(Paragraph(
        f"生成日期：{date.today().strftime('%Y-%m-%d')}　　"
        f"房间数量：{len(rooms)} 个",
        style_normal,
    ))
    story.append(Spacer(1, 0.8 * cm))

    # ── Per-room sections ─────────────────────────────────────────────────────
    for room, opt, heatmap in zip(rooms, results, heatmap_paths):
        sim = opt.final_result
        area = polygon_area(room.polygon)

        story.append(Paragraph(f"计算区域：{room.name}", style_h2))

        # Design parameters table
        params_data = [
            ["参数", "数值"],
            ["计算面积", f"{area:.1f} m²"],
            ["层高", f"{room.height:.1f} m"],
            ["安装高度", f"{room.mount_height:.1f} m"],
            ["照度要求", f"{room.target_lux:.0f} lux"],
            ["灯具光通量", f"{opt.lumens_per_lamp:,.0f} lm"],
            ["流明法预估数量", f"{opt.n_est} 盏"],
            ["优化迭代次数", f"{opt.iterations_used} 次"],
            ["最终灯具布置", f"{opt.nx} 列 × {opt.ny} 行 = {opt.total_luminaires} 盏"],
        ]
        story.append(_make_table(params_data, col_widths=[6 * cm, 10 * cm]))
        story.append(Spacer(1, 0.4 * cm))

        # Photometric results table
        status_text = "✓ 合规" if sim.meets_target else "✗ 不合规"
        status_color = colors.HexColor("#1e8449") if sim.meets_target else colors.red
        results_data = [
            ["指标", "数值", "要求"],
            ["平均照度 (lux)", f"{sim.avg_lux:.1f}", f"≥ {room.target_lux:.0f}"],
            ["最小照度 (lux)", f"{sim.min_lux:.1f}", "—"],
            ["最大照度 (lux)", f"{sim.max_lux:.1f}", "—"],
            ["照度均匀度 U₀", f"{sim.uniformity:.3f}", "≥ 0.40"],
            ["合规状态", status_text, ""],
        ]
        tbl = _make_table(results_data, col_widths=[5 * cm, 5 * cm, 6 * cm])
        # Colour the compliance row
        tbl._argW  # trigger internal layout so we can add style
        tbl.setStyle(TableStyle([
            ("TEXTCOLOR", (1, 5), (1, 5), status_color),
            ("FONTNAME", (1, 5), (1, 5), _CJK_BOLD),
        ]))
        story.append(tbl)
        story.append(Spacer(1, 0.4 * cm))

        # Heatmap image
        if Path(heatmap).exists():
            available_width = W - 4 * cm
            img = Image(str(heatmap), width=available_width, height=available_width * 0.55)
            story.append(img)
            story.append(Paragraph(
                f"图：{room.name} 照度分布（网格间距 {sim.grid_resolution} m）",
                style_small,
            ))
        story.append(Spacer(1, 0.5 * cm))

        # Luminaire coordinate table (first 50)
        MAX_ROWS = 50
        lums = sim.luminaires
        lum_data = [["序号", "X (m)", "Y (m)", "Z (m)"]]
        for i, l in enumerate(lums[:MAX_ROWS]):
            lum_data.append([str(i + 1), f"{l.x:.2f}", f"{l.y:.2f}", f"{l.z:.2f}"])
        story.append(Paragraph(
            f"灯具坐标（共 {len(lums)} 盏"
            + (f"，仅显示前 {MAX_ROWS} 盏" if len(lums) > MAX_ROWS else "") + "）",
            style_normal,
        ))
        story.append(_make_table(
            lum_data,
            col_widths=[2.5 * cm, 4 * cm, 4 * cm, 4 * cm],
            header_bg=colors.HexColor("#d6eaf8"),
        ))
        story.append(Spacer(1, 1 * cm))

    doc.build(story)
    return output_path


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _make_table(
    data: list[list],
    col_widths: list[float] | None = None,
    header_bg=None,
) -> "Table":
    from reportlab.lib import colors
    from reportlab.platypus import Table, TableStyle

    if header_bg is None:
        header_bg = colors.HexColor("#2e86c1")

    tbl = Table(data, colWidths=col_widths, repeatRows=1)
    style = TableStyle([
        # Header row
        ("BACKGROUND", (0, 0), (-1, 0), header_bg),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), _CJK_BOLD),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        # Body rows
        ("FONTNAME", (0, 1), (-1, -1), _CJK_REG),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#eaf4fb")]),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        # Grid
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#aab7b8")),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
    ])
    tbl.setStyle(style)
    return tbl
