"""
FlashForge Convert MCP Server

Convert 2D images to 3D-printable STL files and slice for printing.

Tools:
- image_to_stl_contour: Edge detection and extrusion for icons/logos
- image_to_stl_heightmap: Brightness-to-height for relief models
- image_to_lithophane: Create backlit photo displays
- image_to_svg: Vector conversion for slicers
- validate_stl: Check STL printability
- fix_model: Scale, add base, remove floating pieces from 3D models
- slice_stl: Slice STL to G-code using OrcaSlicer
- split_model: Split 3D models into printable parts
- add_connectors: Add peg/hole snap-fit connectors to parts
- analyze_split_points: Suggest optimal cut locations for figurines
- export_assembly_3mf: Combine parts into a 3MF assembly
"""

import os
from pathlib import Path
from mcp.server import Server
from mcp.types import Tool, TextContent, Resource
from mcp.server.stdio import stdio_server

from . import converters
from . import slicer
from . import figurines

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
- **Auto-orient** to stand upright (figurines lying down are rotated)
- **Scale** to target height (default 80mm)
- **Remove floating pieces** that can't print
- **Repair mesh** for clean, watertight output

Best for: AI-generated models (Meshy, Tripo, etc), downloaded models with issues,
models that are too small, lying on their side, or have disconnected parts.

