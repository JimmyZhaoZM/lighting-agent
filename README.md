# LightingAgent

AI-driven illuminance calculation and lighting layout design system.

Input a CAD drawing (DWG/DXF) + IES photometric files + illuminance requirements → output an optimized fixture layout, simulation report, and annotated CAD drawing.

---

## Before You Start — Manual Steps Required

Two tools cannot be installed automatically and must be set up manually first:

### 1. Radiance (required for simulation)

The Homebrew formula for Radiance has been removed. Install from the official GitHub releases:

1. Go to: https://github.com/LBNL-ETA/Radiance/releases
2. Download the latest macOS `.pkg` for your chip:
   - **Apple Silicon (M1/M2/M3/M4)** → `Radiance_*_OSX_arm64.pkg`
   - **Intel Mac** → `Radiance_*_OSX.pkg`
3. Run the installer
   > **macOS security warning:** macOS may block the installer with "cannot be opened because it is from an unidentified developer." To bypass this:
   > 1. Double-click the `.pkg` — it will be blocked
   > 2. Open **System Settings → Privacy & Security**
   > 3. Scroll down and click **"Open Anyway"** next to the Radiance entry
   > 4. Confirm in the dialog that appears
4. Add Radiance to your PATH and set the library path (both are required):
   ```bash
   echo 'export PATH="/usr/local/radiance/bin:$PATH"' >> ~/.zshrc
   echo 'export RAYPATH="/usr/local/radiance/lib"' >> ~/.zshrc
   source ~/.zshrc
   ```
   > **Note:** `RAYPATH` is needed so Radiance tools can find their `.cal` library files (e.g. `rayinit.cal`). Without it, `rtrace` will fail at runtime even if `oconv` works fine.
5. Verify: `which oconv` should print a path

### 2. ODA File Converter (required for DWG input only)

1. Download from: https://www.opendesign.com/guestfiles/oda_file_converter
2. Install to `/Applications/ODAFileConverter.app`

> If you only use DXF files (not DWG), you can skip step 2.

---

## Requirements

- macOS (Apple Silicon or Intel)
- Python 3.11+
- Homebrew
- **Radiance** — manual install required (see above)
- ODA File Converter — for DWG input (see above)

## Installation

```bash
git clone https://github.com/JimmyZhaoZM/lighting-agent
cd lighting-agent
./install.sh
```

`install.sh` will automatically install:
- **Python packages** — ezdxf, numpy, scipy, reportlab, fastmcp, click

It will also verify that Radiance and ODA File Converter are present and warn if not found.

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
