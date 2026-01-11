"""
Shared utilities for FlashForge 2D-to-3D conversion scripts.
"""

import os
from pathlib import Path

import numpy as np
from PIL import Image
import trimesh


# FlashForge Adventurer 5M build volume (mm)
MAX_BUILD_X = 220
MAX_BUILD_Y = 220
MAX_BUILD_Z = 220


def load_image(image_path: str, grayscale: bool = True) -> np.ndarray:
    """
    Load an image file and return as numpy array.

    Args:
        image_path: Path to input image (PNG, JPG, etc.)
        grayscale: Convert to grayscale if True

    Returns:
        numpy array of image data

    Raises:
        FileNotFoundError: If image file doesn't exist
        ValueError: If file is not a valid image
    """
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Image file not found: {image_path}")

    try:
        img = Image.open(image_path)
        if grayscale:
            img = img.convert('L')
        else:
            img = img.convert('RGBA')
        return np.array(img)
    except Exception as e:
        raise ValueError(f"Failed to load image: {e}")


def preprocess_image(
    img_array: np.ndarray,
    invert: bool = False,
    smooth_radius: int = 0,
    target_size: tuple = None
) -> np.ndarray:
    """
    Preprocess image array for 3D conversion.

    Args:
        img_array: Input image as numpy array
        invert: Invert brightness values
        smooth_radius: Gaussian blur radius (0 = no smoothing)
        target_size: Optional (width, height) to resize to

    Returns:
        Preprocessed numpy array
    """
    from PIL import ImageFilter

    img = Image.fromarray(img_array)

    if target_size:
        img = img.resize(target_size, Image.Resampling.LANCZOS)

    if smooth_radius > 0:
        img = img.filter(ImageFilter.GaussianBlur(radius=smooth_radius))

    result = np.array(img)

    if invert:
        result = 255 - result

    return result


def validate_mesh(mesh: trimesh.Trimesh) -> dict:
    """
    Validate that a mesh is suitable for 3D printing.

    Args:
        mesh: trimesh.Trimesh object to validate

    Returns:
        dict with validation results:
            - is_valid: bool
            - is_watertight: bool
            - bounds: mesh bounds in mm
            - volume: mesh volume in mm³
            - issues: list of any problems found
    """
    issues = []

    is_watertight = mesh.is_watertight
    if not is_watertight:
        issues.append("Mesh is not watertight (has holes)")

    bounds = mesh.bounds
    dimensions = bounds[1] - bounds[0]

    if dimensions[0] > MAX_BUILD_X:
        issues.append(f"X dimension ({dimensions[0]:.1f}mm) exceeds build volume ({MAX_BUILD_X}mm)")
    if dimensions[1] > MAX_BUILD_Y:
        issues.append(f"Y dimension ({dimensions[1]:.1f}mm) exceeds build volume ({MAX_BUILD_Y}mm)")
    if dimensions[2] > MAX_BUILD_Z:
        issues.append(f"Z dimension ({dimensions[2]:.1f}mm) exceeds build volume ({MAX_BUILD_Z}mm)")

    volume = mesh.volume if is_watertight else None

    return {
        'is_valid': len(issues) == 0,
        'is_watertight': is_watertight,
        'bounds': bounds,
        'dimensions': dimensions,
        'volume': volume,
        'issues': issues
    }


def scale_to_fit(
    mesh: trimesh.Trimesh,
    max_x: float = None,
    max_y: float = None,
    max_z: float = None
) -> trimesh.Trimesh:
    """
    Scale mesh to fit within specified bounds while maintaining aspect ratio.

    Args:
        mesh: trimesh.Trimesh to scale
        max_x: Maximum X dimension in mm
        max_y: Maximum Y dimension in mm
        max_z: Maximum Z dimension in mm

    Returns:
        Scaled trimesh.Trimesh
    """
    max_x = max_x or MAX_BUILD_X
    max_y = max_y or MAX_BUILD_Y
    max_z = max_z or MAX_BUILD_Z

    bounds = mesh.bounds
    dimensions = bounds[1] - bounds[0]

    scale_factors = []
    if dimensions[0] > 0:
        scale_factors.append(max_x / dimensions[0])
    if dimensions[1] > 0:
        scale_factors.append(max_y / dimensions[1])
    if dimensions[2] > 0:
        scale_factors.append(max_z / dimensions[2])

    if not scale_factors:
        return mesh

    scale = min(scale_factors)
    if scale < 1.0:
        mesh.apply_scale(scale)

    return mesh


def export_stl(mesh: trimesh.Trimesh, output_path: str, validate: bool = True) -> dict:
    """
    Export mesh to STL file with optional validation.

    Args:
        mesh: trimesh.Trimesh to export
        output_path: Path for output STL file
        validate: Run validation before export

    Returns:
        dict with export results including validation info
    """
    result = {'output_path': output_path}

    if validate:
        validation = validate_mesh(mesh)
        result['validation'] = validation
        if not validation['is_valid']:
            print(f"Warning: Mesh has issues: {validation['issues']}")

    # Ensure output directory exists
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    mesh.export(output_path)
    result['success'] = True
    result['file_size'] = os.path.getsize(output_path)

    return result


def print_summary(result: dict) -> None:
    """Print a summary of the conversion result."""
    print(f"\nSTL exported: {result['output_path']}")
    print(f"File size: {result['file_size'] / 1024:.1f} KB")

    if 'validation' in result:
        v = result['validation']
        dims = v['dimensions']
        print(f"Dimensions: {dims[0]:.1f} x {dims[1]:.1f} x {dims[2]:.1f} mm")
        print(f"Watertight: {'Yes' if v['is_watertight'] else 'No'}")
        if v['volume']:
            print(f"Volume: {v['volume']:.1f} mm³")
        if v['issues']:
            print("Issues:")
            for issue in v['issues']:
                print(f"  - {issue}")
