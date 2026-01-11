# FlashForge Skill - Complementing Orca-Flashforge

## Purpose

This skill fills the gaps in the Orca-Flashforge workflow — specifically converting raster images (PNG/JPG) into 3D-printable formats. Orca-Flashforge handles SVG→3D natively and has AI-powered generative modeling, but lacks precise raster→3D conversion.

## What This Skill Does (That Orca-Flashforge Doesn't)

| Task | Orca-Flashforge | This Skill |
|------|-----------------|------------|
| PNG/JPG → precise STL extrusion | ❌ | ✅ |
| PNG/JPG → clean SVG (for import to Orca) | ❌ | ✅ |
| Photo → lithophane STL | ❌ | ✅ |
| Batch convert multiple icons | ❌ | ✅ |
| Heightmap relief from grayscale | ❌ | ✅ |
| Cookie cutter from outline | ❌ | ✅ |

## What This Skill Does NOT Do (Use Orca-Flashforge Instead)

- Slicing (STL → G-code) — use Orca-Flashforge
- Printer management/monitoring — use Orca-Flashforge or Flash Maker
- SVG → 3D — already built into Orca-Flashforge
- AI-generated 3D models from descriptions — use Orca-Flashforge's AI

---

## Skill Architecture

```
flashforge/
├── SKILL.md
├── scripts/
│   ├── png_to_stl.py          # Raster → 3D via contour extrusion
│   ├── png_to_svg.py          # Raster → SVG for Orca import
│   ├── lithophane.py          # Photo → lithophane STL
│   ├── heightmap_relief.py    # Grayscale → relief model
│   ├── cookie_cutter.py       # Outline → cookie cutter shape
│   └── batch_convert.py       # Process multiple files
├── references/
│   └── adventurer-5m-specs.md # Printer specs and best practices
└── assets/
    └── samples/               # Example inputs/outputs
```

---

## SKILL.md

