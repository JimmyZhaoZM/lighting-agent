# LightingAgent

AI-driven illuminance calculation and lighting layout design system.

Input a CAD drawing (DXF) + IES photometric files + illuminance requirements → output an optimized fixture layout, simulation report, and annotated CAD drawing.

## Requirements

- macOS (Apple Silicon or Intel)
- Python 3.11+
- Homebrew

## Installation

```bash
git clone https://github.com/<your-username>/lighting-agent
cd lighting-agent
./install.sh
```

## Quick Start

```bash
# CLI
lighting-agent run --dxf plan.dxf --ies ./ies/ --output ./output/

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

## CAD Layer Convention

- `LIGHT_ZONE` — closed polylines defining calculation zones
- Layer properties comment format: `height=5.5;target=300;mount=4.8`

See `docs/cad-layer-convention.md` for full details.

## Project Structure

```
lighting_agent/
├── cad/          # DXF parsing and writing
├── radiance/     # Radiance model building and simulation
├── ies/          # IES file loading and conversion
├── optimizer/    # Fixture layout optimization
└── reporter/     # PDF report and falsecolor image generation
mcp_server/       # MCP Server for AI agent tool calls
cli/              # Command-line interface
```

## License

MIT
