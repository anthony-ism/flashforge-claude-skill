---
name: flashforge-figurine
version: 1.0.0
description: |
  Convert images (concept art, clay models, character designs) into 3D-printable STL files 
  for FlashForge Adventurer 5M/5M Pro printers. Supports both local GPU inference and cloud 
  API backends. Use when the user wants to:
  - Turn concept art or photos into 3D printable figurines
  - Convert clay model photos to STL files
  - Generate miniatures from single images
  - Batch process multiple images to 3D models
  
  Automatically detects available hardware and selects optimal backend, or allows explicit
  backend selection via flags.
dependencies:
  core:
    - numpy
    - opencv-python
    - Pillow
    - requests
    - trimesh
    - pymeshlab
    - numpy-stl
  local_gpu:
    - torch>=2.1.0
    - torchvision
    - transformers
    - huggingface_hub
  optional:
    - rembg  # Background removal
    - gradio # Web UI
---

# FlashForge Figurine Skill

Transform 2D images into 3D-printable figurines with intelligent backend selection.

## Quick Start

```bash
# Detect hardware and use best available backend
python generate.py input.png

# Explicit API mode (works on any hardware)
python generate.py input.png --backend api

# Explicit local mode (requires compatible GPU)
python generate.py input.png --backend local

# Specify output
python generate.py input.png -o my_figurine.stl
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        FLASHFORGE FIGURINE SKILL                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  INPUT                    GENERATION                      OUTPUT         │
│  ─────                    ──────────                      ──────         │
│                                                                          │
│  ┌──────────┐            ┌─────────────┐               ┌──────────┐    │
│  │  Image   │            │   Backend   │               │   STL    │    │
│  │  (PNG/   │ ────────── │   Router    │ ────────────► │  (print  │    │
│  │   JPG)   │            │             │               │   ready) │    │
│  └──────────┘            └──────┬──────┘               └──────────┘    │
│                                 │                                       │
│       ┌─────────────────────────┼─────────────────────────┐            │
│       │                         │                         │            │
│       ▼                         ▼                         ▼            │
│  ┌─────────┐             ┌─────────────┐           ┌──────────┐       │
│  │  LOCAL  │             │    API      │           │  HYBRID  │       │
│  │ TripoSR │             │  Tripo/     │           │  Local   │       │
│  │ Hunyuan │             │  Meshy      │           │  prep +  │       │
│  │ TRELLIS │             │             │           │  API gen │       │
│  └─────────┘             └─────────────┘           └──────────┘       │
│                                                                          │
├─────────────────────────────────────────────────────────────────────────┤
│                          POST-PROCESSING                                 │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────────────┐    │
│  │  Mesh    │ → │  Scale   │ → │  Add     │ → │  Export STL      │    │
│  │  Repair  │   │  & Orient│   │  Base    │   │  (print-ready)   │    │
│  └──────────┘   └──────────┘   └──────────┘   └──────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
```

## Backend Selection Logic

```python
def select_backend(requested: str = "auto") -> str:
    """
    Backend selection priority:
    1. If explicitly requested, use that (with validation)
    2. If 'auto', detect hardware and choose best option
    """
    if requested == "api":
        return "api"  # Always available
    
    if requested == "local":
        if not check_gpu_available():
            raise RuntimeError("Local backend requested but no compatible GPU found")
        return "local"
    
    # Auto-detection
    if requested == "auto":
        gpu_info = detect_gpu()
        
        if gpu_info["available"] and gpu_info["vram_gb"] >= 6:
            if gpu_info["compute_capability"] >= 7.5:
                return "local"  # Modern GPU, use local
            else:
                print(f"GPU {gpu_info['name']} has compute capability {gpu_info['compute_capability']}")
                print("This may not work with modern PyTorch. Falling back to API.")
                return "api"
        else:
            return "api"  # No GPU or insufficient VRAM
```

## Configuration

### Environment Variables

```bash
# API Keys (required for API backend)
export TRIPO_API_KEY="your_tripo_key"
export MESHY_API_KEY="your_meshy_key"

# Backend preference
export FIGURINE_BACKEND="auto"  # auto | local | api

# Local model selection
export LOCAL_MODEL="triposr"  # triposr | hunyuan | trellis
```

### Config File (~/.flashforge/config.yaml)

