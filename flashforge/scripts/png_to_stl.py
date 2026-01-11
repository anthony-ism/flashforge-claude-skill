#!/usr/bin/env python3
"""
Convert PNG/JPG images to 3D STL using contour detection and extrusion.

Best for: icons, logos, clipart with clear edges and solid colors
"""

import argparse

import cv2
import numpy as np
import trimesh
from shapely.geometry import Polygon, MultiPolygon
from shapely.ops import unary_union
from shapely.validation import make_valid

from utils import (
    export_stl,
    print_summary,
    scale_to_fit,
    MAX_BUILD_X,
    MAX_BUILD_Y,
)


def extract_contours(
    image_path: str,
    threshold: int = 127,
    invert: bool = False
) -> tuple:
    """
    Extract contours from an image using edge detection.

    Args:
        image_path: Path to input image
        threshold: Binarization threshold (0-255)
        invert: Invert the binary image before contour detection

    Returns:
        Tuple of (contours, hierarchy, image shape)
    """
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise FileNotFoundError(f"Could not load image: {image_path}")

    # Binarize
    _, binary = cv2.threshold(img, threshold, 255, cv2.THRESH_BINARY)

    if invert:
        binary = 255 - binary

    # Find contours with hierarchy for handling holes
    contours, hierarchy = cv2.findContours(
        binary, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE
    )

    return contours, hierarchy, img.shape


def simplify_contour(contour: np.ndarray, tolerance: float = 1.0) -> np.ndarray:
    """Simplify a contour using Douglas-Peucker algorithm."""
    epsilon = tolerance * cv2.arcLength(contour, True) / 100
    return cv2.approxPolyDP(contour, epsilon, True)


def contours_to_polygons(
    contours: list,
    hierarchy: np.ndarray,
    simplify_tolerance: float = 0.5
) -> list:
    """Convert OpenCV contours to Shapely polygons with hole handling."""
    if hierarchy is None or len(contours) == 0:
        return []

    hierarchy = hierarchy[0]
    polygons = []

    # Find top-level contours (no parent)
    for i, contour in enumerate(contours):
        if hierarchy[i][3] == -1:  # No parent = outer contour
            if len(contour) < 3:
                continue

            simplified = simplify_contour(contour, simplify_tolerance)
            if len(simplified) < 3:
                continue

            points = simplified.reshape(-1, 2)
            try:
                outer_poly = Polygon(points)
                if not outer_poly.is_valid:
                    outer_poly = make_valid(outer_poly)
                if outer_poly.is_empty or outer_poly.area < 1:
                    continue

                # Find holes (children of this contour)
                holes = []
                child_idx = hierarchy[i][2]
                while child_idx != -1:
                    child_contour = contours[child_idx]
                    if len(child_contour) >= 3:
                        child_simplified = simplify_contour(child_contour, simplify_tolerance)
                        if len(child_simplified) >= 3:
                            hole_points = child_simplified.reshape(-1, 2)
                            holes.append(hole_points.tolist())
                    child_idx = hierarchy[child_idx][0]

                if holes:
                    outer_poly = Polygon(points, holes)
                    if not outer_poly.is_valid:
                        outer_poly = make_valid(outer_poly)

                if not outer_poly.is_empty and outer_poly.area > 1:
                    polygons.append(outer_poly)

            except Exception:
                continue

    return polygons


def extrude_polygon(polygon, height: float) -> list:
    """
    Extrude a 2D polygon (or collection) to create 3D meshes.

    Handles Polygon, MultiPolygon, and GeometryCollection.
    Returns a list of meshes.
    """
    from shapely.geometry import GeometryCollection, MultiPolygon as MP

    meshes = []

    # Handle different geometry types
    if isinstance(polygon, (MP, GeometryCollection)):
        # Extract all polygons from collection
        for geom in polygon.geoms:
            if isinstance(geom, Polygon) and not geom.is_empty and geom.area > 1:
                try:
                    mesh = trimesh.creation.extrude_polygon(geom, height)
                    if mesh is not None:
                        meshes.append(mesh)
                except Exception as e:
                    continue
    elif isinstance(polygon, Polygon):
        try:
            mesh = trimesh.creation.extrude_polygon(polygon, height)
            if mesh is not None:
                meshes.append(mesh)
        except Exception as e:
            print(f"Warning: Could not extrude polygon: {e}")

    return meshes


def add_base_plate(mesh: trimesh.Trimesh, base_height: float) -> trimesh.Trimesh:
    """Add a rectangular base plate under the mesh."""
    bounds = mesh.bounds
    width = bounds[1, 0] - bounds[0, 0]
    depth = bounds[1, 1] - bounds[0, 1]

    # Create base plate slightly larger than the model
    padding = 2  # mm padding on each side
    base = trimesh.creation.box([width + padding * 2, depth + padding * 2, base_height])

    # Position base plate
    base.apply_translation([
        (bounds[0, 0] + bounds[1, 0]) / 2,
        (bounds[0, 1] + bounds[1, 1]) / 2,
        -base_height / 2
    ])

    # Move main mesh up by base height
    mesh.apply_translation([0, 0, base_height])

    # Combine
    return trimesh.util.concatenate([base, mesh])


