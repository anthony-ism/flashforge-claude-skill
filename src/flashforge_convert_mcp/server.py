"""
FlashForge Convert MCP Server

Convert 2D images to 3D-printable STL files.

Tools:
- image_to_stl_contour: Edge detection and extrusion for icons/logos
- image_to_stl_heightmap: Brightness-to-height for relief models
- image_to_lithophane: Create backlit photo displays
- image_to_svg: Vector conversion for slicers
- validate_stl: Check STL printability
- fix_model: Scale, add base, remove floating pieces from 3D models
"""

import os
from pathlib import Path
from mcp.server import Server
from mcp.types import Tool, TextContent, Resource
from mcp.server.stdio import stdio_server

from . import converters

server = Server("flashforge-convert")

# Default output directory (relative to where the server is run from)
OUTPUT_DIR = Path.cwd() / "output"


def get_output_path(input_path: str, suffix: str = "", extension: str = ".stl") -> str:
    """Generate output path in the output directory based on input filename."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    input_name = Path(input_path).stem
    output_name = f"{input_name}{suffix}{extension}"
    return str(OUTPUT_DIR / output_name)


@server.list_tools()
async def list_tools():
    """List all available conversion tools."""
    return [
        Tool(
            name="image_to_stl_contour",
            description="""Convert a PNG/JPG image to STL using edge detection and extrusion.

Best for: icons, logos, clipart with clear edges and solid colors.

The image is converted to black/white, edges are detected, and the shapes
are extruded into 3D. Use 'invert' to swap which areas become solid.