```yaml
---
name: flashforge
description: Convert raster images (PNG, JPG) to 3D-printable STL files or clean SVGs for import into Orca-Flashforge. Use when the user wants to: (1) Turn a PNG/JPG icon, logo, or clipart into a precise 3D model, (2) Convert an image to SVG for Orca-Flashforge import, (3) Create lithophanes from photos, (4) Generate relief/heightmap models, (5) Make cookie cutters from shapes, (6) Batch process multiple images. Outputs are optimized for FlashForge Adventurer 5M/5M Pro (220x220x220mm build volume).
---

# FlashForge Image-to-3D Skill

This skill converts raster images to 3D-printable files, complementing Orca-Flashforge's native capabilities.

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

**How it works:**
1. Convert to grayscale
2. Threshold to binary (black/white)
3. Find contours using OpenCV
4. Convert contours to polygons
5. Extrude polygons to 3D mesh
6. Export as STL

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
- `--thickness`: Min/max thickness range in mm (default: 0.8-3.0)
- `--width`: Output width in mm (default: 100)
- `--positive`: Light areas thick (default is negative/traditional)
- `--frame`: Add decorative frame (none | simple | ornate)

**How it works:**
1. Convert to grayscale
2. Map brightness to thickness (dark = thin, light = thick)
3. Generate mesh surface
4. Add backing/frame if requested
5. Export STL

### Method 4: Heightmap Relief (Artistic)

Best for: Grayscale artwork, terrain, texture stamps

```bash
python scripts/heightmap_relief.py terrain.png output.stl --max-height 10
```

**Parameters:**
- `--max-height`: Maximum relief height in mm (default: 10)
- `--base-height`: Base plate thickness in mm (default: 2)
- `--smooth`: Gaussian blur passes (default: 1)
- `--resolution`: Output mesh resolution (default: 1.0)

### Method 5: Cookie Cutter

Best for: Shape outlines for baking cookie cutters

```bash
python scripts/cookie_cutter.py shape.png cutter.stl --depth 15
```

**Parameters:**
- `--depth`: Cutter depth in mm (default: 15)
- `--wall`: Wall thickness in mm (default: 1.2)
- `--handle`: Add handle on top (default: true)
- `--bevel`: Add cutting edge bevel (default: true)

### Method 6: Batch Processing

Process multiple files with same settings:

```bash
python scripts/batch_convert.py ./icons/ ./output/ --method contour --height 5
```

---

## FlashForge Adventurer 5M Pro Specs

Reference these when setting output dimensions:

| Spec | Value |
|------|-------|
| Build Volume | 220 x 220 x 220 mm |
| Max Print Speed | 600 mm/s |
| Layer Height | 0.1 - 0.4 mm |
| Nozzle Diameter | 0.4 mm (default) |
| Supported Materials | PLA, PETG, ABS, ASA, TPU |
| File Formats | STL, OBJ, 3MF |
| Bed Type | Flexible PEI |

**Recommended settings for converted models:**
- Layer height: 0.2mm for speed, 0.12mm for detail
- Infill: 15-20% for decorative, 40%+ for functional
- Supports: Usually not needed for extruded icons (flat bottom)
- First layer: 0.28mm at 20mm/s for adhesion

---

## Example Workflows

### "Convert this Mario icon to a 3D keychain"

1. Analyze image: PNG with clear edges, solid colors → use contour method
2. Run: `python scripts/png_to_stl.py mario.png mario.stl --height 4 --scale 40 --base 2`
3. Output: `mario.stl` (40mm wide, 4mm tall icon on 2mm base)
4. User imports STL into Orca-Flashforge for slicing

### "Make a lithophane of this family photo"

1. Analyze: Detailed photo → use lithophane method
2. Run: `python scripts/lithophane.py family.jpg family.stl --style flat --width 120 --frame simple`
3. Output: `family.stl` (120mm wide with frame)
4. Recommend: Print vertically, white PLA, 0.12mm layers, 100% infill

### "I have 20 game icons to convert"

1. Place all PNGs in a folder
2. Run: `python scripts/batch_convert.py ./game-icons/ ./stls/ --method contour --height 3 --scale 30`
3. Output: 20 STL files ready for batch printing

### "I want to use Orca's SVG import but only have PNG"

1. Run: `python scripts/png_to_svg.py logo.png logo.svg --smoothing medium`
2. Output: Clean SVG
3. Open Orca-Flashforge → Right-click workspace → Add Part → Select SVG
4. Orca handles the 3D extrusion natively

---

## Dependencies

```
numpy
opencv-python
Pillow
trimesh
numpy-stl
shapely
svgwrite
potrace  # For PNG→SVG tracing
```

Install: `pip install numpy opencv-python Pillow trimesh numpy-stl shapely svgwrite pypotrace --break-system-packages`

---

## Output Location

All generated files should be saved to the user's preferred location. Suggest:
- macOS: `~/Documents/3D Prints/` or Orca-Flashforge's default import folder
- The STL can then be opened directly in Orca-Flashforge for slicing
```

---

## Implementation Priority

Build scripts in this order:

1. **png_to_svg.py** — Most valuable, bridges the gap to Orca's native SVG support
2. **png_to_stl.py** — Core contour extrusion for icons/logos
3. **lithophane.py** — Popular use case, photo gifts
4. **cookie_cutter.py** — Fun, practical, good for kids
5. **heightmap_relief.py** — Artistic/terrain use cases
6. **batch_convert.py** — Power user feature

---

## Testing Checklist

- [ ] Simple black icon on white background
- [ ] Icon with transparency (PNG with alpha)
- [ ] Multi-color icon (should handle by converting to b/w)
- [ ] Photo with gradients (lithophane)
- [ ] Complex shape with holes (donut, letter O, etc.)
- [ ] Very small icon (should warn about printability)
- [ ] Very large icon (should warn about bed size)
- [ ] Batch of 10+ files
