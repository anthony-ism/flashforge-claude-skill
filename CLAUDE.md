# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Claude Code skill called `flashforge` that converts 2D images (PNG, JPG, SVG, clipart, icons, logos) into 3D printable STL files optimized for FDM printing on a FlashForge Adventurer 5M printer.

## Target Architecture

```
flashforge/
├── SKILL.md                    # Main skill definition (YAML frontmatter + markdown body)
├── scripts/
│   ├── heightmap_to_stl.py     # Brightness-to-height extrusion (photos, lithophanes)
│   ├── contour_to_stl.py       # Edge detection + extrusion (icons, logos)
│   ├── svg_to_stl.py           # SVG path extrusion (vector graphics)
│   └── utils.py                # Image preprocessing, STL validation
├── references/
│   └── printing-guidelines.md  # FlashForge Adventurer 5M settings
└── assets/
    └── sample-outputs/         # Example STL outputs
```

## Development Setup (uv)

This project uses `uv` for dependency and virtual environment management.

```bash
# Install dependencies and create venv
uv sync

# Run Python scripts with dependencies
uv run python flashforge/scripts/utils.py

# Run MCP servers
uv run flashforge-printer-mcp
uv run flashforge-convert-mcp
uv run flashforge-generate-mcp

# Add a new dependency
uv add <package-name>
```

**Important:** Always use `uv run` to execute Python scripts to ensure the correct virtual environment and dependencies are used.

## Python Dependencies

Managed via `pyproject.toml`:
```
numpy
numpy-stl
Pillow
opencv-python
trimesh
shapely
svgpathtools
mcp
requests
mapbox-earcut
```

## Conversion Methods

| Method | Best For | Key Libraries |
|--------|----------|---------------|
| Heightmap extrusion | Photos, grayscale art, lithophanes | numpy, numpy-stl, Pillow |
| Contour extrusion | Icons, logos, clipart with clear edges | opencv-python, trimesh, shapely |
| SVG path extrusion | Vector graphics, clean line art | svgpathtools, trimesh (or OpenSCAD CLI) |

## FlashForge Adventurer 5M Constraints

- Build volume: 220 x 220 x 220 mm
- Default scale should fit within these bounds
- Add 2mm base for bed adhesion
- Validate mesh is watertight before export

## SKILL.md Frontmatter Format

```yaml
---
name: flashforge
description: Convert 2D images (PNG, JPG, SVG, clipart, icons, logos) into 3D printable STL files for FDM printing...
---
```

## Script Requirements

Each conversion script must:
1. Validate input file exists and is a valid image
2. Check output mesh is manifold (printable)
3. Verify dimensions fit printer bounds (220mm max)
4. Accept parameters: max_height, base_height, scale, threshold (where applicable)
