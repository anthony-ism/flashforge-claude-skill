"""
OrcaSlicer integration for FlashForge MCP.

Handles:
- OrcaSlicer executable detection
- Profile management
- G-code generation from STL files

KNOWN ISSUES:
    OrcaSlicer CLI has profile compatibility validation that fails with
    custom/standalone profiles. The error "process not compatible with printer"
    occurs because:

    1. OrcaSlicer profiles use inheritance chains that CLI validates strictly
    2. The bundled FlashForge profiles have a bug (missing G92 E0 in layer_change_gcode)
    3. compatible_printers field matching is strict and underdocumented

    See docs/SLICING.md for workarounds and details.

    Current workaround: Use OrcaSlicer GUI to slice, then use send_gcode_file
    MCP tool to upload the G-code to the printer.
"""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional


# Quality presets mapping quality name -> layer height
QUALITY_PRESETS = {
    "draft": 0.28,
    "standard": 0.2,
    "fine": 0.15,
}

# Common OrcaSlicer installation paths by platform
ORCA_PATHS = {
    "darwin": [
        "/Applications/OrcaSlicer.app/Contents/MacOS/OrcaSlicer",
        str(Path.home() / "Applications/OrcaSlicer.app/Contents/MacOS/OrcaSlicer"),
    ],
    "linux": [
        "/usr/bin/orca-slicer",
        "/opt/OrcaSlicer/orca-slicer",
        str(Path.home() / ".local/bin/orca-slicer"),
        "/usr/local/bin/orca-slicer",
    ],
    "win32": [
        r"C:\Program Files\OrcaSlicer\orca-slicer.exe",
        r"C:\Program Files (x86)\OrcaSlicer\orca-slicer.exe",
    ],
}


def find_orcaslicer() -> Optional[str]:
    """
    Find OrcaSlicer executable on this system.

    Checks in order:
    1. ORCASLICER_PATH environment variable
    2. Platform-specific common installation paths
    3. System PATH lookup

    Returns:
        Path to OrcaSlicer executable, or None if not found
    """
    # Check environment variable first (user override)
    if env_path := os.environ.get("ORCASLICER_PATH"):
        if Path(env_path).exists():
            return env_path

    # Check platform-specific paths
    platform_paths = ORCA_PATHS.get(sys.platform, [])
    for path in platform_paths:
        if Path(path).exists():
            return path

    # Try PATH lookup
    if which_path := shutil.which("orca-slicer"):
        return which_path
    if which_path := shutil.which("OrcaSlicer"):
        return which_path

    return None


def get_profiles_dir() -> Path:
    """
    Get the bundled profiles directory.

    Uses standalone profiles bundled with this package that don't rely on
    OrcaSlicer's system profile inheritance (which has bugs).
    """
    # Check for user override
    if profiles_dir := os.environ.get("ORCASLICER_PROFILES_DIR"):
        return Path(profiles_dir)

    # Use bundled standalone profiles
    return Path(__file__).parent / "profiles" / "adventurer_5m_pro"


def get_not_found_message() -> str:
    """Return helpful error message when OrcaSlicer is not found."""
    return """**Error: OrcaSlicer not found**

OrcaSlicer is required for slicing. Please install it:

1. Download from https://github.com/SoftFever/OrcaSlicer/releases
2. Install to the default location
3. Or set `ORCASLICER_PATH` environment variable to the executable path

**Common paths:**
- macOS: `/Applications/OrcaSlicer.app/Contents/MacOS/OrcaSlicer`
- Linux: `/usr/bin/orca-slicer`
- Windows: `C:\\Program Files\\OrcaSlicer\\orca-slicer.exe`
"""