Example: "Fix this model and scale to 100mm"
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
                        "description": "Base plate thickness in mm (default: 0 = no base)",
                        "default": 0,
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
                    },
                    "auto_orient": {
                        "type": "boolean",
                        "description": "Auto-orient model to stand upright (default: true)",
                        "default": True
                    }
                },
                "required": ["input_path"]
            }
        ),
        Tool(
            name="slice_stl",
            description="""Slice an STL file to G-code for printing on FlashForge Adventurer 5M.

Uses OrcaSlicer to generate G-code with optimized settings for your printer.
The model is automatically centered on the print plate.
The resulting .gcode file can be sent directly to the printer.

Requires OrcaSlicer to be installed. Set ORCASLICER_PATH if not auto-detected.

Example: "Slice this STL for printing with fine quality and 30% infill"
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "stl_path": {
                        "type": "string",
                        "description": "Absolute path to input STL file"
                    },
                    "output_path": {
                        "type": "string",
                        "description": "Output G-code path (optional, auto-generated if not provided)"
                    },
                    "quality": {
                        "type": "string",
                        "description": "Print quality preset (default: standard)",
                        "enum": ["draft", "standard", "fine"],
                        "default": "standard"
                    },
                    "layer_height": {
                        "type": "number",
                        "description": "Override layer height in mm (0.08-0.4, default: based on quality)",
                        "minimum": 0.08,
                        "maximum": 0.4
                    },
                    "infill_percent": {
                        "type": "integer",
                        "description": "Infill density percentage (default: 20)",
                        "default": 20,
                        "minimum": 0,
                        "maximum": 100
                    },
                    "support": {
                        "type": "boolean",
                        "description": "Enable support structures (default: false)",
                        "default": False
                    },
                    "material": {
                        "type": "string",
                        "description": "Filament material type (default: pla)",
                        "enum": ["pla", "petg"],
                        "default": "pla"
                    }
                },
                "required": ["stl_path"]
            }
        ),
        # Multi-part figurine tools
        Tool(
            name="split_model",
            description="""Split a 3D model into printable parts using cut planes.

Best for: figurines too tall to print, models that need assembly.

Cuts the model at specified Z heights and creates separate watertight STL files
for each part. Parts are automatically positioned at Z=0 for printing.

Example: "Split this knight figurine at 50mm and 100mm for easier printing"
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "input_path": {
                        "type": "string",
                        "description": "Absolute path to input 3D model (STL, GLB, OBJ)"
                    },
                    "output_dir": {
                        "type": "string",
                        "description": "Directory for output part files"
                    },
                    "cut_heights_z": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "List of Z heights (in mm) for horizontal cuts, e.g., [50, 100]"
                    },
                    "cut_planes": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "origin": {
                                    "type": "array",
                                    "items": {"type": "number"},
                                    "description": "[x, y, z] point on the cut plane"
                                },
                                "normal": {
                                    "type": "array",
                                    "items": {"type": "number"},
                                    "description": "[nx, ny, nz] direction the plane faces"
                                }
                            }
                        },
                        "description": "Advanced: custom cut planes with origin and normal vectors"
                    }
                },
                "required": ["input_path", "output_dir"]
            }
        ),
        Tool(
            name="add_connectors",
            description="""Add peg or hole snap-fit connectors to a model part.

Best for: creating assembly joints between split parts.

Pegs are solid protrusions added to one part. Holes are cavities in the matching
part. Default 4mm diameter with 0.2mm clearance for reliable FDM printing.

Example: "Add a peg connector to the top of this part at the center"
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "input_path": {
                        "type": "string",
                        "description": "Absolute path to input STL file"
                    },
                    "output_path": {
                        "type": "string",
                        "description": "Output STL path (optional, auto-generated if not provided)"
                    },
                    "connector_type": {
                        "type": "string",
                        "enum": ["peg", "hole"],
                        "description": "Type of connector: 'peg' (protrusion) or 'hole' (cavity)"
                    },
                    "position": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "[x, y, z] center point for connector (default: center of top face)"
                    },
                    "direction": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "[nx, ny, nz] direction connector points (default: [0, 0, 1] = up)"
                    },
                    "diameter_mm": {
                        "type": "number",
                        "description": "Connector diameter in mm (default: 4.0)",
                        "default": 4.0,
                        "minimum": 2.0,
                        "maximum": 10.0
                    },
                    "depth_mm": {
                        "type": "number",
                        "description": "Connector depth in mm (default: 5.0)",
                        "default": 5.0,
                        "minimum": 2.0,
                        "maximum": 20.0
                    },
                    "clearance_mm": {
                        "type": "number",
                        "description": "Extra diameter for holes to ensure fit (default: 0.2mm)",
                        "default": 0.2,
                        "minimum": 0.1,
                        "maximum": 1.0
                    }
                },
                "required": ["input_path", "connector_type"]
            }
        ),
        Tool(
            name="analyze_split_points",
            description="""Analyze model geometry and suggest optimal cut locations.

Best for: finding natural break points in figurines before splitting.

Scans cross-sectional area at various heights to find narrowest points (necks,
waists, joints) where cuts will be cleanest and connectors most stable.

Example: "Analyze this dragon model and suggest where to split it"
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "input_path": {
                        "type": "string",
                        "description": "Absolute path to 3D model file"
                    },
                    "num_suggestions": {
                        "type": "integer",
                        "description": "Number of cut points to suggest (default: 3)",
                        "default": 3,
                        "minimum": 1,
                        "maximum": 10
                    }
                },
                "required": ["input_path"]
            }
        ),
        Tool(
            name="export_assembly_3mf",
            description="""Combine multiple part files into a single 3MF assembly.

Best for: packaging split parts for slicing together or sharing.

Creates a 3MF file containing all parts, optionally arranged on the build plate.
The 3MF format preserves part relationships and can be opened in OrcaSlicer.

Example: "Package these 3 parts into an assembly.3mf file"
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "part_paths": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of paths to STL/OBJ part files"
                    },
                    "output_path": {
                        "type": "string",
                        "description": "Path for output 3MF file"
                    },
                    "arrange": {
                        "type": "boolean",
                        "description": "Automatically arrange parts on build plate (default: true)",
                        "default": True
                    },
                    "spacing_mm": {
                        "type": "number",
                        "description": "Spacing between arranged parts in mm (default: 10)",
                        "default": 10,
                        "minimum": 5,
                        "maximum": 50
                    }
                },
                "required": ["part_paths", "output_path"]
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
                base_height_mm=arguments.get("base_height_mm", 0),
                base_padding_mm=arguments.get("base_padding_mm", 3.0),
                remove_floating=arguments.get("remove_floating", True),
                auto_orient=arguments.get("auto_orient", True),
            )
            return [TextContent(type="text", text=format_fix_result(result))]
        except Exception as e:
            return [TextContent(type="text", text=f"Error fixing model: {e}")]

    elif name == "slice_stl":
        try:
            # Check if OrcaSlicer is available
            orca_path = slicer.find_orcaslicer()
            if not orca_path:
                return [TextContent(type="text", text=slicer.get_not_found_message())]

            output_path = arguments.get("output_path") or get_output_path(arguments["stl_path"], "_sliced", ".gcode")

            result = slicer.slice_stl(
                stl_path=arguments["stl_path"],
                output_path=output_path,
                quality=arguments.get("quality", "standard"),
                layer_height=arguments.get("layer_height"),
                infill_percent=arguments.get("infill_percent", 20),
                support=arguments.get("support", False),
                material=arguments.get("material", "pla"),
            )

            return [TextContent(type="text", text=format_slice_result(result))]
        except Exception as e:
            return [TextContent(type="text", text=f"Error slicing STL: {e}")]

    # Multi-part figurine tools
    elif name == "split_model":
        try:
            output_dir = arguments.get("output_dir") or str(OUTPUT_DIR / "parts")
            result = figurines.split_model(
                input_path=arguments["input_path"],
                output_dir=output_dir,
                cut_heights_z=arguments.get("cut_heights_z"),
                cut_planes=arguments.get("cut_planes"),
            )
            return [TextContent(type="text", text=format_split_result(result))]
        except Exception as e:
            return [TextContent(type="text", text=f"Error splitting model: {e}")]

    elif name == "add_connectors":
        try:
            output_path = arguments.get("output_path") or get_output_path(
                arguments["input_path"],
                f"_{arguments['connector_type']}"
            )
            result = figurines.add_connector(
                input_path=arguments["input_path"],
                output_path=output_path,
                connector_type=arguments["connector_type"],
                position=arguments.get("position"),
                direction=arguments.get("direction"),
                diameter_mm=arguments.get("diameter_mm", 4.0),
                depth_mm=arguments.get("depth_mm", 5.0),
                clearance_mm=arguments.get("clearance_mm", 0.2),
            )
            return [TextContent(type="text", text=format_connector_result(result))]
        except Exception as e:
            return [TextContent(type="text", text=f"Error adding connector: {e}")]

    elif name == "analyze_split_points":
        try:
            result = figurines.analyze_split_points(
                input_path=arguments["input_path"],
                num_suggestions=arguments.get("num_suggestions", 3),
            )
            return [TextContent(type="text", text=format_analysis_result(result))]
        except Exception as e:
            return [TextContent(type="text", text=f"Error analyzing model: {e}")]

    elif name == "export_assembly_3mf":
        try:
            result = figurines.export_assembly_3mf(
                part_paths=arguments["part_paths"],
                output_path=arguments["output_path"],
                arrange=arguments.get("arrange", True),
                spacing_mm=arguments.get("spacing_mm", 10.0),
            )
            return [TextContent(type="text", text=format_assembly_result(result))]
        except Exception as e:
            return [TextContent(type="text", text=f"Error exporting assembly: {e}")]

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


def format_slice_result(result: dict) -> str:
    """Format slicing result for display."""
    file_size_kb = result.get("file_size_bytes", 0) / 1024
    file_size_str = f"{file_size_kb:.1f} KB" if file_size_kb < 1024 else f"{file_size_kb/1024:.1f} MB"

    return f"""**Slicing Complete**

**Output:** {result.get('output_path', 'N/A')}
**File Size:** {file_size_str}

**Print Settings:**
- Quality: {result.get('quality', 'standard')}
- Layer Height: {result.get('layer_height', 0.2)}mm
- Infill: {result.get('infill_percent', 20)}%
- Support: {'Yes' if result.get('support') else 'No'}
- Material: {result.get('material', 'PLA')}

**Estimates:**
- Print Time: {result.get('print_time_estimate', 'Unknown')}
- Filament: {result.get('filament_used_g', 0):.1f}g ({result.get('filament_used_m', 0):.2f}m)

Ready to send to printer with `send_gcode_file`!
"""


def format_split_result(result: dict) -> str:
    """Format model split result for display."""
    orig_dims = result.get("original_dimensions_mm", {})

    output = f"""**Model Split Complete**

**Input:** {result.get('input_path', 'N/A')}
**Original Size:** {orig_dims.get('x', 0):.1f} x {orig_dims.get('y', 0):.1f} x {orig_dims.get('z', 0):.1f} mm
**Parts Created:** {result.get('num_parts', 0)}

**Parts:**
"""
    for part in result.get('parts', []):
        dims = part.get('dimensions_mm', {})
        watertight = 'Yes' if part.get('watertight') else 'No'
        output += f"""
**Part {part.get('part_number', 0)}:**
- Output: {part.get('output_path', 'N/A')}
- Size: {dims.get('x', 0):.1f} x {dims.get('y', 0):.1f} x {dims.get('z', 0):.1f} mm
- Triangles: {part.get('triangles', 0):,}
- Watertight: {watertight}
"""

    output += """
**Next Steps:**
1. Use `analyze_split_points` to find good connector locations
2. Use `add_connectors` to add peg/hole connectors to each part
3. Slice and print each part separately
"""
    return output


def format_connector_result(result: dict) -> str:
    """Format connector result for display."""
    file_size_kb = result.get("file_size_bytes", 0) / 1024

    return f"""**Connector Added**

**Output:** {result.get('output_path', 'N/A')}
**File Size:** {file_size_kb:.1f} KB

**Connector Details:**
- Type: {result.get('connector_type', 'N/A').upper()}
- Diameter: {result.get('diameter_mm', 4.0):.1f}mm{' (+' + str(result.get('clearance_mm', 0)) + 'mm clearance)' if result.get('connector_type') == 'hole' else ''}
- Depth: {result.get('depth_mm', 5.0):.1f}mm
- Position: [{', '.join(f'{x:.1f}' for x in result.get('position', [0, 0, 0]))}]
- Direction: [{', '.join(f'{x:.1f}' for x in result.get('direction', [0, 0, 1]))}]

**Mesh Quality:**
- Triangles: {result.get('triangles', 0):,}
- Watertight: {'Yes' if result.get('watertight') else 'No'}

**Tip:** For matching parts, use the same position but opposite connector type (peg/hole).
"""


def format_analysis_result(result: dict) -> str:
    """Format split point analysis result for display."""
    output = f"""**Split Point Analysis**

**Model:** {result.get('input_path', 'N/A')}
**Model Height:** {result.get('model_height_mm', 0):.1f}mm

**Suggested Cut Points:** {result.get('num_suggestions', 0)}
"""

    for i, suggestion in enumerate(result.get('suggested_cuts', []), 1):
        output += f"""
**Cut {i}:** Z = {suggestion.get('height_from_bottom_mm', 0):.1f}mm ({suggestion.get('height_ratio', 0) * 100:.0f}% from bottom)
- Cross-sectional area: {suggestion.get('area_mm2', 0):.1f}mm²
- Narrowness score: {suggestion.get('score', 0):.2f} (higher = better)
"""

    output += """
**Recommended Cut Heights:**
"""
    for height in result.get('recommended_cut_heights_z', []):
        output += f"- {height:.1f}mm\n"

    output += """
**Resulting Parts:**
"""
    for part in result.get('resulting_parts', []):
        output += f"- Part {part.get('part', 0)}: {part.get('height_mm', 0):.1f}mm (Z {part.get('start_z', 0):.1f} - {part.get('end_z', 0):.1f})\n"

    output += """
**Next Steps:**
Use `split_model` with `cut_heights_z` parameter to split at these heights.
"""
    return output


def format_assembly_result(result: dict) -> str:
    """Format 3MF assembly result for display."""
    file_size_kb = result.get("file_size_bytes", 0) / 1024
    file_size_str = f"{file_size_kb:.1f} KB" if file_size_kb < 1024 else f"{file_size_kb/1024:.1f} MB"

    output = f"""**3MF Assembly Created**

**Output:** {result.get('output_path', 'N/A')}
**File Size:** {file_size_str}
**Parts Included:** {result.get('num_parts', 0)}
**Arranged on Build Plate:** {'Yes' if result.get('arranged') else 'No'}
"""

    if result.get('fits_build_plate') is not None:
        output += f"**Fits Build Volume:** {'Yes' if result.get('fits_build_plate') else 'No - needs manual rearrangement'}\n"

    output += """
**Parts:**
"""
    for part in result.get('parts', []):
        dims = part.get('dimensions_mm', {})
        output += f"- Part {part.get('part_number', 0)}: {dims.get('x', 0):.1f} x {dims.get('y', 0):.1f} x {dims.get('z', 0):.1f}mm\n"

    output += """
**Next Steps:**
Open the .3mf file in OrcaSlicer to slice all parts together.
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
