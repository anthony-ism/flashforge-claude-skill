# Slicing Integration

This document describes the STL to G-code slicing functionality and its current limitations.

## Overview

The `slice_stl` tool uses OrcaSlicer CLI to convert STL files to G-code for the FlashForge Adventurer 5M Pro printer.

## Current Status: Limited Functionality

**The OrcaSlicer CLI integration has known compatibility issues that prevent automated slicing.**

### The Problem

OrcaSlicer's CLI performs strict profile validation that fails with custom profiles:

```
[error] run 2310: process not compatible with printer.
```

This occurs because:

1. **Profile Inheritance** - OrcaSlicer profiles use an inheritance system (`inherits` field). Standalone profiles without proper inheritance chains fail validation.

2. **Compatibility Checks** - The `compatible_printers` field in process/filament profiles must exactly match the machine variant name, and additional internal checks occur.

3. **System Profile Bug** - OrcaSlicer's bundled FlashForge Adventurer 5M profiles have a validation error: they set `use_relative_e_distances: 1` but the `layer_change_gcode` is missing the required `G92 E0` command.

### Research Sources

- [OrcaSlicer CLI Discussion](https://github.com/SoftFever/OrcaSlicer/discussions/1603)
- [OrcaSlicer Profile Creation Guide](https://www.orcaslicer.com/wiki/developer-reference/How-to-create-profiles)
- [Compatible Printers Issue](https://github.com/SoftFever/OrcaSlicer/issues/3497)

## Workarounds

### Option 1: Use OrcaSlicer GUI (Recommended)

1. Open OrcaSlicer application
2. Import your STL file
3. Select "Flashforge Adventurer 5M Pro" printer
4. Choose "Generic PLA" filament
5. Click "Slice" and export G-code
6. Use `send_gcode_file` MCP tool to send to printer

### Option 2: Use 3MF Project File

Create a template 3MF project in OrcaSlicer GUI with correct settings:

```bash
# Slice a pre-configured 3MF via CLI
/Applications/OrcaSlicer.app/Contents/MacOS/OrcaSlicer \
  --slice 0 \
  --outputdir /output/path \
  project_with_settings.3mf
```

### Option 3: PrusaSlicer CLI

PrusaSlicer has better CLI documentation and uses simpler .ini config files:

```bash
prusa-slicer -g model.stl -o output.gcode --load config.ini
```

See [PrusaSlicer CLI Wiki](https://github.com/prusa3d/PrusaSlicer/wiki/Command-Line-Interface)

## Bundled Profiles

We include standalone profiles in `profiles/adventurer_5m_pro/` that attempt to work without inheritance:

- `machine_standalone.json` - Printer settings with G92 E0 fix
- `process_standalone.json` - Print quality settings
- `filament_standalone.json` - PLA filament settings

These profiles include all necessary settings inline but still fail OrcaSlicer's compatibility validation.

## Future Work

To fix automated slicing, we would need to either:

1. **Contribute upstream fix** - Submit PR to OrcaSlicer to fix the FlashForge profile `layer_change_gcode`

2. **Use OrcaSlicer's profile directory** - Install profiles into OrcaSlicer's user profile directory (`~/Library/Application Support/OrcaSlicer/`) with proper inheritance

3. **Alternative slicer** - Integrate with PrusaSlicer or CuraEngine CLI instead

## Manual Slicing Workflow

Until automated slicing is fixed, use this workflow:

```
STL file
    ↓
[OrcaSlicer GUI] - Manual slice
    ↓
G-code file
    ↓
[send_gcode_file MCP tool] - Automated upload
    ↓
Printer
```

The `send_gcode_file` tool works correctly and can upload G-code and start prints.
