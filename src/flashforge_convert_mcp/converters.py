"""
2D to 3D Conversion Functions

Core conversion logic for:
- Contour extrusion (icons, logos)
- Heightmap relief (photos, grayscale)
- Lithophane (backlit photos)
- PNG to SVG (vector conversion)
"""

import cv2
import numpy as np
import trimesh
from pathlib import Path
from shapely.geometry import Polygon, MultiPolygon, GeometryCollection
from shapely.ops import unary_union
from shapely.validation import make_valid


# Build volume constants (FlashForge Adventurer 5M)
MAX_BUILD_X = 220
MAX_BUILD_Y = 220
MAX_BUILD_Z = 220


def scale_to_fit(mesh: trimesh.Trimesh, max_x=MAX_BUILD_X, max_y=MAX_BUILD_Y, max_z=MAX_BUILD_Z) -> trimesh.Trimesh:
    """Scale mesh to fit within build volume while maintaining aspect ratio."""
    bounds = mesh.bounds
    size = bounds[1] - bounds[0]

    scale_factors = []
    if size[0] > max_x:
        scale_factors.append(max_x / size[0])
    if size[1] > max_y:
        scale_factors.append(max_y / size[1])
    if size[2] > max_z:
        scale_factors.append(max_z / size[2])

    if scale_factors:
        scale = min(scale_factors)
        mesh.apply_scale(scale)

    return mesh


def validate_mesh(mesh: trimesh.Trimesh) -> dict:
    """Validate mesh for 3D printing."""
    bounds = mesh.bounds
    dimensions = bounds[1] - bounds[0]

    issues = []
    if not mesh.is_watertight:
        issues.append("Mesh is not watertight (may have holes)")
    if dimensions[0] > MAX_BUILD_X or dimensions[1] > MAX_BUILD_Y or dimensions[2] > MAX_BUILD_Z:
        issues.append(f"Exceeds build volume ({MAX_BUILD_X}x{MAX_BUILD_Y}x{MAX_BUILD_Z}mm)")

    return {
        "is_valid": len(issues) == 0,
        "is_watertight": mesh.is_watertight,
        "bounds": bounds.tolist(),
        "dimensions_mm": {"x": float(dimensions[0]), "y": float(dimensions[1]), "z": float(dimensions[2])},
        "volume_mm3": float(mesh.volume) if mesh.is_watertight else None,
        "triangle_count": len(mesh.faces),
        "vertex_count": len(mesh.vertices),
        "issues": issues
    }


# =============================================================================
# CONTOUR EXTRUSION (png_to_stl)
# =============================================================================

