"""
FlashForge Generate MCP Server

AI-powered 3D model generation from single images.

Tools:
- generate_3d_from_image: Create 3D figurine using Tripo AI
- get_generation_balance: Check API credits
"""

import os
from pathlib import Path
from mcp.server import Server
from mcp.types import Tool, TextContent, Resource
from mcp.server.stdio import stdio_server

from . import tripo

server = Server("flashforge-generate")


def check_api_key() -> bool:
    """Check if Tripo API key is configured."""
    return bool(
        os.environ.get("TRIPO_API_KEY") or
        os.environ.get("TRIPO_3D_API_TOKEN")
    )


@server.list_tools()
async def list_tools():
    """List all available generation tools."""
    return [
        Tool(
            name="generate_3d_from_image",
            description="""Generate a true 3D model from a single image using AI.

Creates full 3D geometry (not just an extrusion) from photos of objects,
characters, or figurines. The AI analyzes the image and generates a complete
3D mesh with proper depth and detail.

Best for: figurines, characters, products, toys, sculptures.

Note: Generation takes 30-60 seconds. Requires Tripo API credits.
Set TRIPO_API_KEY environment variable before using.

Example: "Generate a 3D figurine from this character image, 100mm tall with a base"
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
                        "description": "Absolute path for output STL file"
                    },
                    "scale_mm": {
                        "type": "number",
                        "description": "Target height in millimeters (default: 80)",
                        "default": 80,
                        "minimum": 20,
                        "maximum": 200
                    },
                    "add_base": {
                        "type": "boolean",
                        "description": "Add a flat base plate for printing stability (default: true)",
                        "default": True
                    },
                    "base_height_mm": {
                        "type": "number",
                        "description": "Base plate height in mm (default: 2)",
                        "default": 2,
                        "minimum": 1,
                        "maximum": 10
                    }
                },
                "required": ["image_path", "output_path"]
            }
        ),
        Tool(
            name="get_generation_balance",
            description="""Check your remaining Tripo AI API credits.

Shows how many 3D generations you have left. Each generation typically
uses 1 credit. Free tier includes credits for getting started.

Use this before generating to ensure you have enough credits.
""",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    """Handle tool calls."""

    if name == "generate_3d_from_image":
        if not check_api_key():
            return [TextContent(
                type="text",
                text="""**Error: Tripo API key not configured**

To use AI 3D generation, you need a Tripo API key:

1. Sign up at https://tripo3d.ai (free tier available)
2. Get your API key from the dashboard
3. Set the environment variable:
   ```
   export TRIPO_API_KEY='your_key_here'
   ```

Then restart Claude Desktop to pick up the new environment variable.
"""
            )]

        try:
            image_path = arguments["image_path"]
            output_path = arguments["output_path"]

            if not Path(image_path).exists():
                return [TextContent(type="text", text=f"Error: Image not found: {image_path}")]

            # Start generation
            result_text = f"**Generating 3D model from image...**\n\n"
            result_text += f"Input: {image_path}\n"
            result_text += f"Target height: {arguments.get('scale_mm', 80)}mm\n"
            result_text += f"This may take 30-60 seconds...\n\n"

            result = tripo.generate_figurine(
                image_path=image_path,
                output_path=output_path,
                scale_mm=arguments.get("scale_mm", 80),
                add_base=arguments.get("add_base", True),
                base_height_mm=arguments.get("base_height_mm", 2),
                verbose=False
            )

            dims = result.get("dimensions_mm", {})
            result_text += f"""**Generation Complete!**

**Output:** {result['output_path']}
**File Size:** {result['file_size_bytes'] / 1024:.1f} KB

**Dimensions:**
- X: {dims.get('x', 0):.1f} mm
- Y: {dims.get('y', 0):.1f} mm
- Z: {dims.get('z', 0):.1f} mm

**Mesh Info:**
- Triangles: {result.get('triangle_count', 0):,}
- Vertices: {result.get('vertex_count', 0):,}
- Watertight: {'Yes' if result.get('is_watertight') else 'No'}
- Base Added: {'Yes' if result.get('has_base') else 'No'}

Ready to import into OrcaSlicer for printing!
"""
            return [TextContent(type="text", text=result_text)]

        except Exception as e:
            return [TextContent(type="text", text=f"**Generation failed:** {e}")]

    elif name == "get_generation_balance":
        if not check_api_key():
            return [TextContent(
                type="text",
                text="**Error:** Tripo API key not configured. Set TRIPO_API_KEY environment variable."
            )]

        try:
            client = tripo.TripoClient(verbose=False)
            balance = client.get_balance()

            result = "**Tripo AI API Balance**\n\n"
            for key, value in balance.items():
                result += f"- {key}: {value}\n"

            return [TextContent(type="text", text=result)]

        except Exception as e:
            return [TextContent(type="text", text=f"**Error checking balance:** {e}")]

    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


@server.list_resources()
async def list_resources():
    """List available resources."""
    return [
        Resource(
            uri="generate://guide",
            name="AI Generation Guide",
            description="Tips for best results with AI 3D generation",
            mimeType="text/markdown"
        )
    ]


@server.read_resource()
async def read_resource(uri: str):
    """Read a resource."""
    if uri == "generate://guide":
        return """# AI 3D Generation Guide

## What Works Best

AI 3D generation creates true 3D models (not extrusions) from single images.
Best results come from:

- **Clear subject**: Single object/character with distinct outline
- **Good lighting**: Well-lit, minimal shadows
- **Simple background**: Plain or transparent background
- **Multiple views visible**: Front-facing works, but slight angle helps
- **High resolution**: Larger images capture more detail

## What Doesn't Work Well

- Multiple objects in one image
- Very thin or detailed features (may be simplified)
- Text or 2D patterns
- Low contrast images
- Heavily stylized art (may lose detail)

## Tips for Figurines

1. Use reference images with the character facing forward
2. Transparent background (PNG) helps isolation
3. Scale to 50-100mm for best detail/print time balance
4. Always add a base for printing stability
5. Print with supports for overhangs

## Tripo API

This server uses the Tripo AI API for generation.

- **Free tier**: Limited credits to try
- **Paid plans**: More credits for regular use
- **Generation time**: 30-60 seconds per model

Sign up at https://tripo3d.ai

## When to Use This vs Convert Tools

| Use Generate | Use Convert |
|--------------|-------------|
| 3D characters/figurines | Flat icons/logos |
| Products with depth | 2D artwork |
| Sculptures | Simple shapes |
| Photos of objects | Silhouettes |

Generate creates true 3D. Convert extrudes 2D shapes.
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