```yaml
# Backend configuration
backend:
  default: auto  # auto | local | api
  
  api:
    provider: tripo  # tripo | meshy
    tripo:
      api_key: ${TRIPO_API_KEY}
      model: v2.5
      texture: standard  # none | standard | hd
    meshy:
      api_key: ${MESHY_API_KEY}
      style: realistic
      
  local:
    model: triposr  # triposr | hunyuan | trellis
    device: cuda:0  # cuda:0 | cuda:1 | cpu
    dtype: float16  # float16 | float32
    
# Processing options
preprocessing:
  remove_background: true
  convert_to_matcap: false
  target_resolution: 1024
  
# Output options
output:
  format: stl  # stl | obj | glb
  scale_mm: 80  # Target height in mm
  add_base: true
  base_height_mm: 2
  hollow: false
  wall_thickness_mm: 2
  
# Printer profile
printer:
  name: "FlashForge Adventurer 5M Pro"
  build_volume:
    x: 220
    y: 220
    z: 220
  nozzle_diameter: 0.4
```

## CLI Reference

### Basic Usage

```bash
# Simple generation (auto backend)
python generate.py input.png

# With output path
python generate.py input.png -o output.stl

# Batch processing
python generate.py ./images/*.png -o ./output/
```

### Backend Selection

```bash
# Force API backend
python generate.py input.png --backend api

# Force local backend
python generate.py input.png --backend local

# Specify API provider
python generate.py input.png --backend api --provider tripo
python generate.py input.png --backend api --provider meshy

# Specify local model
python generate.py input.png --backend local --model triposr
python generate.py input.png --backend local --model hunyuan
python generate.py input.png --backend local --model trellis  # Requires 24GB+ VRAM
```

### Preprocessing Options

```bash
# Remove background before processing
python generate.py input.png --remove-bg

# Convert to matcap (gray clay look) for better geometry
python generate.py input.png --matcap

# Skip preprocessing
python generate.py input.png --no-preprocess
```

### Output Options

```bash
# Set scale (height in mm)
python generate.py input.png --scale 100

# Add base for printing
python generate.py input.png --add-base --base-height 3

# Hollow out (saves filament)
python generate.py input.png --hollow --wall-thickness 2

# Output format
python generate.py input.png --format glb  # Keep textures
python generate.py input.png --format stl  # Print-ready
```

### Advanced

```bash
# Verbose output with timing
python generate.py input.png -v

# Dry run (show what would happen)
python generate.py input.png --dry-run

# Generate multi-view before 3D (better quality)
python generate.py input.png --generate-views

# Keep intermediate files
python generate.py input.png --keep-intermediates
```

## Python API

### Basic Usage

```python
from flashforge_figurine import FigurineGenerator

# Auto backend selection
generator = FigurineGenerator()
mesh = generator.generate("input.png")
mesh.export("output.stl")

# Explicit backend
generator = FigurineGenerator(backend="api", provider="tripo")
mesh = generator.generate("input.png")
```

### Full Pipeline Control

```python
from flashforge_figurine import (
    FigurineGenerator,
    ImagePreprocessor,
    MeshPostprocessor,
    PrintOptimizer
)

# Step 1: Preprocess image
preprocessor = ImagePreprocessor()
clean_image = preprocessor.process(
    "input.png",
    remove_background=True,
    convert_to_matcap=True,
    target_resolution=1024
)

# Step 2: Generate 3D mesh
generator = FigurineGenerator(backend="auto")
raw_mesh = generator.generate(clean_image)

# Step 3: Post-process mesh
postprocessor = MeshPostprocessor()
fixed_mesh = postprocessor.process(
    raw_mesh,
    repair=True,
    smooth=False,
    decimate_ratio=0.8
)

# Step 4: Optimize for printing
optimizer = PrintOptimizer(printer="adventurer_5m_pro")
print_mesh = optimizer.process(
    fixed_mesh,
    target_height_mm=80,
    add_base=True,
    base_height_mm=2,
    hollow=False
)

# Export
print_mesh.export("figurine_print_ready.stl")
```

### Batch Processing

```python
from flashforge_figurine import BatchProcessor

processor = BatchProcessor(
    backend="api",  # Faster for batches (parallel requests)
    max_concurrent=5
)

results = processor.process_folder(
    input_dir="./images",
    output_dir="./stls",
    scale_mm=60,
    add_base=True
)

for result in results:
    print(f"{result.input} -> {result.output} ({result.status})")
```

## Backend Details

### Local: TripoSR

**Requirements:** 6GB+ VRAM, CUDA compute capability 7.5+

```python
# TripoSR is fastest and most reliable for local inference
generator = FigurineGenerator(backend="local", model="triposr")
```

**Pros:**
- Fast (~1 second inference)
- Low VRAM requirement
- MIT license
- Well-tested

**Cons:**
- Vertex colors only (no UV textures)
- Older model architecture
- Less detail than newer models

### Local: Hunyuan3D

**Requirements:** 6GB+ VRAM (shape), 16GB+ (shape+texture)

