#!/usr/bin/env python3
"""
FlashForge 3D Model Generator

Generate 3D-printable models from images using multiple methods:
- figurine: AI-powered 3D generation (requires Tripo API)
- flat: Contour extrusion for icons/logos
- relief: Heightmap extrusion for grayscale art
- lithophane: Photo to lithophane

Usage:
    python generate.py starman.png --figurine          # AI 3D figurine
    python generate.py logo.png --flat                 # Flat extrusion
    python generate.py art.png --relief                # Heightmap relief
    python generate.py photo.jpg --lithophane          # Lithophane
"""

import argparse
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="Generate 3D-printable models from images",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s starman.png --figurine              AI-generated 3D figurine
  %(prog)s starman.png --figurine --scale 60   60mm tall figurine
  %(prog)s logo.png --flat --height 5          5mm thick flat extrusion
  %(prog)s photo.jpg --lithophane              Photo to lithophane
  %(prog)s art.png --relief --max-height 10    Heightmap relief
        """
    )

    # Input/Output
    parser.add_argument("input", help="Input image file")
    parser.add_argument("-o", "--output", help="Output STL file (default: input_name.stl)")

    # Mode selection
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        "--figurine", action="store_true",
        help="AI 3D figurine (requires TRIPO_API_KEY)"
    )
    mode_group.add_argument(
        "--flat", action="store_true",
        help="Flat contour extrusion (icons, logos)"
    )
    mode_group.add_argument(
        "--relief", action="store_true",
        help="Heightmap relief (grayscale art)"
    )
    mode_group.add_argument(
        "--lithophane", action="store_true",
        help="Photo lithophane"
    )

    # Common options
    parser.add_argument(
        "--scale", type=float, default=80,
        help="Target height/width in mm (default: 80)"
    )
    parser.add_argument(
        "--no-base", action="store_true",
        help="Don't add base plate"
    )
    parser.add_argument(
        "--base-height", type=float, default=2,
        help="Base height in mm (default: 2)"
    )

    # Flat mode options
    parser.add_argument(
        "--height", type=float, default=5,
        help="[flat] Extrusion height in mm (default: 5)"
    )
    parser.add_argument(
        "--threshold", type=int, default=127,
        help="[flat] Binarization threshold 0-255 (default: 127)"
    )
    parser.add_argument(
        "--invert", action="store_true",
        help="[flat] Invert colors (extrude dark areas)"
    )

    # Relief mode options
    parser.add_argument(
        "--max-height", type=float, default=10,
        help="[relief] Maximum relief height in mm (default: 10)"
    )

    # Lithophane options
    parser.add_argument(
        "--thickness", type=float, default=3,
        help="[lithophane] Max thickness in mm (default: 3)"
    )
    parser.add_argument(
        "--frame", choices=["none", "simple"], default="none",
        help="[lithophane] Add frame (default: none)"
    )

    # Utility
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--version", action="version", version="%(prog)s 1.0.0")

    args = parser.parse_args()

    # Validate input
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input file not found: {args.input}", file=sys.stderr)
        return 1

    # Determine output path
    if args.output:
        output_path = args.output
    else:
        output_path = str(input_path.with_suffix(".stl"))

    # Route to appropriate generator
    try:
        if args.figurine:
            result = generate_figurine(args, input_path, output_path)
        elif args.flat:
            result = generate_flat(args, input_path, output_path)
        elif args.relief:
            result = generate_relief(args, input_path, output_path)
        elif args.lithophane:
            result = generate_lithophane(args, input_path, output_path)

        print(f"\nSuccess! Output: {result}")
        print("Next: Open in OrcaSlicer to slice and print")
        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


def generate_figurine(args, input_path, output_path):
    """Generate AI 3D figurine using Tripo API."""
    from figurines.backends.tripo_api import generate_figurine as tripo_generate

    print(f"Generating 3D figurine from: {input_path}")
    print(f"Target height: {args.scale}mm")

    return tripo_generate(
        image_path=str(input_path),
        output_path=output_path,
        scale_mm=args.scale,
        add_base=not args.no_base,
        base_height_mm=args.base_height,
        verbose=args.verbose or True
    )


def generate_flat(args, input_path, output_path):
    """Generate flat contour extrusion."""
    # Import from scripts directory
    sys.path.insert(0, str(Path(__file__).parent / "scripts"))
    from png_to_stl import png_to_stl

    print(f"Generating flat extrusion from: {input_path}")
    print(f"Height: {args.height}mm, Width: {args.scale}mm")

    result = png_to_stl(
        image_path=str(input_path),
        output_path=output_path,
        height=args.height,
        scale=args.scale,
        threshold=args.threshold,
        invert=args.invert,
        base=args.base_height if not args.no_base else 0,
        fit_to_bed=True
    )

    return output_path


def generate_relief(args, input_path, output_path):
    """Generate heightmap relief."""
    sys.path.insert(0, str(Path(__file__).parent / "scripts"))
    from heightmap_to_stl import heightmap_to_stl

    print(f"Generating heightmap relief from: {input_path}")
    print(f"Max height: {args.max_height}mm")

    # Calculate scale to fit target width
    scale_factor = args.scale / 100  # Rough approximation

    result = heightmap_to_stl(
        image_path=str(input_path),
        output_path=output_path,
        max_height=args.max_height,
        base_height=args.base_height if not args.no_base else 0,
        scale=scale_factor,
        fit_to_bed=True
    )

    return output_path


def generate_lithophane(args, input_path, output_path):
    """Generate lithophane."""
    sys.path.insert(0, str(Path(__file__).parent / "scripts"))
    from lithophane import lithophane

    print(f"Generating lithophane from: {input_path}")
    print(f"Width: {args.scale}mm, Thickness: {args.thickness}mm")

    result = lithophane(
        image_path=str(input_path),
        output_path=output_path,
        thickness=args.thickness,
        width=args.scale,
        frame=args.frame
    )

    return output_path


if __name__ == "__main__":
    sys.exit(main())