Example: "Convert this Mario icon to a 3D keychain, 40mm wide with a 2mm base"
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "image_path": {
                        "type": "string",
                        "description": "Absolute path to input image (PNG, JPG, WebP)"
                    },
                    "output_path": {
                        "type": "string",
                        "description": "Output STL filename (optional, auto-generated in output folder if not provided)"
                    },
                    "height_mm": {
                        "type": "number",
                        "description": "Extrusion height in millimeters (default: 5)",
                        "default": 5,
                        "minimum": 0.5,
                        "maximum": 50
                    },
                    "scale_mm": {
                        "type": "number",
                        "description": "Target width in millimeters (default: auto-fit)",
                        "minimum": 10,
                        "maximum": 220
                    },
                    "threshold": {
                        "type": "integer",
                        "description": "Black/white cutoff 0-255, lower = more detail (default: 127)",
                        "default": 127,
                        "minimum": 0,
                        "maximum": 255
                    },
                    "invert": {
                        "type": "boolean",
                        "description": "Swap foreground/background - extrude dark areas instead of light",
                        "default": False
                    },
                    "base_mm": {
                        "type": "number",
                        "description": "Base plate thickness for bed adhesion (default: 0 = no base)",
                        "default": 0,
                        "minimum": 0,
                        "maximum": 10
                    }
                },
                "required": ["image_path"]
            }
        ),
        Tool(
            name="image_to_stl_heightmap",
            description="""Convert an image to STL using brightness-to-height mapping.

Best for: photos, grayscale art, relief models, terrain maps.

Brighter pixels become higher in the 3D model. The result is a relief
sculpture that captures the tonal variation of the original image.

Example: "Create a 3D relief from this mountain photo, 10mm max height"
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "image_path": {
                        "type": "string",
                        "description": "Absolute path to input image"
                    },
                    "output_path": {
                        "type": "string",
                        "description": "Output STL filename (optional, auto-generated in output folder if not provided)"
                    },
                    "max_height_mm": {
                        "type": "number",
                        "description": "Maximum relief height in mm (default: 10)",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 50
                    },
                    "base_mm": {
                        "type": "number",
                        "description": "Base plate thickness in mm (default: 2)",
                        "default": 2,
                        "minimum": 0,
                        "maximum": 20
                    },
                    "invert": {
                        "type": "boolean",
                        "description": "Invert heights - dark areas become higher",
                        "default": False
                    },
                    "smooth": {
                        "type": "integer",
                        "description": "Smoothing radius to reduce noise (default: 0)",
                        "default": 0,
                        "minimum": 0,
                        "maximum": 10
                    }
                },
                "required": ["image_path"]
            }
        ),
        Tool(
            name="image_to_lithophane",
            description="""Create a lithophane STL from a photo.

Best for: backlit photo displays, printed in white PLA.

A lithophane is a thin panel where image brightness is encoded as thickness.
When backlit, the image appears. Print vertically in white PLA for best results.

Example: "Make a lithophane from this family photo, 100mm wide"
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "image_path": {
                        "type": "string",
                        "description": "Absolute path to input photo"
                    },
                    "output_path": {
                        "type": "string",
                        "description": "Output STL filename (optional, auto-generated in output folder if not provided)"
                    },
                    "thickness_mm": {
                        "type": "number",
                        "description": "Maximum thickness in mm (default: 3)",
                        "default": 3,
                        "minimum": 2,
                        "maximum": 5
                    },
                    "width_mm": {
                        "type": "number",
                        "description": "Output width in mm (default: 100)",
                        "default": 100,
                        "minimum": 50,
                        "maximum": 200
                    },
                    "frame": {
                        "type": "string",
                        "description": "Frame style: 'none' or 'simple' (default: none)",
                        "enum": ["none", "simple"],
                        "default": "none"
                    }
                },
                "required": ["image_path"]
            }
        ),
        Tool(
            name="image_to_svg",
            description="""Convert a raster image to clean SVG vector format.

Best for: creating vector paths for slicer import (Orca, PrusaSlicer).

Traces the edges of the image and outputs clean vector paths. Useful when
your slicer has native SVG support and you want precise control.

Example: "Convert this logo to SVG for OrcaSlicer"
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "image_path": {
                        "type": "string",
                        "description": "Absolute path to input image"
                    },
                    "output_path": {
                        "type": "string",
                        "description": "Output SVG filename (optional, auto-generated in output folder if not provided)"
                    },
                    "smoothing": {
                        "type": "string",
                        "description": "Edge smoothing: none, low, medium, high (default: medium)",
                        "enum": ["none", "low", "medium", "high"],
                        "default": "medium"
                    },
                    "threshold": {
                        "type": "integer",
                        "description": "Black/white cutoff 0-255 (default: 127)",
                        "default": 127,
                        "minimum": 0,
                        "maximum": 255
                    },
                    "invert": {
                        "type": "boolean",
                        "description": "Invert colors",
                        "default": False
                    }
                },
                "required": ["image_path"]
            }
        ),
        Tool(
            name="validate_stl",
            description="""Check if an STL file is valid for 3D printing.

Analyzes the mesh for common issues:
- Watertightness (no holes in the mesh)
- Size within build volume (220x220x220mm for Adventurer 5M)
- Triangle and vertex count
- Estimated volume

Example: "Check if this STL is printable"
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "stl_path": {
                        "type": "string",
                        "description": "Absolute path to STL file to validate"
                    }
                },
                "required": ["stl_path"]
            }
        ),
        Tool(
            name="fix_model",
            description="""Fix and prepare a 3D model for printing.

Performs multiple fixes on STL/GLB/OBJ files:
- **Scale** to target height (default 80mm)
- **Remove floating pieces** that can't print
- **Add base plate** for bed adhesion
- **Repair mesh** using voxelization for clean, watertight output

Best for: AI-generated models (Tripo, etc), downloaded models with issues,
models that are too small or have disconnected parts.

Example: "Fix this model, scale to 100mm with a 3mm base"
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "input_path": {
                        "type": "string",
                        "description": "Absolute path to input 3D model (STL, GLB, OBJ)"
                    },
                    "output_path": {
                        "type": "string",
                        "description": "Output STL filename (optional, auto-generated in output folder if not provided)"
                    },
                    "target_height_mm": {
                        "type": "number",
                        "description": "Target height in millimeters (default: 80)",
                        "default": 80,
                        "minimum": 10,
                        "maximum": 220
                    },
                    "base_height_mm": {
                        "type": "number",
                        "description": "Base plate thickness in mm (default: 2, use 0 for no base)",
                        "default": 2,
                        "minimum": 0,
                        "maximum": 10
                    },
                    "base_padding_mm": {
                        "type": "number",
                        "description": "Extra padding around model for base in mm (default: 3)",
                        "default": 3,
                        "minimum": 0,
                        "maximum": 20
                    },
                    "remove_floating": {
                        "type": "boolean",
                        "description": "Remove disconnected floating pieces (default: true)",
                        "default": True
                    }
                },
                "required": ["input_path"]
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    """Handle tool calls."""

    if name == "image_to_stl_contour":
        try:
            output_path = arguments.get("output_path") or get_output_path(arguments["image_path"], "_contour")
            result = converters.image_to_stl_contour(
                image_path=arguments["image_path"],
                output_path=output_path,
                height_mm=arguments.get("height_mm", 5.0),
                scale_mm=arguments.get("scale_mm"),
                threshold=arguments.get("threshold", 127),
                invert=arguments.get("invert", False),
                base_mm=arguments.get("base_mm", 0)
            )
            return [TextContent(type="text", text=format_result("Contour Extrusion", result))]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {e}")]

    elif name == "image_to_stl_heightmap":
        try:
            output_path = arguments.get("output_path") or get_output_path(arguments["image_path"], "_heightmap")
            result = converters.image_to_stl_heightmap(
                image_path=arguments["image_path"],
                output_path=output_path,
                max_height_mm=arguments.get("max_height_mm", 10.0),
                base_mm=arguments.get("base_mm", 2.0),
                invert=arguments.get("invert", False),
                smooth=arguments.get("smooth", 0)
            )
            return [TextContent(type="text", text=format_result("Heightmap Relief", result))]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {e}")]

    elif name == "image_to_lithophane":
        try:
            output_path = arguments.get("output_path") or get_output_path(arguments["image_path"], "_lithophane")
            result = converters.image_to_lithophane(
                image_path=arguments["image_path"],
                output_path=output_path,
                thickness_mm=arguments.get("thickness_mm", 3.0),
                width_mm=arguments.get("width_mm", 100.0),
                frame=arguments.get("frame", "none")
            )
            return [TextContent(type="text", text=format_result("Lithophane", result))]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {e}")]

    elif name == "image_to_svg":
        try:
            output_path = arguments.get("output_path") or get_output_path(arguments["image_path"], "", ".svg")
            result = converters.image_to_svg(
                image_path=arguments["image_path"],
                output_path=output_path,
                smoothing=arguments.get("smoothing", "medium"),
                threshold=arguments.get("threshold", 127),
                invert=arguments.get("invert", False)
            )
            return [TextContent(type="text", text=format_svg_result(result))]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {e}")]

    elif name == "validate_stl":
        try:
            result = converters.validate_stl_file(arguments["stl_path"])
            return [TextContent(type="text", text=format_validation(arguments["stl_path"], result))]
        except Exception as e:
            return [TextContent(type="text", text=f"Error validating STL: {e}")]

    elif name == "fix_model":
        try:
            from flashforge.scripts.fix_model import fix_model
            output_path = arguments.get("output_path") or get_output_path(arguments["input_path"], "_fixed")
            result = fix_model(
                input_path=arguments["input_path"],
                output_path=output_path,
                target_height_mm=arguments.get("target_height_mm", 80.0),
                base_height_mm=arguments.get("base_height_mm", 2.0),
                base_padding_mm=arguments.get("base_padding_mm", 3.0),
                remove_floating=arguments.get("remove_floating", True),
            )
            return [TextContent(type="text", text=format_fix_result(result))]
        except Exception as e:
            return [TextContent(type="text", text=f"Error fixing model: {e}")]

    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


def format_result(conversion_type: str, result: dict) -> str:
    """Format conversion result for display."""
    dims = result.get("dimensions_mm", {})
    output = f"""**{conversion_type} Complete**

**Output:** {result['output_path']}
**File Size:** {result['file_size_bytes'] / 1024:.1f} KB
**Input Resolution:** {result.get('input_resolution', 'N/A')}

**Dimensions:**
- X: {dims.get('x', 0):.1f} mm
- Y: {dims.get('y', 0):.1f} mm
- Z: {dims.get('z', 0):.1f} mm

**Mesh Info:**
- Triangles: {result.get('triangle_count', 0):,}
- Vertices: {result.get('vertex_count', 0):,}
- Watertight: {'Yes' if result.get('is_watertight') else 'No'}
"""
    if result.get("issues"):
        output += f"\n**Warnings:**\n"
        for issue in result["issues"]:
            output += f"- {issue}\n"

    return output


def format_svg_result(result: dict) -> str:
    """Format SVG conversion result."""
    dims = result.get("svg_dimensions", {})
    return f"""**SVG Conversion Complete**

**Output:** {result['output_path']}
**File Size:** {result['file_size_bytes'] / 1024:.1f} KB
**Input Resolution:** {result.get('input_resolution', 'N/A')}
**Contours Converted:** {result.get('contours_converted', 0)}
**SVG Dimensions:** {dims.get('width', 0)} x {dims.get('height', 0)} pixels

The SVG can be imported directly into OrcaSlicer or PrusaSlicer.
"""


def format_validation(path: str, result: dict) -> str:
    """Format validation result."""
    dims = result.get("dimensions_mm", {})
    status = "**VALID**" if result.get("is_valid") else "**HAS ISSUES**"

    output = f"""**STL Validation: {status}**

**File:** {path}

**Dimensions:**
- X: {dims.get('x', 0):.1f} mm
- Y: {dims.get('y', 0):.1f} mm
- Z: {dims.get('z', 0):.1f} mm

**Mesh Info:**
- Triangles: {result.get('triangle_count', 0):,}
- Vertices: {result.get('vertex_count', 0):,}
- Watertight: {'Yes' if result.get('is_watertight') else 'No'}
"""
    if result.get("volume_mm3"):
        output += f"- Volume: {result['volume_mm3']:.1f} mm³\n"

    if result.get("issues"):
        output += f"\n**Issues Found:**\n"
        for issue in result["issues"]:
            output += f"- {issue}\n"
    else:
        output += "\n**No issues detected.** Ready to slice and print!"

    return output


def format_fix_result(result: dict) -> str:
    """Format model fix result for display."""
    orig = result.get("original_dims", [0, 0, 0])
    final = result.get("final_dims", [0, 0, 0])

    output = f"""**Model Fix Complete**

**Output:** {result.get('output_path', 'N/A')}

**Original Size:** {orig[0]:.1f} x {orig[1]:.1f} x {orig[2]:.1f} mm
**Final Size:** {final[0]:.1f} x {final[1]:.1f} x {final[2]:.1f} mm
**Scale Factor:** {result.get('scale_factor', 1):.2f}x

**Fixes Applied:**
- Floating pieces removed: {result.get('removed_bodies', 0)}
- Base plate added: {'Yes' if result.get('final_dims', [0,0,0])[2] > result.get('original_dims', [0,0,0])[2] * result.get('scale_factor', 1) else 'No'}

**Mesh Quality:**
- Triangles: {result.get('faces', 0):,}
- Watertight: {'Yes' if result.get('watertight') else 'No'}
- Fits build volume (220mm): {'Yes' if result.get('fits_build_volume') else 'No - needs rescaling'}
"""
    return output


@server.list_resources()
async def list_resources():
    """List available resources."""
    return [
        Resource(
            uri="convert://guide",
            name="Conversion Guide",
            description="Which conversion method to use for different images",
            mimeType="text/markdown"
        ),
        Resource(
            uri="convert://settings",
            name="Recommended Print Settings",
            description="FlashForge Adventurer 5M print settings",
            mimeType="text/markdown"
        )
    ]


@server.read_resource()
async def read_resource(uri: str):
    """Read a resource."""
    if uri == "convert://guide":
        return """# Image to 3D Conversion Guide

## Which Tool Should I Use?

| Your Image | Recommended Tool | Why |
|------------|------------------|-----|
| Icon with solid colors | `image_to_stl_contour` | Clean edges, flat extrusion |
| Logo with transparency | `image_to_stl_contour` + `invert` | Extrude the shape itself |
| Photo or detailed art | `image_to_stl_heightmap` | Captures gradients as height |
| Photo for backlight display | `image_to_lithophane` | Designed for light transmission |
| Need SVG for slicer | `image_to_svg` | Vector output for Orca/Prusa |

## Tips

### Contour Extrusion
- Use `threshold` to control edge detection sensitivity
- Use `invert=true` if you're getting the background instead of the subject
- Add `base_mm` for better bed adhesion

### Heightmap Relief
- Works best with grayscale images
- Increase `max_height_mm` for more dramatic relief
- Use `smooth` to reduce noise in photos

### Lithophane
- Print in **white PLA** for best results
- Print **vertically** (90° rotation in slicer)
- 100% infill recommended
- 0.1-0.2mm layer height for detail
"""
    elif uri == "convert://settings":
        return """# FlashForge Adventurer 5M Print Settings

## Build Volume
- X: 220mm
- Y: 220mm
- Z: 220mm

## Recommended Settings by Model Type

### Icons/Logos (Contour Extrusion)
- Layer Height: 0.2mm
- Infill: 20-50%
- Supports: Usually not needed
- Material: Any PLA/PETG

### Relief Models (Heightmap)
- Layer Height: 0.15-0.2mm
- Infill: 20-30%
- Supports: Usually not needed
- Material: Any PLA/PETG

### Lithophanes
- Layer Height: 0.1-0.15mm
- Infill: **100%**
- Print Orientation: **Vertical**
- Material: **White PLA only**
- Speed: Slow (30-40mm/s)

## OrcaSlicer Profiles
Recommended slicer for FlashForge Adventurer 5M on macOS.
Import the built-in FlashForge profile for optimal results.
"""
    return f"Resource not found: {uri}"


def main():
    """Run the MCP server."""
    import asyncio
    asyncio.run(run_server())


async def run_server():
    """Async server runner."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    main()