```python
# Hunyuan3D for better quality
generator = FigurineGenerator(backend="local", model="hunyuan")
```

**Pros:**
- PBR textures
- Better geometry detail
- Commercial use OK
- Training code available

**Cons:**
- Slower than TripoSR
- Higher VRAM for textures
- More complex setup

### Local: TRELLIS.2

**Requirements:** 24GB+ VRAM

```python
# TRELLIS.2 for best quality (requires RTX 4090/A100)
generator = FigurineGenerator(backend="local", model="trellis")
```

**Pros:**
- Best quality output
- PBR materials including transparency
- Handles complex topology
- MIT license

**Cons:**
- Very high VRAM requirement
- Slower inference
- Linux only

### API: Tripo

```python
generator = FigurineGenerator(
    backend="api",
    provider="tripo",
    api_key="your_key"  # Or use TRIPO_API_KEY env var
)
```

**Pricing:**
- $0.20/model (no texture)
- $0.30/model (standard texture)
- $0.40/model (HD texture)
- Free tier: 300 credits/month

### API: Meshy

```python
generator = FigurineGenerator(
    backend="api", 
    provider="meshy",
    api_key="your_key"
)
```

**Pricing:**
- Free tier: Limited daily generations
- Pro: $9.99/month

## Hardware Compatibility

### GPU Support Matrix

| GPU | VRAM | Compute | TripoSR | Hunyuan | TRELLIS | Notes |
|-----|------|---------|---------|---------|---------|-------|
| GTX 1080 Ti | 11GB | 6.1 | ⚠️ | ⚠️ | ❌ | Needs PyTorch 2.1, may fail |
| RTX 2080 Ti | 11GB | 7.5 | ✅ | ✅ | ❌ | Good budget option |
| RTX 3060 | 12GB | 8.6 | ✅ | ✅ | ❌ | Best value |
| RTX 3080 | 10GB | 8.6 | ✅ | ✅ | ❌ | Fast |
| RTX 3090 | 24GB | 8.6 | ✅ | ✅ | ✅ | Recommended |
| RTX 4090 | 24GB | 8.9 | ✅ | ✅ | ✅ | Best performance |
| Apple M1-M4 | Unified | N/A | ❌ | ❌ | ❌ | Use API backend |

### Fallback Behavior

```
┌─────────────────────────────────────────────────────────────┐
│  HARDWARE DETECTION FLOW                                     │
│                                                              │
│  Start                                                       │
│    │                                                         │
│    ▼                                                         │
│  ┌─────────────────┐                                        │
│  │ Check for CUDA  │                                        │
│  └────────┬────────┘                                        │
│           │                                                  │
│     ┌─────┴─────┐                                           │
│     │           │                                            │
│    Yes          No ──────────────────────┐                  │
│     │                                     │                  │
│     ▼                                     │                  │
│  ┌─────────────────┐                     │                  │
│  │ Check compute   │                     │                  │
│  │ capability      │                     │                  │
│  └────────┬────────┘                     │                  │
│           │                               │                  │
│     ┌─────┴─────┐                        │                  │
│     │           │                         │                  │
│   ≥7.5        <7.5                       │                  │
│     │           │                         │                  │
│     ▼           ▼                         │                  │
│  ┌────────┐  ┌─────────────────┐         │                  │
│  │ Check  │  │ Warn: Old GPU   │         │                  │
│  │ VRAM   │  │ Try PyTorch 2.1 │         │                  │
│  └───┬────┘  │ or use API      │         │                  │
│      │       └────────┬────────┘         │                  │
│   ┌──┴──┐             │                  │                  │
│   │     │             │                  │                  │
│ ≥6GB  <6GB           │                  │                  │
│   │     │             │                  │                  │
│   ▼     ▼             ▼                  ▼                  │
│ LOCAL  ─────────────► API ◄──────────────                   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## File Structure

```
flashforge-figurine/
├── SKILL.md                    # This file
├── generate.py                 # Main CLI entry point
├── setup.py                    # Package installation
├── requirements.txt            # Core dependencies
├── requirements-local.txt      # Local GPU dependencies
│
├── src/
│   ├── __init__.py
│   ├── generator.py            # Main FigurineGenerator class
│   ├── config.py               # Configuration management
│   │
│   ├── backends/
│   │   ├── __init__.py
│   │   ├── base.py             # Abstract backend interface
│   │   ├── router.py           # Backend selection logic
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── tripo.py        # Tripo API client
│   │   │   └── meshy.py        # Meshy API client
│   │   └── local/
│   │       ├── __init__.py
│   │       ├── triposr.py      # TripoSR wrapper
│   │       ├── hunyuan.py      # Hunyuan3D wrapper
│   │       └── trellis.py      # TRELLIS.2 wrapper
│   │
│   ├── preprocessing/
│   │   ├── __init__.py
│   │   ├── background.py       # Background removal
│   │   ├── matcap.py           # Matcap conversion
│   │   └── enhance.py          # Image enhancement
│   │
│   ├── postprocessing/
│   │   ├── __init__.py
│   │   ├── repair.py           # Mesh repair (manifold, holes)
│   │   ├── optimize.py         # Decimation, smoothing
│   │   └── print_prep.py       # Add base, hollow, orient
│   │
│   └── utils/
│       ├── __init__.py
│       ├── hardware.py         # GPU detection
│       ├── formats.py          # File format conversions
│       └── validation.py       # Input/output validation
│
├── tests/
│   ├── test_backends.py
│   ├── test_preprocessing.py
│   └── test_postprocessing.py
│
└── examples/
    ├── basic_usage.py
    ├── batch_processing.py
    └── custom_pipeline.py
