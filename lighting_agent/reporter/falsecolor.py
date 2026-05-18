"""Generate a false-colour illuminance heatmap PNG from a SimulationResult.

Uses matplotlib — no Radiance install required at report time.
Overlays room luminaire positions and a target-lux contour.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from lighting_agent.schemas import SimulationResult


def render_heatmap(
    result: SimulationResult,
    output_path: Path,
    *,
    colormap: str = "YlOrRd",
    dpi: int = 150,
    figsize: tuple[float, float] | None = None,
) -> Path:
    """Render the illuminance grid as a false-colour PNG.

    Args:
        result:       SimulationResult with illuminance_grid populated.
        output_path:  Destination .png file (parent directory must exist).
        colormap:     Matplotlib colormap name (default "YlOrRd").
        dpi:          Output resolution (default 150).
        figsize:      Figure size in inches. Auto-sized from room aspect if None.

    Returns:
        output_path (for chaining).
    """
    import matplotlib
    import matplotlib.pyplot as plt
    from matplotlib.colors import Normalize
    from matplotlib.cm import ScalarMappable

    # Use a CJK-compatible font when available (macOS: PingFang SC / STHeiti)
    # PingFang SC (macOS) covers CJK + Latin + subscripts; fall back to others
    _cjk_fonts = ["PingFang SC", "Hiragino Sans GB", "WenQuanYi Micro Hei",
                  "STHeiti", "DejaVu Sans"]
    matplotlib.rcParams["font.sans-serif"] = _cjk_fonts
    matplotlib.rcParams["axes.unicode_minus"] = False

    grid = np.array(result.illuminance_grid, dtype=float)
    if grid.ndim == 1:
        grid = grid.reshape(1, -1)
    ny, nx = grid.shape
    res = result.grid_resolution

    # Real-world extent from luminaire envelope + half-cell padding
    lums = result.luminaires
    if lums:
        x0 = min(l.x for l in lums) - res / 2
        x1 = max(l.x for l in lums) + res / 2
        y0 = min(l.y for l in lums) - res / 2
        y1 = max(l.y for l in lums) + res / 2
    else:
        x0, y0, x1, y1 = 0.0, 0.0, nx * res, ny * res

    width_m = x1 - x0
    height_m = max(y1 - y0, 1e-6)
    if figsize is None:
        aspect = width_m / height_m
        fig_w = max(6.0, min(14.0, aspect * 7.0))
        fig_h = fig_w / aspect + 1.5
        figsize = (fig_w, max(4.0, fig_h))

    fig, ax = plt.subplots(figsize=figsize)

    vmin = max(0.0, result.min_lux * 0.8)
    vmax = max(result.max_lux * 1.05, vmin + 1.0)
    ax.imshow(
        grid,
        origin="lower",
        extent=[x0, x1, y0, y1],
        cmap=colormap,
        vmin=vmin,
        vmax=vmax,
        aspect="equal",
        interpolation="bilinear",
    )

    cbar = fig.colorbar(
        ScalarMappable(norm=Normalize(vmin=vmin, vmax=vmax), cmap=colormap),
        ax=ax, fraction=0.03, pad=0.02,
    )
    cbar.set_label("Illuminance (lux)", fontsize=9)

    # Dashed contour at target lux (requires at least 2×2 grid)
    if vmin < result.target_lux < vmax and ny >= 2 and nx >= 2:
        ax.contour(
            grid, levels=[result.target_lux],
            colors=["white"], linewidths=[1.0], linestyles=["--"],
            extent=[x0, x1, y0, y1], origin="lower",
        )

    # Luminaire markers
    if lums:
        ax.scatter(
            [l.x for l in lums], [l.y for l in lums],
            marker="+", s=60, linewidths=1.2, color="white",
            zorder=5, label=f"Luminaires ({len(lums)})",
        )
        ax.legend(fontsize=8, loc="upper right", framealpha=0.6)

    status = "PASS" if result.meets_target else "FAIL"
    ax.set_title(
        f"Illuminance — {result.room_name}\n"
        f"Avg {result.avg_lux:.0f} lux  |  Min {result.min_lux:.0f} lux  |  "
        f"U0 {result.uniformity:.3f}  |  Target {result.target_lux:.0f} lux  [{status}]",
        fontsize=10, pad=8,
    )
    ax.set_xlabel("X (m)", fontsize=9)
    ax.set_ylabel("Y (m)", fontsize=9)
    ax.tick_params(labelsize=8)

    fig.tight_layout()
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return output_path
