#!/usr/bin/env python3
"""
Convert PNG/JPG images to clean SVG files for import into Orca-Flashforge.

Best for: When you want to use Orca's native SVG→3D, but start with a raster image
"""

import argparse
from pathlib import Path

import cv2
import numpy as np
import svgwrite


def trace_contours(
    image_path: str,
    threshold: int = 127,
    invert: bool = False,
    smoothing: str = 'medium',
    simplify: float = 2.0
) -> tuple:
    """
    Trace contours from an image for SVG conversion.

    Args:
        image_path: Path to input image
        threshold: Binarization threshold (0-255)
        invert: Invert the binary image
        smoothing: Smoothing level (none, low, medium, high)
        simplify: Path simplification tolerance

    Returns:
        Tuple of (contours list, image dimensions)
    """
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise FileNotFoundError(f"Could not load image: {image_path}")

    height, width = img.shape

    # Apply smoothing
    smooth_map = {'none': 0, 'low': 3, 'medium': 5, 'high': 9}
    kernel_size = smooth_map.get(smoothing, 5)
    if kernel_size > 0:
        img = cv2.GaussianBlur(img, (kernel_size, kernel_size), 0)

    # Binarize
    _, binary = cv2.threshold(img, threshold, 255, cv2.THRESH_BINARY)

    if invert:
        binary = 255 - binary

    # Find contours
    contours, hierarchy = cv2.findContours(
        binary, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE
    )

    # Simplify contours
    simplified_contours = []
    for contour in contours:
        if len(contour) < 3:
            continue
        epsilon = simplify
        approx = cv2.approxPolyDP(contour, epsilon, True)
        if len(approx) >= 3:
            simplified_contours.append(approx)

    return simplified_contours, hierarchy, (width, height)


def contour_to_svg_path(contour: np.ndarray) -> str:
    """Convert a single contour to SVG path data."""
    points = contour.reshape(-1, 2)
    if len(points) < 3:
        return ""

    # Start path
    path_data = f"M {points[0][0]},{points[0][1]}"

    # Add line segments
    for point in points[1:]:
        path_data += f" L {point[0]},{point[1]}"

    # Close path
    path_data += " Z"

    return path_data


def create_svg(
    contours: list,
    hierarchy: np.ndarray,
    dimensions: tuple,
    output_path: str,
    stroke_width: float = 0
) -> str:
    """
    Create SVG file from contours.

    Args:
        contours: List of contours
        hierarchy: Contour hierarchy
        dimensions: (width, height) of original image
        output_path: Path for output SVG file
        stroke_width: Stroke width for outlines (0 = filled)

    Returns:
        Path to created SVG file
    """
    width, height = dimensions

    dwg = svgwrite.Drawing(
        output_path,
        size=(f'{width}px', f'{height}px'),
        viewBox=f'0 0 {width} {height}'
    )

    # Add a white background (optional, comment out for transparent)
    # dwg.add(dwg.rect(insert=(0, 0), size=(width, height), fill='white'))

    if hierarchy is None or len(contours) == 0:
        dwg.save()
        return output_path

    hierarchy = hierarchy[0]

    # Process contours
    for i, contour in enumerate(contours):
        path_data = contour_to_svg_path(contour)
        if not path_data:
            continue

        # Determine if this is an outer contour or hole
        is_outer = hierarchy[i][3] == -1 if i < len(hierarchy) else True

        if stroke_width > 0:
            # Outline mode
            dwg.add(dwg.path(
                d=path_data,
                fill='none',
                stroke='black',
                stroke_width=stroke_width
            ))
        else:
            # Filled mode
            fill_color = 'black' if is_outer else 'white'
            dwg.add(dwg.path(
                d=path_data,
                fill=fill_color,
                stroke='none'
            ))

    dwg.save()
    return output_path


def png_to_svg(
    image_path: str,
    output_path: str,
    smoothing: str = 'medium',
    threshold: int = 127,
    simplify: float = 2.0,
    invert: bool = False,
    colors: int = 2
) -> dict:
    """
    Convert a PNG/JPG image to SVG.

    Args:
        image_path: Path to input image
        output_path: Path for output SVG file
        smoothing: Smoothing level (none, low, medium, high)
        threshold: Binarization threshold (0-255)
        simplify: Path simplification tolerance
        invert: Invert image colors
        colors: Number of colors (2 = black/white)

    Returns:
        dict with conversion results
    """
    if not Path(image_path).exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    print(f"Converting: {image_path}")
    print(f"Settings: smoothing={smoothing}, threshold={threshold}, simplify={simplify}")

    # Trace contours
    contours, hierarchy, dimensions = trace_contours(
        image_path,
        threshold=threshold,
        invert=invert,
        smoothing=smoothing,
        simplify=simplify
    )

    print(f"Image size: {dimensions[0]} x {dimensions[1]} pixels")
    print(f"Found {len(contours)} paths")

    if not contours:
        raise ValueError("No contours found. Try adjusting --threshold or --smoothing")

    # Create SVG
    svg_path = create_svg(contours, hierarchy, dimensions, output_path)

    import os
    file_size = os.path.getsize(svg_path)

    print(f"\nSVG exported: {svg_path}")
    print(f"File size: {file_size / 1024:.1f} KB")
    print(f"\nNext: Open Orca-Flashforge → Right-click workspace → Add Part → Select this SVG")

    return {
        'output_path': svg_path,
        'success': True,
        'file_size': file_size,
        'num_paths': len(contours)
    }


def main():
    parser = argparse.ArgumentParser(
        description='Convert PNG/JPG image to SVG for Orca-Flashforge import'
    )
    parser.add_argument('input', help='Input image file (PNG, JPG)')
    parser.add_argument('output', help='Output SVG file path')
    parser.add_argument(
        '--smoothing', choices=['none', 'low', 'medium', 'high'], default='medium',
        help='Curve smoothing level (default: medium)'
    )
    parser.add_argument(
        '--threshold', type=int, default=127,
        help='Binarization threshold 0-255 (default: 127)'
    )
    parser.add_argument(
        '--simplify', type=float, default=2.0,
        help='Path simplification tolerance (default: 2.0)'
    )
    parser.add_argument(
        '--invert', action='store_true',
        help='Invert image colors'
    )
    parser.add_argument(
        '--colors', type=int, default=2,
        help='Number of colors to trace (default: 2 for black/white)'
    )

    args = parser.parse_args()

    png_to_svg(
        args.input,
        args.output,
        smoothing=args.smoothing,
        threshold=args.threshold,
        simplify=args.simplify,
        invert=args.invert,
        colors=args.colors
    )


if __name__ == '__main__':
    main()