def extract_contours(image_path: str, threshold: int = 127, invert: bool = False) -> tuple:
    """Extract contours from an image using edge detection."""
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise FileNotFoundError(f"Could not load image: {image_path}")

    _, binary = cv2.threshold(img, threshold, 255, cv2.THRESH_BINARY)

    if invert:
        binary = 255 - binary

    contours, hierarchy = cv2.findContours(binary, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    return contours, hierarchy, img.shape


def simplify_contour(contour: np.ndarray, tolerance: float = 1.0) -> np.ndarray:
    """Simplify a contour using Douglas-Peucker algorithm."""
    epsilon = tolerance * cv2.arcLength(contour, True) / 100
    return cv2.approxPolyDP(contour, epsilon, True)


def contours_to_polygons(contours: list, hierarchy: np.ndarray, simplify_tolerance: float = 0.5) -> list:
    """Convert OpenCV contours to Shapely polygons with hole handling."""
    if hierarchy is None or len(contours) == 0:
        return []

    hierarchy = hierarchy[0]
    polygons = []

    for i, contour in enumerate(contours):
        if hierarchy[i][3] == -1:
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

                holes = []
                child_idx = hierarchy[i][2]
                while child_idx != -1:
                    child_contour = contours[child_idx]
                    if len(child_contour) >= 3:
                        child_simplified = simplify_contour(child_contour, simplify_tolerance)
                        if len(child_simplified) >= 3:
                            child_points = child_simplified.reshape(-1, 2)
                            holes.append(child_points)
                    child_idx = hierarchy[child_idx][0]

                if holes:
                    try:
                        outer_poly = Polygon(points, holes)
                        if not outer_poly.is_valid:
                            outer_poly = make_valid(outer_poly)
                    except:
                        pass

                if not outer_poly.is_empty and outer_poly.area >= 1:
                    polygons.append(outer_poly)

            except Exception:
                continue

    return polygons


def extrude_polygon(polygon, height: float) -> list:
    """Extrude a 2D polygon to 3D."""
    if isinstance(polygon, (MultiPolygon, GeometryCollection)):
        meshes = []
        geoms = polygon.geoms if hasattr(polygon, 'geoms') else [polygon]
        for geom in geoms:
            if isinstance(geom, Polygon) and not geom.is_empty:
                meshes.extend(extrude_polygon(geom, height))
        return meshes

    if not isinstance(polygon, Polygon) or polygon.is_empty:
        return []

    try:
        mesh = trimesh.creation.extrude_polygon(polygon, height)
        if mesh is not None and len(mesh.vertices) > 0:
            return [mesh]
    except Exception:
        pass

    return []


def add_base_plate(mesh: trimesh.Trimesh, base_height: float) -> trimesh.Trimesh:
    """Add a base plate under the mesh."""
    bounds = mesh.bounds
    width = bounds[1, 0] - bounds[0, 0]
    depth = bounds[1, 1] - bounds[0, 1]

    base = trimesh.creation.box([width + 4, depth + 4, base_height])
    base.vertices[:, 2] -= base_height / 2
    base.vertices[:, 0] += (bounds[0, 0] + bounds[1, 0]) / 2
    base.vertices[:, 1] += (bounds[0, 1] + bounds[1, 1]) / 2

    mesh.vertices[:, 2] += base_height

    return trimesh.util.concatenate([base, mesh])


def image_to_stl_contour(
    image_path: str,
    output_path: str,
    height_mm: float = 5.0,
    scale_mm: float = None,
    threshold: int = 127,
    invert: bool = False,
    base_mm: float = 0,
    simplify: float = 0.5,
    fit_to_bed: bool = True
) -> dict:
    """
    Convert PNG/JPG image to STL using contour extrusion.

    Best for: icons, logos, clipart with clear edges and solid colors.
    """
    contours, hierarchy, img_shape = extract_contours(image_path, threshold=threshold, invert=invert)

    polygons = contours_to_polygons(contours, hierarchy, simplify)

    if not polygons:
        raise ValueError("No valid contours found. Try adjusting threshold or use invert=True")

    try:
        merged = unary_union(polygons)
        if isinstance(merged, Polygon):
            polygons = [merged]
        elif isinstance(merged, MultiPolygon):
            polygons = list(merged.geoms)
    except:
        pass

    meshes = []
    for poly in polygons:
        poly_meshes = extrude_polygon(poly, height_mm)
        meshes.extend(poly_meshes)

    if not meshes:
        raise ValueError("Failed to create any valid meshes")

    combined = trimesh.util.concatenate(meshes)
    combined.vertices[:, 1] = -combined.vertices[:, 1]
    combined.vertices -= combined.centroid
    combined.vertices[:, 2] -= combined.bounds[0, 2]

    if scale_mm is not None:
        current_width = combined.bounds[1, 0] - combined.bounds[0, 0]
        if current_width > 0:
            scale_factor = scale_mm / current_width
            combined.vertices[:, 0] *= scale_factor
            combined.vertices[:, 1] *= scale_factor

    if fit_to_bed:
        combined = scale_to_fit(combined)

    if base_mm > 0:
        combined = add_base_plate(combined, base_mm)

    combined.export(output_path)
    validation = validate_mesh(combined)

    return {
        "output_path": output_path,
        "file_size_bytes": Path(output_path).stat().st_size,
        "input_resolution": f"{img_shape[1]}x{img_shape[0]}",
        "contours_found": len(contours),
        "polygons_created": len(polygons),
        **validation
    }


# =============================================================================
# HEIGHTMAP RELIEF
# =============================================================================

def image_to_stl_heightmap(
    image_path: str,
    output_path: str,
    max_height_mm: float = 10.0,
    base_mm: float = 2.0,
    scale: float = 1.0,
    invert: bool = False,
    smooth: int = 0,
    fit_to_bed: bool = True
) -> dict:
    """
    Convert image to STL using brightness-to-height mapping.

    Best for: photos, grayscale art, relief models.
    """
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise FileNotFoundError(f"Could not load image: {image_path}")

    if smooth > 0:
        img = cv2.GaussianBlur(img, (smooth * 2 + 1, smooth * 2 + 1), 0)

    if invert:
        img = 255 - img

    height, width = img.shape
    pixels_per_mm = 2.0

    x = np.arange(width) / pixels_per_mm * scale
    y = np.arange(height) / pixels_per_mm * scale
    X, Y = np.meshgrid(x, y)

    Z = (img / 255.0) * max_height_mm + base_mm

    vertices = []
    faces = []

    # Top surface
    for i in range(height):
        for j in range(width):
            vertices.append([X[i, j], Y[i, j], Z[i, j]])

    def idx(i, j):
        return i * width + j

    for i in range(height - 1):
        for j in range(width - 1):
            faces.append([idx(i, j), idx(i + 1, j), idx(i + 1, j + 1)])
            faces.append([idx(i, j), idx(i + 1, j + 1), idx(i, j + 1)])

    # Bottom surface
    base_start = len(vertices)
    for i in range(height):
        for j in range(width):
            vertices.append([X[i, j], Y[i, j], 0])

    for i in range(height - 1):
        for j in range(width - 1):
            faces.append([base_start + idx(i, j), base_start + idx(i, j + 1), base_start + idx(i + 1, j + 1)])
            faces.append([base_start + idx(i, j), base_start + idx(i + 1, j + 1), base_start + idx(i + 1, j)])

    # Side walls
    for j in range(width - 1):
        faces.append([idx(0, j), idx(0, j + 1), base_start + idx(0, j + 1)])
        faces.append([idx(0, j), base_start + idx(0, j + 1), base_start + idx(0, j)])
        i = height - 1
        faces.append([idx(i, j), base_start + idx(i, j), base_start + idx(i, j + 1)])
        faces.append([idx(i, j), base_start + idx(i, j + 1), idx(i, j + 1)])

    for i in range(height - 1):
        faces.append([idx(i, 0), base_start + idx(i, 0), base_start + idx(i + 1, 0)])
        faces.append([idx(i, 0), base_start + idx(i + 1, 0), idx(i + 1, 0)])
        j = width - 1
        faces.append([idx(i, j), idx(i + 1, j), base_start + idx(i + 1, j)])
        faces.append([idx(i, j), base_start + idx(i + 1, j), base_start + idx(i, j)])

    mesh = trimesh.Trimesh(vertices=vertices, faces=faces)
    mesh.vertices[:, 1] = -mesh.vertices[:, 1]
    mesh.vertices -= mesh.centroid
    mesh.vertices[:, 2] -= mesh.bounds[0, 2]

    if fit_to_bed:
        mesh = scale_to_fit(mesh)

    mesh.export(output_path)
    validation = validate_mesh(mesh)

    return {
        "output_path": output_path,
        "file_size_bytes": Path(output_path).stat().st_size,
        "input_resolution": f"{width}x{height}",
        **validation
    }


# =============================================================================
# LITHOPHANE
# =============================================================================

def image_to_lithophane(
    image_path: str,
    output_path: str,
    thickness_mm: float = 3.0,
    width_mm: float = 100.0,
    positive: bool = False,
    frame: str = "none"
) -> dict:
    """
    Create a lithophane STL from a photo.

    Best for: backlit photo display, printed in white PLA.
    """
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise FileNotFoundError(f"Could not load image: {image_path}")

    # Resize for reasonable resolution
    max_pixels = 400
    height, width = img.shape
    if width > max_pixels:
        scale = max_pixels / width
        new_width = int(width * scale)
        new_height = int(height * scale)
        img = cv2.resize(img, (new_width, new_height))
        height, width = img.shape

    if not positive:
        img = 255 - img

    min_thickness = 0.8
    max_thickness = thickness_mm

    # Calculate dimensions
    pixel_width = width_mm / width
    actual_height = height * pixel_width

    x = np.arange(width) * pixel_width
    y = np.arange(height) * pixel_width
    X, Y = np.meshgrid(x, y)

    Z = min_thickness + (img / 255.0) * (max_thickness - min_thickness)

    vertices = []
    faces = []

    # Front surface
    for i in range(height):
        for j in range(width):
            vertices.append([X[i, j], Y[i, j], Z[i, j]])

    def idx(i, j):
        return i * width + j

    for i in range(height - 1):
        for j in range(width - 1):
            faces.append([idx(i, j), idx(i + 1, j), idx(i + 1, j + 1)])
            faces.append([idx(i, j), idx(i + 1, j + 1), idx(i, j + 1)])

    # Back surface
    back_start = len(vertices)
    for i in range(height):
        for j in range(width):
            vertices.append([X[i, j], Y[i, j], 0])

    for i in range(height - 1):
        for j in range(width - 1):
            faces.append([back_start + idx(i, j), back_start + idx(i, j + 1), back_start + idx(i + 1, j + 1)])
            faces.append([back_start + idx(i, j), back_start + idx(i + 1, j + 1), back_start + idx(i + 1, j)])

    # Side walls
    for j in range(width - 1):
        faces.append([idx(0, j), idx(0, j + 1), back_start + idx(0, j + 1)])
        faces.append([idx(0, j), back_start + idx(0, j + 1), back_start + idx(0, j)])
        i = height - 1
        faces.append([idx(i, j), back_start + idx(i, j), back_start + idx(i, j + 1)])
        faces.append([idx(i, j), back_start + idx(i, j + 1), idx(i, j + 1)])

    for i in range(height - 1):
        faces.append([idx(i, 0), back_start + idx(i, 0), back_start + idx(i + 1, 0)])
        faces.append([idx(i, 0), back_start + idx(i + 1, 0), idx(i + 1, 0)])
        j = width - 1
        faces.append([idx(i, j), idx(i + 1, j), back_start + idx(i + 1, j)])
        faces.append([idx(i, j), back_start + idx(i + 1, j), back_start + idx(i, j)])

    mesh = trimesh.Trimesh(vertices=vertices, faces=faces)

    # Add frame if requested
    if frame == "simple":
        frame_width = 5.0
        bounds = mesh.bounds
        frame_mesh = trimesh.creation.box([
            bounds[1, 0] - bounds[0, 0] + frame_width * 2,
            bounds[1, 1] - bounds[0, 1] + frame_width * 2,
            max_thickness
        ])
        inner = trimesh.creation.box([
            bounds[1, 0] - bounds[0, 0],
            bounds[1, 1] - bounds[0, 1],
            max_thickness + 1
        ])
        inner.vertices[:, 0] += (bounds[0, 0] + bounds[1, 0]) / 2
        inner.vertices[:, 1] += (bounds[0, 1] + bounds[1, 1]) / 2
        frame_mesh.vertices[:, 0] += (bounds[0, 0] + bounds[1, 0]) / 2
        frame_mesh.vertices[:, 1] += (bounds[0, 1] + bounds[1, 1]) / 2
        frame_mesh = frame_mesh.difference(inner)
        mesh = trimesh.util.concatenate([mesh, frame_mesh])

    mesh.vertices[:, 1] = -mesh.vertices[:, 1]
    mesh.vertices -= mesh.centroid
    mesh.vertices[:, 2] -= mesh.bounds[0, 2]

    mesh.export(output_path)
    validation = validate_mesh(mesh)

    return {
        "output_path": output_path,
        "file_size_bytes": Path(output_path).stat().st_size,
        "input_resolution": f"{width}x{height}",
        "lithophane_width_mm": width_mm,
        "lithophane_height_mm": actual_height,
        **validation
    }


# =============================================================================
# PNG TO SVG
# =============================================================================

def image_to_svg(
    image_path: str,
    output_path: str,
    smoothing: str = "medium",
    threshold: int = 127,
    simplify: float = 2.0,
    invert: bool = False
) -> dict:
    """
    Convert raster image to clean SVG.

    Best for: creating vector paths for slicer import.
    """
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise FileNotFoundError(f"Could not load image: {image_path}")

    # Apply smoothing
    smooth_values = {"none": 0, "low": 3, "medium": 5, "high": 9}
    blur_size = smooth_values.get(smoothing, 5)
    if blur_size > 0:
        img = cv2.GaussianBlur(img, (blur_size, blur_size), 0)

    _, binary = cv2.threshold(img, threshold, 255, cv2.THRESH_BINARY)

    if invert:
        binary = 255 - binary

    contours, hierarchy = cv2.findContours(binary, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    height, width = img.shape

    # Build SVG
    svg_parts = [
        f'<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">',
    ]

    for contour in contours:
        if len(contour) < 3:
            continue

        epsilon = simplify * cv2.arcLength(contour, True) / 100
        simplified = cv2.approxPolyDP(contour, epsilon, True)

        if len(simplified) < 3:
            continue

        points = simplified.reshape(-1, 2)
        path_data = f"M {points[0][0]},{points[0][1]}"
        for point in points[1:]:
            path_data += f" L {point[0]},{point[1]}"
        path_data += " Z"

        svg_parts.append(f'  <path d="{path_data}" fill="black" stroke="none"/>')

    svg_parts.append('</svg>')

    svg_content = '\n'.join(svg_parts)
    with open(output_path, 'w') as f:
        f.write(svg_content)

    return {
        "output_path": output_path,
        "file_size_bytes": Path(output_path).stat().st_size,
        "input_resolution": f"{width}x{height}",
        "contours_converted": len(contours),
        "svg_dimensions": {"width": width, "height": height}
    }


def validate_stl_file(stl_path: str) -> dict:
    """Validate an STL file for 3D printing."""
    mesh = trimesh.load(stl_path)
    return validate_mesh(mesh)
