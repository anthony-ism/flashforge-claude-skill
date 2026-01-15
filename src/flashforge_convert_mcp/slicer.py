"""
OrcaSlicer integration for FlashForge MCP.

Handles:
- OrcaSlicer executable detection
- Profile management
- G-code generation from STL files
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
    Get the OrcaSlicer system profiles directory for FlashForge.

    Checks for user override via ORCASLICER_PROFILES_DIR environment variable,
    otherwise uses OrcaSlicer's built-in system profiles.
    """
    # Check for user override
    if profiles_dir := os.environ.get("ORCASLICER_PROFILES_DIR"):
        return Path(profiles_dir)

    # Use OrcaSlicer's built-in FlashForge profiles
    if sys.platform == "darwin":
        return Path("/Applications/OrcaSlicer.app/Contents/Resources/profiles/Flashforge")
    elif sys.platform == "win32":
        return Path(r"C:\Program Files\OrcaSlicer\resources\profiles\Flashforge")
    else:
        # Linux - check common paths
        for path in [
            Path("/opt/OrcaSlicer/resources/profiles/Flashforge"),
            Path("/usr/share/OrcaSlicer/resources/profiles/Flashforge"),
        ]:
            if path.exists():
                return path

    # Fallback to bundled profiles
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

    # Map quality to OrcaSlicer system profile names
    # These match the built-in Flashforge Adventurer 5M Pro profiles
    quality_to_process = {
        "draft": "0.24mm Draft @Flashforge AD5M Pro 0.4 Nozzle.json",
        "standard": "0.20mm Standard @Flashforge AD5M Pro 0.4 Nozzle.json",
        "fine": "0.12mm Fine @Flashforge AD5M Pro 0.4 Nozzle.json",
    }

    material_to_filament = {
        "pla": "Flashforge Generic PLA.json",
        "petg": "Flashforge Generic PETG.json",
    }

    printer_profile = profiles_dir / "machine" / "Flashforge Adventurer 5M Pro 0.4 Nozzle.json"
    process_profile = profiles_dir / "process" / quality_to_process.get(quality, quality_to_process["standard"])
    filament_profile = profiles_dir / "filament" / material_to_filament.get(material, material_to_filament["pla"])

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
