"""
FlashForge Printer MCP Server

Control and monitor FlashForge 3D printers from AI assistants.

Tools:
- discover_printers: Find FlashForge printers on local network
- get_printer_info: Get printer model, firmware, serial number
- get_printer_status: Get temperatures, progress, and state
- send_gcode_file: Upload G-code file with optional auto-start
- get_camera_url: Get camera stream URL for monitoring
- watch_printer: Combined status check with camera option for active prints
"""

import os
import subprocess
import sys
from pathlib import Path
from mcp.server import Server
from mcp.types import Tool, TextContent, Resource
from mcp.server.stdio import stdio_server

from . import protocol

# Create the MCP server
server = Server("flashforge-printer")


@server.list_tools()
async def list_tools():
    """List all available printer control tools."""
    return [
        Tool(
            name="discover_printers",
            description="""Find FlashForge 3D printers on your local network.

Sends a UDP broadcast to discover all FlashForge printers (Adventurer 5M, 5M Pro, etc.)
connected to the same network. Returns printer name, IP address, model, and firmware.

Use this tool first to find your printer's IP address before using other printer tools.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "timeout_seconds": {
                        "type": "number",
                        "description": "How long to wait for printer responses (default: 5 seconds)",
                        "default": 5,
                        "minimum": 1,
                        "maximum": 30
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="get_printer_info",
            description="""Get detailed information about a FlashForge printer.

Returns the printer's model name, firmware version, serial number, and build volume dimensions.
Requires the printer's IP address (use discover_printers to find it).""",
            inputSchema={
                "type": "object",
                "properties": {
                    "ip": {
                        "type": "string",
                        "description": "Printer IP address (e.g., '192.168.1.100')"
                    }
                },
                "required": ["ip"]
            }
        ),
        Tool(
            name="get_printer_status",
            description="""Get the current status of a FlashForge printer.

Returns real-time information including:
- State: idle, printing, or paused
- Nozzle temperature (current and target)
- Bed temperature (current and target)
- Print progress percentage (if printing)

Useful for monitoring prints in progress.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "ip": {
                        "type": "string",
                        "description": "Printer IP address"
                    }
                },
                "required": ["ip"]
            }
        ),
        Tool(
            name="send_gcode_file",
            description="""Upload a G-code file to the printer and optionally start printing.

Transfers a .gcode or .gx file to the printer's internal storage.
The file will be saved to the printer's user folder and can be started immediately
or printed later from the printer's touchscreen.

Warning: Starting a print will begin heating and movement. Ensure the printer is ready.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "ip": {
                        "type": "string",
                        "description": "Printer IP address"
                    },
                    "file_path": {
                        "type": "string",
                        "description": "Absolute path to the G-code file to upload"
                    },
                    "start_print": {
                        "type": "boolean",
                        "description": "Start printing immediately after upload (default: false)",
                        "default": False
                    }
                },
                "required": ["ip", "file_path"]
            }
        ),
        Tool(
            name="get_camera_url",
            description="""Get the camera stream URL for a FlashForge printer.

Returns the MJPEG stream URL that can be opened in a browser or video player
to view the printer's built-in camera feed. Useful for remote monitoring.

The URL format is: http://<ip>:8080/?action=stream""",
            inputSchema={
                "type": "object",
                "properties": {
                    "ip": {
                        "type": "string",
                        "description": "Printer IP address"
                    }
                },
                "required": ["ip"]
            }
        ),
        Tool(
            name="watch_printer",
            description="""Smart printer dashboard - discover, check status, and watch active prints.

This is the recommended way to check on your printer. It:
1. Discovers printers on the network (or uses specified IP)
2. Shows detailed status including temperatures and print progress
3. If printing, offers to open the camera feed in your browser

Perfect for: "How's my print going?" or "Check on my printer"

Example: "Watch my printer" or "How's the print at 192.168.1.100 doing?"
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "ip": {
                        "type": "string",
                        "description": "Printer IP address (optional - will auto-discover if not provided)"
                    },
                    "open_camera": {
                        "type": "boolean",
                        "description": "Automatically open camera feed in browser if printer is actively printing (default: false)",
                        "default": False
                    }
                },
                "required": []
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    """Handle tool calls."""

    if name == "discover_printers":
        timeout = arguments.get("timeout_seconds", 5)
        try:
            printers = protocol.discover_printers(timeout=timeout)
            if not printers:
                return [TextContent(
                    type="text",
                    text="No FlashForge printers found on the network.\n\n"
                         "Make sure:\n"
                         "- Printer is powered on and connected to WiFi/Ethernet\n"
                         "- Computer is on the same network as the printer\n"
                         "- Printer's LAN mode is enabled in settings"
                )]

            result = f"Found {len(printers)} printer(s):\n\n"
            for i, p in enumerate(printers, 1):
                result += f"**[{i}] {p.name}**\n"
                result += f"  - IP: {p.ip}\n"
                if p.model:
                    result += f"  - Model: {p.model}\n"
                if p.firmware:
                    result += f"  - Firmware: {p.firmware}\n"
                result += f"  - Camera: {protocol.get_camera_url(p.ip)}\n\n"

            return [TextContent(type="text", text=result)]
        except Exception as e:
            return [TextContent(type="text", text=f"Error discovering printers: {e}")]

    elif name == "get_printer_info":
        ip = arguments["ip"]
        try:
            info = protocol.get_printer_info(ip)
            result = f"**Printer Info ({ip})**\n\n"
            for key, value in info.items():
                result += f"- {key}: {value}\n"
            return [TextContent(type="text", text=result)]
        except Exception as e:
            return [TextContent(type="text", text=f"Error getting printer info: {e}")]

    elif name == "get_printer_status":
        ip = arguments["ip"]
        try:
            status = protocol.get_printer_status(ip)

            result = f"**Printer Status ({ip})**\n\n"
            result += f"State: **{status.get('state', 'unknown').upper()}**\n\n"

            if 'nozzle_temp' in status:
                result += f"Nozzle: {status['nozzle_temp']:.0f}°C"
                if 'nozzle_target' in status and status['nozzle_target'] > 0:
                    result += f" / {status['nozzle_target']:.0f}°C target"
                result += "\n"

            if 'bed_temp' in status:
                result += f"Bed: {status['bed_temp']:.0f}°C"
                if 'bed_target' in status and status['bed_target'] > 0:
                    result += f" / {status['bed_target']:.0f}°C target"
                result += "\n"

            if 'progress' in status:
                result += f"\nProgress: **{status['progress']:.1f}%**"
                if 'bytes_printed' in status and 'bytes_total' in status:
                    result += f" ({status['bytes_printed']:,} / {status['bytes_total']:,} bytes)"
                result += "\n"

            return [TextContent(type="text", text=result)]
        except Exception as e:
            return [TextContent(type="text", text=f"Error getting printer status: {e}")]

    elif name == "send_gcode_file":
        ip = arguments["ip"]
        file_path = arguments["file_path"]
        start_print = arguments.get("start_print", False)

        path = Path(file_path)
        if not path.exists():
            return [TextContent(type="text", text=f"Error: File not found: {file_path}")]

        if not path.suffix.lower() in ['.gcode', '.gx']:
            return [TextContent(type="text", text=f"Error: File must be .gcode or .gx format")]

        try:
            filesize = path.stat().st_size
            result = f"Uploading {path.name} ({filesize / 1024:.1f} KB) to {ip}...\n"

            success = protocol.send_file(
                ip=ip,
                filepath=str(path),
                start_print=start_print
            )

            if success:
                result += f"\n**Upload complete!**\n"
                if start_print:
                    result += "Print has been started."
                else:
                    result += f"File saved to printer. Start print from the touchscreen or use start_print=true."

            return [TextContent(type="text", text=result)]
        except Exception as e:
            return [TextContent(type="text", text=f"Error uploading file: {e}")]

    elif name == "get_camera_url":
        ip = arguments["ip"]
        url = protocol.get_camera_url(ip)
        return [TextContent(
            type="text",
            text=f"**Camera Stream URL**\n\n{url}\n\nOpen in a browser or video player (like VLC) to view the live feed."
        )]

    elif name == "watch_printer":
        ip = arguments.get("ip")
        open_camera = arguments.get("open_camera", False)

        try:
            # Step 1: Find printer if IP not provided
            if not ip:
                printers = protocol.discover_printers(timeout=5.0)
                if not printers:
                    return [TextContent(
                        type="text",
                        text="**No printers found on the network.**\n\n"
                             "Make sure your printer is on and connected to the same network."
                    )]
                if len(printers) > 1:
                    result = f"**Found {len(printers)} printers** - specify which one to watch:\n\n"
                    for p in printers:
                        result += f"- **{p.name}** at `{p.ip}`\n"
                    result += "\nUse: watch_printer with ip='...' to select one."
                    return [TextContent(type="text", text=result)]
                ip = printers[0].ip
                printer_name = printers[0].name
            else:
                printer_name = ip

            # Step 2: Get printer info and status
            info = {}
            try:
                info = protocol.get_printer_info(ip)
            except:
                pass

            status = protocol.get_printer_status(ip)
            camera_url = protocol.get_camera_url(ip)

            # Step 3: Build response
            state = status.get('state', 'unknown').upper()
            is_printing = state == 'PRINTING'

            result = f"# 🖨️ {info.get('name', printer_name)}\n\n"

            if info.get('model'):
                result += f"**Model:** {info['model']}\n"
            result += f"**IP:** {ip}\n"
            result += f"**Status:** "

            if is_printing:
                progress = status.get('progress', 0)
                result += f"🟢 **PRINTING** ({progress:.1f}% complete)\n\n"

                # Progress bar
                bar_length = 20
                filled = int(bar_length * progress / 100)
                bar = "█" * filled + "░" * (bar_length - filled)
                result += f"```\n[{bar}] {progress:.1f}%\n```\n\n"
            elif state == 'IDLE':
                result += "⚪ **IDLE** (ready to print)\n\n"
            elif state == 'PAUSED':
                result += "🟡 **PAUSED**\n\n"
            else:
                result += f"⚫ **{state}**\n\n"

            # Temperatures
            result += "## Temperatures\n\n"
            if 'nozzle_temp' in status:
                nozzle = status['nozzle_temp']
                target = status.get('nozzle_target', 0)
                if target > 0:
                    result += f"- **Nozzle:** {nozzle:.0f}°C → {target:.0f}°C\n"
                else:
                    result += f"- **Nozzle:** {nozzle:.0f}°C\n"

            if 'bed_temp' in status:
                bed = status['bed_temp']
                target = status.get('bed_target', 0)
                if target > 0:
                    result += f"- **Bed:** {bed:.0f}°C → {target:.0f}°C\n"
                else:
                    result += f"- **Bed:** {bed:.0f}°C\n"

            result += "\n"

            # Camera section
            result += "## 📹 Camera\n\n"
            result += f"**Stream URL:** {camera_url}\n\n"

            if is_printing:
                result += "💡 **Tip:** Open the camera URL in your browser or VLC to watch your print!\n"

                # Open camera if requested
                if open_camera:
                    try:
                        if sys.platform == 'darwin':
                            subprocess.Popen(['open', camera_url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                            result += "\n✅ **Camera opened in your default browser!**\n"
                        elif sys.platform == 'linux':
                            subprocess.Popen(['xdg-open', camera_url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                            result += "\n✅ **Camera opened in your default browser!**\n"
                        elif sys.platform == 'win32':
                            subprocess.Popen(['start', camera_url], shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                            result += "\n✅ **Camera opened in your default browser!**\n"
                    except Exception as e:
                        result += f"\n⚠️ Could not open browser: {e}\n"
            else:
                result += "Camera available for monitoring when you start a print.\n"

            return [TextContent(type="text", text=result)]

        except Exception as e:
            return [TextContent(type="text", text=f"**Error watching printer:** {e}")]

    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


@server.list_resources()
async def list_resources():
    """List available resources."""
    return [
        Resource(
            uri="printer://help",
            name="Printer Help",
            description="Guide to using FlashForge printer tools",
            mimeType="text/markdown"
        )
    ]


@server.read_resource()
async def read_resource(uri: str):
    """Read a resource."""
    if uri == "printer://help":
        return """# FlashForge Printer MCP Server

## Quick Start

1. **Discover your printer:**
   "Find FlashForge printers on my network"

2. **Check printer status:**
   "What's the status of my printer at 192.168.1.100?"

3. **Upload and print:**
   "Send model.gcode to my printer and start printing"

## Available Tools

| Tool | Description |
|------|-------------|
| **watch_printer** | Smart dashboard - status + camera (recommended!) |
| discover_printers | Find printers on network |
| get_printer_info | Get model and firmware info |
| get_printer_status | Check temperatures and progress |
| send_gcode_file | Upload G-code to printer |
| get_camera_url | Get live camera stream URL |

## Supported Printers

- FlashForge Adventurer 5M
- FlashForge Adventurer 5M Pro
- Other FlashForge printers with network support

## Requirements

- Printer and computer on same local network
- Printer's LAN mode enabled
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
