# LightingAgent

AI-driven illuminance calculation and lighting layout design system.

Input a CAD drawing (DWG/DXF) + IES photometric files + illuminance requirements → output an optimized fixture layout, simulation report, and annotated CAD drawing.

---

## Before You Start — Manual Step Required

**DWG file support requires ODA File Converter**, which must be installed manually (it is a GUI application and cannot be installed via Homebrew):

1. Download from: https://www.opendesign.com/guestfiles/oda_file_converter
2. Install to `/Applications/ODAFileConverter.app`
3. Then run `./install.sh`

> If you only use DXF files (not DWG), you can skip this step.

---

## Requirements

- macOS (Apple Silicon or Intel)
- Python 3.11+
- Homebrew
- ODA File Converter (for DWG input — see above)

## Installation

```bash
git clone https://github.com/JimmyZhaoZM/lighting-agent
cd lighting-agent
./install.sh
```

`install.sh` will automatically install:
- **Radiance** (`brew install radiance`) — oconv, rtrace, rpict, falsecolor, ies2rad
- **Python packages** — ezdxf, numpy, scipy, reportlab, fastmcp, click

It will also verify that ODA File Converter is present and warn if not found.

## Quick Start

```bash
# CLI — DWG input
lighting-agent run --cad plan.dwg --ies ./ies/ --output ./output/

# CLI — DXF input
lighting-agent run --cad plan.dxf --ies ./ies/ --output ./output/

# MCP Server (for Claude Code / Cursor)
python -m mcp_server.server
```

## MCP Server Setup (Claude Code)

Add to `.mcp.json` in your project:

```json
{
  "mcpServers": {
    "lighting-agent": {
      "command": "python",
      "args": ["-m", "mcp_server.server"],
      "cwd": "/path/to/lighting-agent"
    }
  }
}
```

## CAD Drawing Convention

Draw closed polylines on layer `LIGHT_ZONE*` to define calculation zones.
Add a TEXT entity inside each zone: `height=9;target=150;mount=9`

See [`docs/cad-layer-convention.md`](docs/cad-layer-convention.md) for full details.

## DWG Converter Priority

| Converter | How to install | Priority |
|-----------|---------------|----------|
| ODA File Converter | Manual download (link above) | ✅ Primary |
| LibreDWG (`dwg2dxf`) | `brew install libredwg` | Fallback |

ODA is preferred because it supports all modern AutoCAD versions. LibreDWG supports up to DWG 2018 and is used as a fallback if ODA is not installed.

## Project Structure

```
lighting_agent/
├── cad/          # DWG/DXF parsing and writing
├── radiance/     # Radiance model building and simulation
├── ies/          # IES file loading and conversion
├── optimizer/    # Fixture layout optimization
└── reporter/     # PDF report and falsecolor image generation
mcp_server/       # MCP Server for AI agent tool calls
cli/              # Command-line interface
docs/
├── cad-layer-convention.md   # How to draw LIGHT_ZONE layers in CAD
└── checkpoints/              # Auto-generated run logs (phase1_YYYYMMDD_HHMMSS.json, last 10 kept)
```

## License

MIT