```

## Error Handling

### Common Errors

```python
# GPU not available
FigurineError: No compatible GPU found. Use --backend api or install CUDA.

# Insufficient VRAM
FigurineError: Model 'trellis' requires 24GB VRAM, but only 11GB available.
              Use --model triposr or --backend api instead.

# API key missing
FigurineError: Tripo API key not found. Set TRIPO_API_KEY environment variable
              or pass api_key parameter.

# Old GPU
FigurineWarning: GTX 1080 Ti (compute 6.1) may not work with current PyTorch.
                Attempting with PyTorch 2.1 compatibility mode...
                If this fails, use --backend api.

# Mesh repair failed
FigurineWarning: Mesh has non-manifold edges. Attempting repair...
FigurineError: Could not repair mesh. Try --no-repair to skip, but print may fail.
```

### Graceful Degradation

```python
# The skill automatically falls back when issues occur:

1. Local GPU fails → Offer to retry with API
2. High VRAM model fails → Suggest lower VRAM model
3. Mesh repair fails → Export anyway with warning
4. API rate limited → Queue and retry with backoff
```

## Examples

### Example 1: Clay Robot Photo → Print

```bash
# Your clay robot image
python generate.py clay_robot.png \
    --remove-bg \
    --scale 80 \
    --add-base \
    -o robot.stl

# Output: robot.stl (ready for Orca-Flashforge)
```

### Example 2: Concept Art → Miniature

```bash
# Character concept art
python generate.py warrior_concept.jpg \
    --matcap \
    --scale 50 \
    --backend api \
    --provider tripo \
    -o warrior_mini.stl
```

### Example 3: Batch Game Icons

```bash
# Process entire folder
python generate.py ./game_icons/*.png \
    --backend api \
    --scale 40 \
    --add-base \
    -o ./miniatures/
```

### Example 4: High Quality with TRELLIS

```bash
# Best quality (requires 24GB GPU)
python generate.py detailed_character.png \
    --backend local \
    --model trellis \
    --scale 120 \
    --format glb \
    -o character.glb
```

## Print Settings (Orca-Flashforge)

After generating STL, import into Orca-Flashforge with these recommended settings:

### Figurines (PLA)

| Setting | Value |
|---------|-------|
| Layer Height | 0.12mm |
| Infill | 15-20% |
| Supports | Tree (auto) |
| Speed | 80-120mm/s |
| Temperature | 200-210°C |

### Miniatures <50mm (PLA)

| Setting | Value |
|---------|-------|
| Layer Height | 0.08mm |
| Infill | 100% (solid) |
| Supports | Tree (everywhere) |
| Speed | 40-60mm/s |
| Temperature | 195-205°C |

## Troubleshooting

### "CUDA out of memory"

```bash
# Try smaller model
python generate.py input.png --model triposr

# Or reduce resolution
python generate.py input.png --resolution 512

# Or use API
python generate.py input.png --backend api
```

### "No kernel image available" (GTX 1080 Ti)

```bash
# Install older PyTorch
pip install torch==2.1.2 torchvision==0.16.2 --index-url https://download.pytorch.org/whl/cu118

# Or just use API
python generate.py input.png --backend api
```

### "Mesh not watertight"

```bash
# More aggressive repair
python generate.py input.png --repair-aggressive

# Or skip repair (may cause print issues)
python generate.py input.png --no-repair
```

### Poor geometry quality

```bash
# Try matcap preprocessing
python generate.py input.png --matcap

# Or generate multi-view first
python generate.py input.png --generate-views

# Or use higher quality model
python generate.py input.png --model hunyuan --backend local
```
