# FlashForge MCP Servers

MCP (Model Context Protocol) servers for 3D printing with FlashForge printers. Control your printer, convert images to 3D models, and generate AI-powered figurines - all from Claude.

## What's Included

| Server | Purpose | Tools |
|--------|---------|-------|
| **flashforge-printer** | Printer discovery & control | 6 tools |
| **flashforge-convert** | 2D to 3D conversion | 5 tools |
| **flashforge-generate** | AI 3D generation | 2 tools |

## Quick Start

### 1. Install

```bash
# Clone the repository
git clone https://github.com/anthony-ism/flashforge-claude-skill.git
cd flashforge-claude-skill

# Install with uv (recommended)
uv pip install -e .

# Or with pip
pip install -e .
```

### 2. Configure Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "flashforge-printer": {
      "command": "uv",
      "args": ["run", "flashforge-printer-mcp"]
    },
    "flashforge-convert": {
      "command": "uv",
      "args": ["run", "flashforge-convert-mcp"]
    },
    "flashforge-generate": {
      "command": "uv",
      "args": ["run", "flashforge-generate-mcp"],
      "env": {
        "TRIPO_API_KEY": "your-api-key-here"
      }
    }
  }
}
```

### 3. Restart Claude Desktop

The servers will appear in Claude's tool list.

---

## Server 1: flashforge-printer

Control and monitor FlashForge 3D printers on your local network.

### Tools

| Tool | Description |
|------|-------------|
| `watch_printer` | **Smart dashboard** - auto-discover, status, and camera (recommended!) |
| `discover_printers` | Find FlashForge printers via UDP broadcast |
| `get_printer_info` | Get model, firmware, serial number |
| `get_printer_status` | Check temperatures, progress, state |
| `send_gcode_file` | Upload G-code and optionally start print |
| `get_camera_url` | Get live camera stream URL |

### Example Prompts

- **"Watch my printer"** - Auto-discovers and shows full dashboard with camera
- **"How's my print going?"** - Check progress and watch the camera
- "Find FlashForge printers on my network"
- "What's the status of my printer at 192.168.1.100?"
- "Upload output.gcode to my printer"
- "Send model.gcode to my printer and start printing"
- "Watch my printer and open the camera" - Opens camera feed in browser

### Requirements

- FlashForge Adventurer 5M, 5M Pro, or compatible
- Printer and computer on same network
- Printer's LAN mode enabled

---

## Server 2: flashforge-convert

Convert 2D images to 3D-printable STL files.

### Tools

| Tool | Best For | Description |
|------|----------|-------------|
| `image_to_stl_contour` | Icons, logos | Edge detection + extrusion |
| `image_to_stl_heightmap` | Photos, art | Brightness-to-height mapping |
| `image_to_lithophane` | Backlit photos | Thickness-based light transmission |
| `image_to_svg` | Vector output | Clean SVG for slicers |
| `validate_stl` | Quality check | Verify printability |

### Example Prompts

- "Convert this logo to a 3D print, 50mm wide with a 2mm base"
- "Make a relief model from this grayscale image"
- "Create a lithophane from this family photo, 100mm wide"
- "Convert this icon to SVG for OrcaSlicer"
- "Check if this STL file is printable"

### Conversion Decision Guide

| Your Image | Use This Tool |
|------------|---------------|
| Icon with solid colors | `image_to_stl_contour` |
| Photo or detailed art | `image_to_stl_heightmap` |
| Photo for backlight | `image_to_lithophane` |
| Need SVG for slicer | `image_to_svg` |

---

## Server 3: flashforge-generate

AI-powered 3D model generation from single images using [Tripo AI](https://tripo3d.ai).

### Tools

| Tool | Description |
|------|-------------|
| `generate_3d_from_image` | Create true 3D model from photo |
| `get_generation_balance` | Check remaining API credits |

### Example Prompts

- "Generate a 3D figurine from this character image, 100mm tall"
- "Create a 3D model from this product photo with a base"
- "How many generation credits do I have left?"

### Setup

1. Sign up at [tripo3d.ai](https://tripo3d.ai)
2. Get your API key from the dashboard
3. Add to Claude Desktop config:
   ```json
   "env": {
     "TRIPO_API_KEY": "your-key-here"
   }
   ```

### When to Use Generate vs Convert

| Use Generate | Use Convert |
|--------------|-------------|
| 3D characters/figurines | Flat icons/logos |
| Products with depth | 2D artwork |
| Complex 3D shapes | Simple extrusions |

Generate creates true 3D geometry. Convert extrudes 2D shapes.

---

## Supported Printers

Tested with:
- FlashForge Adventurer 5M
- FlashForge Adventurer 5M Pro

Should work with other FlashForge printers that support:
- UDP discovery on 225.0.0.9:19000
- TCP control on port 8899

---

## Build Volume

FlashForge Adventurer 5M:
- X: 220mm
- Y: 220mm
- Z: 220mm

All conversion tools automatically scale output to fit.

---

## Recommended Slicer

**OrcaSlicer** - Works great on macOS (including Apple Silicon) with FlashForge printers.

---

## Development

### Project Structure

```
flashforge-mcp/
├── src/
│   ├── flashforge_printer_mcp/   # Printer control server
│   ├── flashforge_convert_mcp/   # 2D-to-3D conversion server
│   └── flashforge_generate_mcp/  # AI generation server
├── flashforge/                   # Original CLI tools
├── input/                        # Sample input images
├── output/                       # Generated output files
└── docs/                         # Additional documentation
```

### Running Servers Locally

```bash
# Test printer server
uv run python -m flashforge_printer_mcp

# Test convert server
uv run python -m flashforge_convert_mcp

# Test generate server (requires TRIPO_API_KEY)
TRIPO_API_KEY=xxx uv run python -m flashforge_generate_mcp
```

### Dependencies

- Python 3.10+
- mcp (Model Context Protocol SDK)
- opencv-python (image processing)
- trimesh (3D mesh operations)
- numpy, pillow, shapely (utilities)
- requests (API calls)

---

## License

MIT

---

## Links

- [MCP Documentation](https://modelcontextprotocol.io)
- [FlashForge](https://www.flashforge.com)
- [OrcaSlicer](https://github.com/SoftFever/OrcaSlicer)
- [Tripo AI](https://tripo3d.ai)