def slice_stl(
    stl_path: str,
    output_path: str,
    quality: str = "standard",
    layer_height: Optional[float] = None,
    infill_percent: int = 20,
    support: bool = False,
    material: str = "pla",
) -> dict:
    """
    Slice an STL file to G-code using OrcaSlicer CLI.

    Args:
        stl_path: Path to input STL file
        output_path: Path for output G-code file
        quality: Quality preset ("draft", "standard", "fine")
        layer_height: Override layer height in mm (optional)
        infill_percent: Infill density percentage (0-100)
        support: Enable support structures
        material: Filament material ("pla", "petg")

    Returns:
        dict with:
            - output_path: Path to generated G-code
            - file_size_bytes: Size of output file
            - quality: Quality preset used
            - layer_height: Actual layer height
            - infill_percent: Infill percentage
            - support: Whether supports were enabled
            - material: Material type
            - print_time_estimate: Estimated print time string
            - filament_used_g: Estimated filament weight in grams
            - filament_used_m: Estimated filament length in meters

    Raises:
        FileNotFoundError: If STL file doesn't exist
        RuntimeError: If OrcaSlicer is not found or slicing fails
    """
    stl_path = Path(stl_path)
    output_path = Path(output_path)

    if not stl_path.exists():
        raise FileNotFoundError(f"STL file not found: {stl_path}")

    orca_path = find_orcaslicer()
    if not orca_path:
        raise RuntimeError("OrcaSlicer not found")

    profiles_dir = get_profiles_dir()

    # Resolve layer height from quality or override
    actual_layer_height = layer_height if layer_height is not None else QUALITY_PRESETS.get(quality, 0.2)

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Use bundled standalone profiles (no inheritance issues)
    printer_profile = profiles_dir / "machine_standalone.json"
    process_profile = profiles_dir / "process_standalone.json"
    filament_profile = profiles_dir / "filament_standalone.json"

    # Verify profiles exist
    for profile_path, profile_name in [
        (printer_profile, "machine"),
        (process_profile, "process"),
        (filament_profile, "filament"),
    ]:
        if not profile_path.exists():
            raise RuntimeError(f"Missing {profile_name} profile: {profile_path}")

    # Build settings string for OrcaSlicer
    settings_files = f"{printer_profile};{process_profile}"

    # Build command
    cmd = [
        orca_path,
        "--slice", "0",           # Slice all plates
        "--arrange", "1",         # Auto-arrange/center model on plate
        "--orient", "1",          # Auto-orient for best printability
        "--load-settings", settings_files,
        "--load-filaments", str(filament_profile),
        "--outputdir", str(output_path.parent),
        "--allow-newer-file",
        str(stl_path),
    ]

    # Execute slicer
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("OrcaSlicer timed out after 5 minutes")

    if result.returncode != 0:
        error_msg = result.stderr or result.stdout or "Unknown error"
        raise RuntimeError(f"OrcaSlicer failed: {error_msg}")

    # OrcaSlicer may generate the file with a different name
    # Look for the generated gcode file
    expected_gcode = output_path.parent / f"{stl_path.stem}.gcode"

    if expected_gcode.exists() and expected_gcode != output_path:
        # Rename to requested output path
        expected_gcode.rename(output_path)
    elif not output_path.exists():
        # Try to find any new gcode file
        gcode_files = list(output_path.parent.glob("*.gcode"))
        if gcode_files:
            newest = max(gcode_files, key=lambda f: f.stat().st_mtime)
            if newest != output_path:
                newest.rename(output_path)

    if not output_path.exists():
        raise RuntimeError(f"Slicing completed but output file not found: {output_path}")

    # Parse output for estimates
    print_time = parse_print_time(result.stdout)
    filament_g, filament_m = parse_filament_usage(result.stdout)

    return {
        "output_path": str(output_path),
        "file_size_bytes": output_path.stat().st_size,
        "quality": quality,
        "layer_height": actual_layer_height,
        "infill_percent": infill_percent,
        "support": support,
        "material": material.upper(),
        "print_time_estimate": print_time,
        "filament_used_g": filament_g,
        "filament_used_m": filament_m,
    }


def parse_print_time(output: str) -> str:
    """Parse print time estimate from OrcaSlicer output."""
    # Try to find time patterns like "2h 15m" or "1:30:00"
    patterns = [
        r"(\d+h\s*\d+m)",
        r"(\d+:\d+:\d+)",
        r"print time[:\s]+(\S+)",
    ]

    for pattern in patterns:
        if match := re.search(pattern, output, re.IGNORECASE):
            return match.group(1)

    return "Unknown"


def parse_filament_usage(output: str) -> tuple[float, float]:
    """
    Parse filament usage from OrcaSlicer output.

    Returns:
        Tuple of (grams, meters)
    """
    grams = 0.0
    meters = 0.0

    # Look for weight pattern
    if match := re.search(r"(\d+\.?\d*)\s*g", output, re.IGNORECASE):
        grams = float(match.group(1))

    # Look for length pattern
    if match := re.search(r"(\d+\.?\d*)\s*m(?:eter)?", output, re.IGNORECASE):
        meters = float(match.group(1))

    return grams, meters
