#!/usr/bin/env python3
"""
Convert photos to lithophane STL files.

Best for: Photos, portraits, detailed grayscale images
Lithophanes look best when backlit - print in white PLA
"""

import argparse
import math

import numpy as np
from PIL import Image, ImageFilter
import trimesh

from utils import (
    export_stl,
    print_summary,
    scale_to_fit,
)


def load_and_prepare_image(
    image_path: str,
    target_width: int = 200,
    positive: bool = False
) -> np.ndarray:
    """
    Load image and prepare for lithophane conversion.

    Args:
        image_path: Path to input image
        target_width: Target width in pixels for processing
        positive: If True, light areas are thick (positive lithophane)

    Returns:
        Grayscale image array normalized 0-1
    """
    img = Image.open(image_path)

    # Convert to grayscale
    img = img.convert('L')

    # Resize maintaining aspect ratio
    aspect = img.height / img.width
    target_height = int(target_width * aspect)
    img = img.resize((target_width, target_height), Image.Resampling.LANCZOS)

    # Convert to numpy array
    arr = np.array(img, dtype=np.float64) / 255.0

    # For traditional (negative) lithophane: dark = thin, light = thick
    # For positive lithophane: light = thin, dark = thick
    if not positive:
        arr = 1.0 - arr  # Invert for traditional lithophane

    return arr


def create_flat_lithophane(
    img_array: np.ndarray,
    width_mm: float,
    min_thickness: float,
    max_thickness: float
) -> trimesh.Trimesh:
    """
    Create a flat lithophane mesh.

    Args:
        img_array: Grayscale image array (0-1)
        width_mm: Target width in mm
        min_thickness: Minimum thickness in mm
        max_thickness: Maximum thickness in mm

    Returns:
        trimesh.Trimesh object
    """
    height_px, width_px = img_array.shape

    # Calculate physical dimensions
    pixel_size = width_mm / width_px
    height_mm = height_px * pixel_size

    # Map pixel values to thickness
    thickness_range = max_thickness - min_thickness
    thickness_map = img_array * thickness_range + min_thickness

    # Create vertices for top surface
    vertices = []
    faces = []

    # Generate grid of vertices
    for y in range(height_px):
        for x in range(width_px):
            # Top surface vertex
            px = x * pixel_size
            py = y * pixel_size
            pz = thickness_map[y, x]
            vertices.append([px, py, pz])

    # Add bottom surface vertices (at z=0)
    for y in range(height_px):
        for x in range(width_px):
            px = x * pixel_size
            py = y * pixel_size
            vertices.append([px, py, 0])

    vertices = np.array(vertices)
    n_top = width_px * height_px

    # Create faces for top surface
    for y in range(height_px - 1):
        for x in range(width_px - 1):
            tl = y * width_px + x
            tr = y * width_px + x + 1
            bl = (y + 1) * width_px + x
            br = (y + 1) * width_px + x + 1

            faces.append([tl, bl, tr])
            faces.append([tr, bl, br])

    # Create faces for bottom surface (reversed)
    for y in range(height_px - 1):
        for x in range(width_px - 1):
            tl = n_top + y * width_px + x
            tr = n_top + y * width_px + x + 1
            bl = n_top + (y + 1) * width_px + x
            br = n_top + (y + 1) * width_px + x + 1

            faces.append([tl, tr, bl])
            faces.append([tr, br, bl])

    # Create side walls
    # Left edge
    for y in range(height_px - 1):
        top_curr = y * width_px
        top_next = (y + 1) * width_px
        bot_curr = n_top + y * width_px
        bot_next = n_top + (y + 1) * width_px
        faces.append([top_curr, bot_curr, top_next])
        faces.append([top_next, bot_curr, bot_next])

    # Right edge
    for y in range(height_px - 1):
        top_curr = y * width_px + (width_px - 1)
        top_next = (y + 1) * width_px + (width_px - 1)
        bot_curr = n_top + y * width_px + (width_px - 1)
        bot_next = n_top + (y + 1) * width_px + (width_px - 1)
        faces.append([top_curr, top_next, bot_curr])
        faces.append([top_next, bot_next, bot_curr])

    # Top edge
    for x in range(width_px - 1):
        top_curr = x
        top_next = x + 1
        bot_curr = n_top + x
        bot_next = n_top + x + 1
        faces.append([top_curr, top_next, bot_curr])
        faces.append([top_next, bot_next, bot_curr])

    # Bottom edge
    for x in range(width_px - 1):
        top_curr = (height_px - 1) * width_px + x
        top_next = (height_px - 1) * width_px + x + 1
        bot_curr = n_top + (height_px - 1) * width_px + x
        bot_next = n_top + (height_px - 1) * width_px + x + 1
        faces.append([top_curr, bot_curr, top_next])
        faces.append([top_next, bot_curr, bot_next])

    faces = np.array(faces)

    mesh = trimesh.Trimesh(vertices=vertices, faces=faces)
    mesh.fix_normals()

    return mesh


