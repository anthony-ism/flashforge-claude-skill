#!/usr/bin/env python3
"""
Convert images to 3D STL using heightmap/brightness extrusion.

Best for: photos, grayscale art, lithophanes, pixel art
"""

import argparse

import numpy as np
import trimesh

from utils import (
    load_image,
    preprocess_image,
    export_stl,
    print_summary,
    scale_to_fit,
)


def create_heightmap_mesh(
    img_array: np.ndarray,
    max_height: float = 10.0,
    base_height: float = 2.0,
    scale: float = 1.0,
    pixels_per_mm: float = 2.0
) -> trimesh.Trimesh:
    """
    Create a 3D mesh from a grayscale image using heightmap extrusion.

    Each pixel's brightness (0-255) maps to a Z height value.
    The mesh includes a solid base plate for printability.

    Args:
        img_array: 2D numpy array of grayscale values (0-255)
        max_height: Maximum extrusion height in mm
        base_height: Base plate thickness in mm
        scale: Scale factor for X/Y dimensions
        pixels_per_mm: Resolution (higher = smaller physical size)

    Returns:
        trimesh.Trimesh object
    """
    height, width = img_array.shape

    # Calculate physical dimensions
    phys_width = (width / pixels_per_mm) * scale
    phys_height = (height / pixels_per_mm) * scale

    # Normalize brightness to height values
    # 0 (black) = base_height, 255 (white) = base_height + max_height
    heights = (img_array.astype(np.float64) / 255.0) * max_height + base_height

    # Create grid of X, Y coordinates
    x = np.linspace(0, phys_width, width)
    y = np.linspace(0, phys_height, height)
    xx, yy = np.meshgrid(x, y)

    # Flatten for vertex creation
    xx_flat = xx.flatten()
    yy_flat = yy.flatten()
    zz_flat = heights.flatten()

    # Create top surface vertices
    top_vertices = np.column_stack([xx_flat, yy_flat, zz_flat])

    # Create bottom surface vertices (at z=0)
    bottom_vertices = np.column_stack([xx_flat, yy_flat, np.zeros_like(zz_flat)])

    # Combine all vertices
    n_top = len(top_vertices)
    vertices = np.vstack([top_vertices, bottom_vertices])

    # Create faces for top surface
    faces = []
    for i in range(height - 1):
        for j in range(width - 1):
            # Indices of the four corners of this grid cell
            tl = i * width + j          # top-left
            tr = i * width + j + 1      # top-right
            bl = (i + 1) * width + j    # bottom-left
            br = (i + 1) * width + j + 1  # bottom-right

            # Two triangles for top surface
            faces.append([tl, bl, tr])
            faces.append([tr, bl, br])

    # Create faces for bottom surface (reversed winding)
    for i in range(height - 1):
        for j in range(width - 1):
            tl = n_top + i * width + j
            tr = n_top + i * width + j + 1
            bl = n_top + (i + 1) * width + j
            br = n_top + (i + 1) * width + j + 1

            faces.append([tl, tr, bl])
            faces.append([tr, br, bl])

    # Create side walls
    # Left edge (j=0)
    for i in range(height - 1):
        top_curr = i * width
        top_next = (i + 1) * width
        bot_curr = n_top + i * width
        bot_next = n_top + (i + 1) * width
        faces.append([top_curr, bot_curr, top_next])
        faces.append([top_next, bot_curr, bot_next])

    # Right edge (j=width-1)
    for i in range(height - 1):
        top_curr = i * width + (width - 1)
        top_next = (i + 1) * width + (width - 1)
        bot_curr = n_top + i * width + (width - 1)
        bot_next = n_top + (i + 1) * width + (width - 1)
        faces.append([top_curr, top_next, bot_curr])
        faces.append([top_next, bot_next, bot_curr])

    # Top edge (i=0)
    for j in range(width - 1):
        top_curr = j
        top_next = j + 1
        bot_curr = n_top + j
        bot_next = n_top + j + 1
        faces.append([top_curr, top_next, bot_curr])
        faces.append([top_next, bot_next, bot_curr])

    # Bottom edge (i=height-1)
    for j in range(width - 1):
        top_curr = (height - 1) * width + j
        top_next = (height - 1) * width + j + 1
        bot_curr = n_top + (height - 1) * width + j
        bot_next = n_top + (height - 1) * width + j + 1
        faces.append([top_curr, bot_curr, top_next])
        faces.append([top_next, bot_curr, bot_next])

    faces = np.array(faces)

    mesh = trimesh.Trimesh(vertices=vertices, faces=faces)
    mesh.fix_normals()

    return mesh


def heightmap_to_stl(
    image_path: str,
    output_path: str,
    max_height: float = 10.0,
    base_height: float = 2.0,
    scale: float = 1.0,
    invert: bool = False,
    smooth: int = 0,
    fit_to_bed: bool = True
) -> dict:
    """
    Convert an image to STL using heightmap extrusion.

    Args:
        image_path: Path to input image
        output_path: Path for output STL file
        max_height: Maximum extrusion height in mm
        base_height: Base plate thickness in mm
        scale: Scale factor for X/Y dimensions
        invert: Invert brightness (for lithophanes)
        smooth: Gaussian smoothing radius (0 = none)
        fit_to_bed: Scale down to fit printer bed if needed

    Returns:
        dict with conversion results
    """
    # Load and preprocess image
    img_array = load_image(image_path, grayscale=True)
    img_array = preprocess_image(img_array, invert=invert, smooth_radius=smooth)

    print(f"Input image: {img_array.shape[1]} x {img_array.shape[0]} pixels")
    print(f"Settings: max_height={max_height}mm, base={base_height}mm, scale={scale}")
    if invert:
        print("Brightness inverted (lithophane mode)")

    # Create mesh
    mesh = create_heightmap_mesh(
        img_array,
        max_height=max_height,
        base_height=base_height,
        scale=scale
    )

    # Scale to fit printer if needed
    if fit_to_bed:
        mesh = scale_to_fit(mesh)

    # Export
    result = export_stl(mesh, output_path)
    print_summary(result)

    return result


def main():
    parser = argparse.ArgumentParser(
        description='Convert image to 3D STL using heightmap extrusion'
    )
    parser.add_argument('input', help='Input image file (PNG, JPG, etc.)')
    parser.add_argument('output', help='Output STL file path')
    parser.add_argument(
        '--max-height', type=float, default=10.0,
        help='Maximum extrusion height in mm (default: 10)'
    )
    parser.add_argument(
        '--base-height', type=float, default=2.0,
        help='Base plate thickness in mm (default: 2)'
    )
    parser.add_argument(
        '--scale', type=float, default=1.0,
        help='Scale factor for X/Y dimensions (default: 1.0)'
    )
    parser.add_argument(
        '--invert', action='store_true',
        help='Invert brightness (for lithophanes)'
    )
    parser.add_argument(
        '--smooth', type=int, default=0,
        help='Gaussian smoothing radius (default: 0 = none)'
    )
    parser.add_argument(
        '--no-fit', action='store_true',
        help='Do not automatically scale to fit printer bed'
    )

    args = parser.parse_args()

    heightmap_to_stl(
        args.input,
        args.output,
        max_height=args.max_height,
        base_height=args.base_height,
        scale=args.scale,
        invert=args.invert,
        smooth=args.smooth,
        fit_to_bed=not args.no_fit
    )


if __name__ == '__main__':
    main()
