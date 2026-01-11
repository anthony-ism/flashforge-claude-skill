---
name: flashforge
description: Convert raster images (PNG, JPG) to 3D-printable STL files or clean SVGs for import into Orca-Flashforge. Use when the user wants to: (1) Turn a PNG/JPG icon, logo, or clipart into a precise 3D model, (2) Convert an image to SVG for Orca-Flashforge import, (3) Create lithophanes from photos, (4) Generate relief/heightmap models, (5) Make cookie cutters from shapes, (6) Batch process multiple images. Outputs are optimized for FlashForge Adventurer 5M/5M Pro (220x220x220mm build volume).
---

# FlashForge Image-to-3D Skill

This skill converts raster images to 3D-printable files, complementing Orca-Flashforge's native capabilities.

## What This Skill Does (That Orca-Flashforge Doesn't)

| Task | Orca-Flashforge | This Skill |
|------|-----------------|------------|
| PNG/JPG → precise STL extrusion | ❌ | ✅ |
| PNG/JPG → clean SVG (for import to Orca) | ❌ | ✅ |
| Photo → lithophane STL | ❌ | ✅ |
| Batch convert multiple icons | ❌ | ✅ |
| Heightmap relief from grayscale | ❌ | ✅ |
| Cookie cutter from outline | ❌ | ✅ |

## What to Use Orca-Flashforge For

- Slicing (STL → G-code)
- Printer management/monitoring
- SVG → 3D (already built-in)
- AI-generated 3D models from descriptions

## Workflow Decision Tree

```
User has an image they want to 3D print
                │
                ▼
    ┌─────────────────────┐
    │ What format is it?  │
    └─────────────────────┘
           │
     ┌─────┴─────┐
     ▼           ▼
   SVG        PNG/JPG
     │           │
     ▼           ▼
Use Orca     Use this skill
directly     ─────────────────┐
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
        Want precise shape?           Want artistic interpretation?
              │                               │
              ▼                               ▼
        Use this skill                 Use Orca-Flashforge AI
        (contour/heightmap)            (generative modeling)
```

## Conversion Methods

### Method 1: Contour Extrusion (Icons, Logos, Clipart)

Best for: Simple shapes with clear edges, solid colors, icons, logos

```bash
python scripts/png_to_stl.py input.png output.stl --height 5 --scale 50
```

**Parameters:**
- `--height`: Extrusion height in mm (default: 5)
- `--scale`: Output width in mm (default: fit to 100mm)
- `--threshold`: Binarization threshold 0-255 (default: 127)
- `--invert`: Swap foreground/background
- `--base`: Add base plate thickness in mm (default: 0)

### Method 2: SVG Conversion (For Orca-Flashforge Import)

Best for: When you want to use Orca's native SVG→3D, but start with PNG

```bash
python scripts/png_to_svg.py input.png output.svg --smoothing medium
```

**Parameters:**
- `--smoothing`: none | low | medium | high (curve smoothing)
- `--colors`: Number of colors to trace (default: 2 for b/w)
- `--simplify`: Path simplification tolerance (default: 2.0)

**Output:** Clean SVG file ready for Orca-Flashforge → Right-click → Add Part

### Method 3: Lithophane (Photos)

Best for: Photos, portraits, detailed grayscale images

```bash
python scripts/lithophane.py photo.jpg output.stl --style flat --thickness 3
```

**Parameters:**
- `--style`: flat | curved | cylindrical | heart
- `--thickness`: Max thickness in mm (default: 3.0)
- `--width`: Output width in mm (default: 100)
- `--positive`: Light areas thick (default is negative/traditional)
- `--frame`: Add decorative frame (none | simple)

### Method 4: Heightmap Relief (Artistic)

Best for: Grayscale artwork, terrain, texture stamps

```bash
python scripts/heightmap_relief.py terrain.png output.stl --max-height 10
```

**Parameters:**
- `--max-height`: Maximum relief height in mm (default: 10)
- `--base-height`: Base plate thickness in mm (default: 2)
- `--smooth`: Gaussian blur passes (default: 1)

### Method 5: Cookie Cutter

Best for: Shape outlines for baking cookie cutters

```bash
python scripts/cookie_cutter.py shape.png cutter.stl --depth 15
```

**Parameters:**
- `--depth`: Cutter depth in mm (default: 15)
- `--wall`: Wall thickness in mm (default: 1.2)
- `--handle`: Add handle on top (default: true)

### Method 6: Batch Processing

Process multiple files with same settings:

```bash
python scripts/batch_convert.py ./icons/ ./output/ --method contour --height 5
```

## FlashForge Adventurer 5M Specs

| Spec | Value |
|------|-------|
| Build Volume | 220 x 220 x 220 mm |
| Max Print Speed | 600 mm/s |
| Layer Height | 0.1 - 0.4 mm |
| Nozzle Diameter | 0.4 mm (default) |
| Supported Materials | PLA, PETG, ABS, ASA, TPU |
| File Formats | STL, OBJ, 3MF |

**Recommended settings for converted models:**
- Layer height: 0.2mm for speed, 0.12mm for detail
- Infill: 15-20% for decorative, 40%+ for functional
- Supports: Usually not needed for extruded icons (flat bottom)

## Dependencies

```
numpy
opencv-python
Pillow
trimesh
numpy-stl
shapely
svgwrite
mapbox-earcut
```