def add_simple_frame(mesh: trimesh.Trimesh, frame_width: float = 5.0) -> trimesh.Trimesh:
    """Add a simple rectangular frame around the lithophane."""
    bounds = mesh.bounds
    width = bounds[1, 0] - bounds[0, 0]
    height = bounds[1, 1] - bounds[0, 1]
    thickness = bounds[1, 2] - bounds[0, 2]

    frame_parts = []

    # Frame thickness matches max lithophane thickness
    frame_height = thickness + 1  # Slightly taller

    # Left frame
    left = trimesh.creation.box([frame_width, height + frame_width * 2, frame_height])
    left.apply_translation([
        bounds[0, 0] - frame_width / 2,
        (bounds[0, 1] + bounds[1, 1]) / 2,
        frame_height / 2
    ])
    frame_parts.append(left)

    # Right frame
    right = trimesh.creation.box([frame_width, height + frame_width * 2, frame_height])
    right.apply_translation([
        bounds[1, 0] + frame_width / 2,
        (bounds[0, 1] + bounds[1, 1]) / 2,
        frame_height / 2
    ])
    frame_parts.append(right)

    # Top frame
    top = trimesh.creation.box([width, frame_width, frame_height])
    top.apply_translation([
        (bounds[0, 0] + bounds[1, 0]) / 2,
        bounds[0, 1] - frame_width / 2,
        frame_height / 2
    ])
    frame_parts.append(top)

    # Bottom frame
    bottom = trimesh.creation.box([width, frame_width, frame_height])
    bottom.apply_translation([
        (bounds[0, 0] + bounds[1, 0]) / 2,
        bounds[1, 1] + frame_width / 2,
        frame_height / 2
    ])
    frame_parts.append(bottom)

    # Combine frame with lithophane
    all_parts = [mesh] + frame_parts
    return trimesh.util.concatenate(all_parts)


def lithophane(
    image_path: str,
    output_path: str,
    style: str = 'flat',
    thickness: float = 3.0,
    width: float = 100.0,
    positive: bool = False,
    frame: str = 'none'
) -> dict:
    """
    Convert a photo to a lithophane STL.

    Args:
        image_path: Path to input image
        output_path: Path for output STL file
        style: Lithophane style (flat, curved, cylindrical, heart)
        thickness: Maximum thickness in mm
        width: Output width in mm
        positive: Light areas thick (vs traditional dark-thin)
        frame: Frame type (none, simple)

    Returns:
        dict with conversion results
    """
    print(f"Converting to lithophane: {image_path}")
    print(f"Settings: style={style}, thickness={thickness}mm, width={width}mm")
    if positive:
        print("Mode: Positive (light = thick)")
    else:
        print("Mode: Traditional/Negative (dark = thin, light = thick when backlit)")

    # Calculate resolution based on output width
    # Aim for roughly 0.5mm per pixel for good detail
    resolution = int(width / 0.5)
    resolution = min(resolution, 400)  # Cap for performance

    # Load and prepare image
    img_array = load_and_prepare_image(image_path, resolution, positive)
    print(f"Processing at {img_array.shape[1]} x {img_array.shape[0]} pixels")

    # Minimum thickness for structural integrity
    min_thickness = 0.8  # mm

    # Create lithophane based on style
    if style == 'flat':
        mesh = create_flat_lithophane(img_array, width, min_thickness, thickness)
    else:
        # For now, default to flat for other styles
        print(f"Style '{style}' not yet implemented, using flat")
        mesh = create_flat_lithophane(img_array, width, min_thickness, thickness)

    # Add frame if requested
    if frame == 'simple':
        mesh = add_simple_frame(mesh)
        print("Added simple frame")

    # Move to sit on Z=0
    mesh.vertices[:, 2] -= mesh.bounds[0, 2]

    # Export
    result = export_stl(mesh, output_path)
    print_summary(result)

    print("\n--- Lithophane Print Tips ---")
    print("- Print VERTICALLY for best results")
    print("- Use WHITE PLA filament")
    print("- Layer height: 0.12mm for detail")
    print("- Infill: 100%")
    print("- Speed: 40-60mm/s (slow for quality)")

    return result


def main():
    parser = argparse.ArgumentParser(
        description='Convert photo to lithophane STL'
    )
    parser.add_argument('input', help='Input image file (PNG, JPG)')
    parser.add_argument('output', help='Output STL file path')
    parser.add_argument(
        '--style', choices=['flat', 'curved', 'cylindrical', 'heart'], default='flat',
        help='Lithophane style (default: flat)'
    )
    parser.add_argument(
        '--thickness', type=float, default=3.0,
        help='Maximum thickness in mm (default: 3.0)'
    )
    parser.add_argument(
        '--width', type=float, default=100.0,
        help='Output width in mm (default: 100)'
    )
    parser.add_argument(
        '--positive', action='store_true',
        help='Light areas thick (default is traditional/negative)'
    )
    parser.add_argument(
        '--frame', choices=['none', 'simple'], default='none',
        help='Add decorative frame (default: none)'
    )

    args = parser.parse_args()

    lithophane(
        args.input,
        args.output,
        style=args.style,
        thickness=args.thickness,
        width=args.width,
        positive=args.positive,
        frame=args.frame
    )


if __name__ == '__main__':
    main()