def png_to_stl(
    image_path: str,
    output_path: str,
    height: float = 5.0,
    scale: float = None,
    threshold: int = 127,
    invert: bool = False,
    base: float = 0,
    simplify: float = 0.5,
    fit_to_bed: bool = True
) -> dict:
    """
    Convert a PNG/JPG image to STL using contour detection and extrusion.

    Args:
        image_path: Path to input image
        output_path: Path for output STL file
        height: Extrusion height in mm
        scale: Output width in mm (None = auto-fit to 100mm)
        threshold: Binarization threshold (0-255)
        invert: Invert image (swap foreground/background)
        base: Base plate thickness in mm (0 = no base)
        simplify: Contour simplification tolerance
        fit_to_bed: Scale to fit printer bed if needed

    Returns:
        dict with conversion results
    """
    # Extract contours
    contours, hierarchy, img_shape = extract_contours(
        image_path, threshold=threshold, invert=invert
    )

    print(f"Input image: {img_shape[1]} x {img_shape[0]} pixels")
    print(f"Found {len(contours)} contours")
    print(f"Settings: height={height}mm, threshold={threshold}")
    if invert:
        print("Inverted: extruding dark areas")

    # Convert to polygons
    polygons = contours_to_polygons(contours, hierarchy, simplify)
    print(f"Created {len(polygons)} valid polygons")

    if not polygons:
        raise ValueError("No valid contours found in image. Try adjusting --threshold or use --invert")

    # Merge overlapping polygons
    try:
        merged = unary_union(polygons)
        if isinstance(merged, Polygon):
            polygons = [merged]
        elif isinstance(merged, MultiPolygon):
            polygons = list(merged.geoms)
    except Exception:
        pass

    # Extrude all polygons and combine
    meshes = []
    for poly in polygons:
        poly_meshes = extrude_polygon(poly, height)
        meshes.extend(poly_meshes)

    if not meshes:
        raise ValueError("Failed to create any valid meshes")

    # Combine all meshes
    combined = trimesh.util.concatenate(meshes)

    # Flip Y axis (image coordinates are top-down)
    combined.vertices[:, 1] = -combined.vertices[:, 1]

    # Center on origin
    combined.vertices -= combined.centroid

    # Move to sit on Z=0
    combined.vertices[:, 2] -= combined.bounds[0, 2]

    # Scale to target width if specified (X/Y only, preserve Z height)
    if scale is not None:
        current_width = combined.bounds[1, 0] - combined.bounds[0, 0]
        if current_width > 0:
            scale_factor = scale / current_width
            # Scale X and Y only, keep Z at original extrusion height
            combined.vertices[:, 0] *= scale_factor
            combined.vertices[:, 1] *= scale_factor
            print(f"Scaled to {scale}mm width")

    # Scale to fit printer if needed
    if fit_to_bed:
        combined = scale_to_fit(combined)

    # Add base plate if requested
    if base > 0:
        combined = add_base_plate(combined, base)
        print(f"Added {base}mm base plate")

    # Export
    result = export_stl(combined, output_path)
    print_summary(result)

    return result


def main():
    parser = argparse.ArgumentParser(
        description='Convert PNG/JPG image to 3D STL using contour extrusion'
    )
    parser.add_argument('input', help='Input image file (PNG, JPG)')
    parser.add_argument('output', help='Output STL file path')
    parser.add_argument(
        '--height', type=float, default=5.0,
        help='Extrusion height in mm (default: 5)'
    )
    parser.add_argument(
        '--scale', type=float, default=None,
        help='Output width in mm (default: auto-fit to 100mm)'
    )
    parser.add_argument(
        '--threshold', type=int, default=127,
        help='Binarization threshold 0-255 (default: 127)'
    )
    parser.add_argument(
        '--invert', action='store_true',
        help='Invert image (extrude dark areas instead of light)'
    )
    parser.add_argument(
        '--base', type=float, default=0,
        help='Base plate thickness in mm (default: 0 = no base)'
    )
    parser.add_argument(
        '--simplify', type=float, default=0.5,
        help='Contour simplification tolerance (default: 0.5)'
    )
    parser.add_argument(
        '--no-fit', action='store_true',
        help='Do not automatically scale to fit printer bed'
    )

    args = parser.parse_args()

    png_to_stl(
        args.input,
        args.output,
        height=args.height,
        scale=args.scale,
        threshold=args.threshold,
        invert=args.invert,
        base=args.base,
        simplify=args.simplify,
        fit_to_bed=not args.no_fit
    )


if __name__ == '__main__':
    main()
