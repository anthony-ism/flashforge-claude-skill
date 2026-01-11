# FlashForge 2D-to-3D Skill Creation Prompt

## Context for Claude Code

You are building a Claude skill called `flashforge` that converts 2D images (clipart, icons, lo-fi PNGs) into 3D printable STL files optimized for FDM printing on a FlashForge Adventurer 5M printer.

## Goal

Create a skill that enables Claude to:
1. Accept 2D image files (PNG, JPG, SVG)
2. Process them into 3D models using Python scripts
3. Generate STL files ready for slicing and printing
4. Provide sensible defaults for the FlashForge Adventurer 5M (220x220x220mm build volume)

## Skill Architecture

```
flashforge/
├── SKILL.md                    # Main skill definition
├── scripts/
│   ├── heightmap_to_stl.py     # Convert images via heightmap/brightness extrusion
│   ├── contour_to_stl.py       # Convert images via edge detection + extrusion
│   ├── svg_to_stl.py           # Convert SVG paths to 3D models
│   └── utils.py                # Shared utilities (image preprocessing, STL validation)
├── references/
│   └── printing-guidelines.md  # FlashForge-specific print settings and tips
└── assets/
    └── sample-outputs/         # Example STL outputs for reference
```

## SKILL.md Frontmatter

```yaml
---
name: flashforge
description: Convert 2D images (PNG, JPG, SVG, clipart, icons, logos) into 3D printable STL files for FDM printing. Use when the user wants to: (1) Turn a 2D image, icon, or logo into a 3D print, (2) Create lithophanes from photos, (3) Generate relief models from artwork, (4) Prepare files for FlashForge or other FDM 3D printers. Supports heightmap extrusion, contour tracing, and SVG path extrusion methods.
---
```

## Core Conversion Methods

### Method 1: Heightmap Extrusion (Best for: photos, grayscale art, lithophanes)

**How it works:**
- Convert image to grayscale
- Map pixel brightness (0-255) to Z-height values
- Generate mesh from height grid
- Export as STL

**Python libraries:** `numpy`, `numpy-stl`, `Pillow`, `trimesh`

**Example code pattern:**
```python
import numpy as np
from PIL import Image
from stl import mesh

def heightmap_to_stl(image_path, output_path, max_height=10, base_height=2, scale=1.0):
    """
    Convert image to 3D STL using heightmap approach.
    
    Args:
        image_path: Path to input image
        output_path: Path for output STL
        max_height: Maximum extrusion height in mm
        base_height: Base plate thickness in mm
        scale: Scale factor for X/Y dimensions
    """
    img = Image.open(image_path).convert('L')  # Grayscale
    img_array = np.array(img)
    
    # Normalize to height values
    heights = (img_array / 255.0) * max_height + base_height
    
    # Generate mesh vertices and faces
    # ... mesh generation logic ...
    
    # Export STL
    model.save(output_path)
```

### Method 2: Contour Extrusion (Best for: icons, logos, clipart with clear edges)

**How it works:**
- Detect edges/contours using OpenCV
- Convert contours to 2D polygons
- Extrude polygons linearly to create 3D shapes
- Export as STL

**Python libraries:** `opencv-python`, `numpy`, `trimesh`, `shapely`

**Example code pattern:**
```python
import cv2
import numpy as np
import trimesh
from shapely.geometry import Polygon

def contour_to_stl(image_path, output_path, height=5, threshold=127):
    """
    Convert image to 3D STL by detecting contours and extruding.
    
    Args:
        image_path: Path to input image
        output_path: Path for output STL  
        height: Extrusion height in mm
        threshold: Binarization threshold (0-255)
    """
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    _, binary = cv2.threshold(img, threshold, 255, cv2.THRESH_BINARY)
    
    contours, _ = cv2.findContours(binary, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    
    # Convert contours to 3D mesh
    # ... extrusion logic using trimesh ...
    
    mesh.export(output_path)
```

### Method 3: SVG Path Extrusion (Best for: vector graphics, clean line art)

**How it works:**
- Parse SVG path data
- Convert paths to 2D polygons
- Extrude with optional twist/scale
- Export as STL

**Python libraries:** `svgpathtools`, `numpy`, `trimesh`

**Alternative:** Generate OpenSCAD code and render via CLI:
```python
import subprocess

def svg_to_openscad(svg_path, output_scad, height=5):
    """Generate OpenSCAD code from SVG for extrusion."""
    scad_code = f'''
    linear_extrude(height={height})
        import("{svg_path}");
    '''
    with open(output_scad, 'w') as f:
        f.write(scad_code)
    
    # Render to STL
    subprocess.run(['openscad', '-o', output_scad.replace('.scad', '.stl'), output_scad])
```

## FlashForge Adventurer 5M Specific Settings

Include these in `references/printing-guidelines.md`:

- **Build volume:** 220 x 220 x 220 mm
- **Recommended layer height:** 0.2mm for speed, 0.12mm for detail
- **Infill:** 15-20% for decorative items, 40%+ for functional parts
- **Material:** PLA (195-210°C nozzle, 60°C bed)
- **Max print speed:** 600mm/s (but 150-200mm/s for quality)
- **File format:** STL (also supports 3MF, OBJ)

## Workflow in SKILL.md Body

```markdown
## Workflow

### 1. Analyze the Input Image
- Determine image type (photo, icon, logo, clipart)
- Check dimensions and recommend scaling
- Identify if solid regions or gradients

### 2. Select Conversion Method
| Image Type | Recommended Method |
|------------|-------------------|
| Photo/grayscale art | Heightmap extrusion |
| Icon/logo with solid colors | Contour extrusion |
| SVG/vector file | SVG path extrusion |
| Lo-fi pixel art | Heightmap with smoothing |

### 3. Configure Parameters
- **Size:** Scale to fit FlashForge bed (max 220mm)
- **Height:** Typical 3-10mm for decorative, up to 50mm for functional
- **Base:** Add 2mm base for bed adhesion
- **Resolution:** Balance detail vs. file size

### 4. Generate and Validate
- Run appropriate conversion script
- Check mesh is watertight (no holes)
- Preview dimensions
- Offer to adjust parameters

### 5. Output
- Save STL to user-specified location
- Provide print time estimate if possible
- Suggest slicer settings
```

## Implementation Notes

1. **Dependencies to declare:**
   ```yaml
   dependencies:
     - numpy
     - numpy-stl
     - Pillow
     - opencv-python
     - trimesh
     - shapely
     - svgpathtools
   ```

2. **Error handling:** Scripts should validate:
   - Input file exists and is valid image
   - Output mesh is manifold (printable)
   - Dimensions are within printer bounds

3. **Testing:** Create sample inputs in `assets/samples/` with expected outputs

## Example User Interactions

**User:** "Convert this Mario icon to a 3D print"
**Claude:** Uses contour_to_stl.py, sets height to 5mm, scales to 50mm width

**User:** "Make a lithophane from this family photo"
**Claude:** Uses heightmap_to_stl.py, inverts brightness, adds frame

**User:** "Turn my company logo SVG into a nameplate"
**Claude:** Uses svg_to_stl.py, adds text backing, scales to 100mm

---

## Next Steps

1. Initialize the skill using `scripts/init_skill.py flashforge --path /home/claude/flashforge`
2. Implement each conversion script with error handling
3. Write the SKILL.md body with clear workflow instructions
4. Test with sample images
5. Package with `scripts/package_skill.py`