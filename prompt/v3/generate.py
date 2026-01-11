#!/usr/bin/env python3
"""
FlashForge Figurine Generator - CLI Entry Point

Generate 3D-printable figurines from images with automatic backend selection.

Usage:
    python generate.py input.png                          # Auto-detect backend
    python generate.py input.png --backend api            # Force API
    python generate.py input.png --backend local          # Force local GPU
    python generate.py input.png -o output.stl --scale 80 # Custom output
"""

import argparse
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="Generate 3D-printable figurines from images",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s photo.png                        Generate with auto-detected backend
  %(prog)s photo.png --backend api          Use Tripo/Meshy cloud API
  %(prog)s photo.png --backend local        Use local GPU (TripoSR)
  %(prog)s photo.png -o figure.stl          Specify output file
  %(prog)s photo.png --scale 100            Set height to 100mm
  %(prog)s ./images/*.png -o ./output/      Batch process folder
  %(prog)s photo.png --remove-bg --matcap   Preprocess for better results
  %(prog)s --detect-hardware                Show GPU capabilities
        """
    )
    
    # Input/Output
    parser.add_argument(
        "input",
        nargs="*",
        help="Input image(s) or glob pattern"
    )
    parser.add_argument(
        "-o", "--output",
        help="Output file or directory"
    )
    parser.add_argument(
        "--format",
        choices=["stl", "obj", "glb"],
        default="stl",
        help="Output format (default: stl)"
    )
    
    # Backend selection
    backend_group = parser.add_argument_group("Backend Options")
    backend_group.add_argument(
        "--backend",
        choices=["auto", "local", "api"],
        default="auto",
        help="Backend selection (default: auto)"
    )
    backend_group.add_argument(
        "--model",
        choices=["triposr", "hunyuan", "trellis"],
        help="Local model to use (default: auto-select based on VRAM)"
    )
    backend_group.add_argument(
        "--provider",
        choices=["tripo", "meshy"],
        default="tripo",
        help="API provider (default: tripo)"
    )
    backend_group.add_argument(
        "--api-key",
        help="API key (or use TRIPO_API_KEY/MESHY_API_KEY env var)"
    )
    
    # Preprocessing
    preprocess_group = parser.add_argument_group("Preprocessing")
    preprocess_group.add_argument(
        "--remove-bg",
        action="store_true",
        help="Remove background before processing"
    )
    preprocess_group.add_argument(
        "--matcap",
        action="store_true",
        help="Convert to matcap (gray clay) for better geometry"
    )
    preprocess_group.add_argument(
        "--no-preprocess",
        action="store_true",
        help="Skip all preprocessing"
    )
    
    # Output options
    output_group = parser.add_argument_group("Output Options")
    output_group.add_argument(
        "--scale",
        type=float,
        default=80,
        help="Target height in mm (default: 80)"
    )
    output_group.add_argument(
        "--add-base",
        action="store_true",
        default=True,
        help="Add flat base for printing (default: True)"
    )
    output_group.add_argument(
        "--no-base",
        action="store_true",
        help="Don't add base"
    )
    output_group.add_argument(
        "--base-height",
        type=float,
        default=2,
        help="Base height in mm (default: 2)"
    )
    output_group.add_argument(
        "--hollow",
        action="store_true",
        help="Hollow out model to save filament"
    )
    output_group.add_argument(
        "--wall-thickness",
        type=float,
        default=2,
        help="Wall thickness if hollow, in mm (default: 2)"
    )
    
    # Mesh processing
    mesh_group = parser.add_argument_group("Mesh Processing")
    mesh_group.add_argument(
        "--no-repair",
        action="store_true",
        help="Skip mesh repair"
    )
    mesh_group.add_argument(
        "--repair-aggressive",
        action="store_true",
        help="Use aggressive mesh repair"
    )
    
    # Utility
    util_group = parser.add_argument_group("Utility")
    util_group.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output"
    )
    util_group.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would happen without generating"
    )
    util_group.add_argument(
        "--detect-hardware",
        action="store_true",
        help="Detect and display hardware capabilities"
    )
    util_group.add_argument(
        "--version",
        action="version",
        version="%(prog)s 1.0.0"
    )
    
    args = parser.parse_args()
    
    # Handle hardware detection
    if args.detect_hardware:
        detect_hardware()
        return 0
    
    # Validate inputs
    if not args.input:
        parser.error("Input image(s) required. Use --detect-hardware to check GPU.")
    
    # Expand glob patterns
    input_files = []
    for pattern in args.input:
        path = Path(pattern)
        if "*" in pattern:
            input_files.extend(path.parent.glob(path.name))
        elif path.exists():
            input_files.append(path)
        else:
            print(f"Warning: File not found: {pattern}", file=sys.stderr)
    
    if not input_files:
        print("Error: No valid input files found", file=sys.stderr)
        return 1
    
    # Determine output
    if len(input_files) > 1:
        # Batch mode - output must be directory
        if args.output:
            output_dir = Path(args.output)
            output_dir.mkdir(parents=True, exist_ok=True)
        else:
            output_dir = Path("./output")
            output_dir.mkdir(exist_ok=True)
    else:
        output_dir = None
    
    # Dry run
    if args.dry_run:
        print_dry_run(args, input_files, output_dir)
        return 0
    
    # Initialize generator
    try:
        from src.generator import FigurineGenerator
        
        generator = FigurineGenerator(
            backend=args.backend,
            model=args.model,
            provider=args.provider,
            api_key=args.api_key,
            verbose=args.verbose
        )
    except Exception as e:
        print(f"Error initializing generator: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1
    
    # Process files
    success_count = 0
    fail_count = 0
    
    for input_file in input_files:
        # Determine output path
        if output_dir:
            output_path = output_dir / f"{input_file.stem}.{args.format}"
        elif args.output:
            output_path = Path(args.output)
        else:
            output_path = input_file.with_suffix(f".{args.format}")
        
        if args.verbose:
            print(f"\nProcessing: {input_file}")
            print(f"Output: {output_path}")
        
        # Generate
        result = generator.generate(
            image_path=input_file,
            output_path=output_path,
            remove_background=args.remove_bg and not args.no_preprocess,
            convert_to_matcap=args.matcap and not args.no_preprocess,
            scale_mm=args.scale,
            add_base=args.add_base and not args.no_base,
            base_height_mm=args.base_height,
            hollow=args.hollow,
            wall_thickness_mm=args.wall_thickness,
            repair_mesh=not args.no_repair,
            output_format=args.format
        )
        
        if result.success:
            success_count += 1
            if not args.verbose:
                print(f"✓ {input_file.name} -> {output_path.name}")
            
            for warning in result.warnings:
                print(f"  Warning: {warning}")
        else:
            fail_count += 1
            print(f"✗ {input_file.name}: {result.error}", file=sys.stderr)
    
    # Summary
    if len(input_files) > 1:
        print(f"\nProcessed {len(input_files)} files: {success_count} success, {fail_count} failed")
    
    return 0 if fail_count == 0 else 1


def detect_hardware():
    """Detect and display hardware capabilities."""
    try:
        from src.utils.hardware import detect_gpu, print_hardware_summary, check_pytorch_cuda_compatibility
        
        gpu_info = detect_gpu()
        print_hardware_summary(gpu_info)
        
        if gpu_info.available:
            print("\nPyTorch Compatibility Check:")
            compat = check_pytorch_cuda_compatibility(gpu_info)
            
            if compat["compatible"]:
                print("  ✓ PyTorch CUDA is working correctly")
            else:
                for warning in compat["warnings"]:
                    print(f"  ⚠ {warning}")
                for rec in compat["recommendations"]:
                    print(f"    → {rec}")
                    
    except ImportError as e:
        print(f"Error importing modules: {e}")
        print("\nBasic hardware check:")
        
        # Fallback basic check
        try:
            import torch
            print(f"  PyTorch version: {torch.__version__}")
            print(f"  CUDA available: {torch.cuda.is_available()}")
            if torch.cuda.is_available():
                print(f"  CUDA device: {torch.cuda.get_device_name(0)}")
        except ImportError:
            print("  PyTorch not installed")


def print_dry_run(args, input_files, output_dir):
    """Print what would happen without executing."""
    print("=" * 60)
    print("DRY RUN - No files will be generated")
    print("=" * 60)
    print(f"\nBackend: {args.backend}")
    if args.backend == "local" or args.backend == "auto":
        print(f"Local model: {args.model or 'auto-select'}")
    if args.backend == "api" or args.backend == "auto":
        print(f"API provider: {args.provider}")
    
    print(f"\nPreprocessing:")
    print(f"  Remove background: {args.remove_bg and not args.no_preprocess}")
    print(f"  Convert to matcap: {args.matcap and not args.no_preprocess}")
    
    print(f"\nOutput settings:")
    print(f"  Format: {args.format}")
    print(f"  Scale: {args.scale}mm")
    print(f"  Add base: {args.add_base and not args.no_base}")
    print(f"  Hollow: {args.hollow}")
    
    print(f"\nFiles to process ({len(input_files)}):")
    for f in input_files[:10]:
        if output_dir:
            out = output_dir / f"{f.stem}.{args.format}"
        elif args.output:
            out = Path(args.output)
        else:
            out = f.with_suffix(f".{args.format}")
        print(f"  {f} -> {out}")
    
    if len(input_files) > 10:
        print(f"  ... and {len(input_files) - 10} more")
    
    print("\nRun without --dry-run to generate files.")


if __name__ == "__main__":
    sys.exit(main())
