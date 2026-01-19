#!/usr/bin/env python3
"""
Fix 3D models for printing: remove floating pieces, scale, add base.
"""

import argparse
import trimesh
import numpy as np
from pathlib import Path


def auto_orient_upright(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    """
    Orient a mesh so its longest axis is vertical (Z-up).

    Uses PCA to find principal axes and rotates so the longest
    dimension becomes the height. Useful for figurines that are
    lying on their back/side.
    """
    # Get principal axes using PCA on vertices
    centered = mesh.vertices - mesh.vertices.mean(axis=0)
    cov = np.cov(centered.T)
    eigenvalues, eigenvectors = np.linalg.eigh(cov)

    # Sort by eigenvalue (variance) - largest = longest axis
    order = np.argsort(eigenvalues)[::-1]
    eigenvalues = eigenvalues[order]
    eigenvectors = eigenvectors[:, order]

    # Current longest axis (first principal component)
    longest_axis = eigenvectors[:, 0]

    # We want longest axis to be Z (up)
    target_axis = np.array([0, 0, 1])

    # Check if already mostly aligned with Z
    alignment = abs(np.dot(longest_axis, target_axis))
    if alignment > 0.9:
        print("  Model already oriented upright")
        return mesh

    # Calculate rotation to align longest axis with Z
    # Using Rodrigues' rotation formula
    v = np.cross(longest_axis, target_axis)
    s = np.linalg.norm(v)
    c = np.dot(longest_axis, target_axis)

    if s < 1e-6:
        # Axes are parallel or anti-parallel
        if c < 0:
            # 180 degree rotation around X
            rotation_matrix = np.array([
                [1, 0, 0],
                [0, -1, 0],
                [0, 0, -1]
            ])
        else:
            rotation_matrix = np.eye(3)
    else:
        # Skew-symmetric cross-product matrix
        vx = np.array([
            [0, -v[2], v[1]],
            [v[2], 0, -v[0]],
            [-v[1], v[0], 0]
        ])
        rotation_matrix = np.eye(3) + vx + vx @ vx * ((1 - c) / (s * s))

    # Apply rotation
    mesh.apply_transform(
        trimesh.transformations.compose_matrix(angles=None, translate=None, scale=None)
    )
    mesh.vertices = mesh.vertices @ rotation_matrix.T

    print(f"  Rotated model to stand upright (alignment was {alignment:.2f})")
    return mesh


def fix_model(
    input_path: str,
    output_path: str = None,
    target_height_mm: float = 80.0,
    base_height_mm: float = 0,
    base_padding_mm: float = 3.0,
    remove_floating: bool = True,
    min_body_ratio: float = 0.01,
    auto_orient: bool = True,
) -> dict:
    """
    Fix a 3D model for printing.

    Args:
        input_path: Path to input STL/GLB/OBJ file
        output_path: Path to output STL file (default: input_fixed.stl)
        target_height_mm: Target height in mm
        base_height_mm: Height of the base plate (0 = no base)
        base_padding_mm: Padding around the model for the base
        remove_floating: Remove disconnected floating pieces
        min_body_ratio: Minimum volume ratio to keep (relative to largest body)
        auto_orient: Automatically orient model upright (longest axis = Z)

    Returns:
        dict with fix results
    """
    input_path = Path(input_path)
    if output_path is None:
        output_path = input_path.parent / f"{input_path.stem}_fixed.stl"
    else:
        output_path = Path(output_path)

    print(f"Loading {input_path}...")
    mesh = trimesh.load(str(input_path))

    # Handle scenes (multiple objects)
    if isinstance(mesh, trimesh.Scene):
        print("Converting scene to single mesh...")
        mesh = mesh.to_geometry()

    # Auto-orient to stand upright (before measuring original dims)
    if auto_orient:
        print("\nAuto-orienting model...")
        mesh = auto_orient_upright(mesh)

    original_dims = mesh.bounding_box.extents.copy()
    original_faces = len(mesh.faces)

    print(f"\nOriginal model:")
    print(f"  Dimensions: {original_dims[0]:.2f} x {original_dims[1]:.2f} x {original_dims[2]:.2f} mm")
    print(f"  Faces: {original_faces:,}")

    # Split into separate bodies
    bodies = mesh.split(only_watertight=False)
    print(f"  Separate bodies: {len(bodies)}")

    # Remove floating pieces if requested
    removed_bodies = 0
    if remove_floating and len(bodies) > 1:
        # Calculate volumes
        body_volumes = []
        for body in bodies:
            vol = abs(body.volume) if body.is_volume else 0
            # Fallback to bounding box volume if mesh volume fails
            if vol == 0:
                vol = np.prod(body.bounding_box.extents)
            body_volumes.append(vol)

        max_vol = max(body_volumes)

        # Keep only bodies above the threshold
        kept_bodies = []
        for body, vol in zip(bodies, body_volumes):
            ratio = vol / max_vol if max_vol > 0 else 0
            if ratio >= min_body_ratio:
                kept_bodies.append(body)
            else:
                removed_bodies += 1

        if kept_bodies:
            mesh = trimesh.util.concatenate(kept_bodies)
            print(f"\nRemoved {removed_bodies} floating piece(s)")

    # Calculate scale factor to reach target height
    current_height = mesh.bounding_box.extents[2]  # Z is typically up
    scale_factor = target_height_mm / current_height

    # Apply scale
    mesh.apply_scale(scale_factor)

    # Center the model on XY and place bottom at Z=0
    bounds = mesh.bounds
    center_xy = (bounds[0][:2] + bounds[1][:2]) / 2
    mesh.apply_translation([-center_xy[0], -center_xy[1], -bounds[0][2]])

    scaled_dims = mesh.bounding_box.extents.copy()
    print(f"\nScaled model:")
    print(f"  Dimensions: {scaled_dims[0]:.2f} x {scaled_dims[1]:.2f} x {scaled_dims[2]:.2f} mm")
    print(f"  Scale factor: {scale_factor:.2f}x")

    # Add base plate
    if base_height_mm > 0:
        bounds = mesh.bounds
        base_width = scaled_dims[0] + 2 * base_padding_mm
        base_depth = scaled_dims[1] + 2 * base_padding_mm

        # Create base plate
        base = trimesh.creation.box(
            extents=[base_width, base_depth, base_height_mm]
        )

        # Position base below the model
        base.apply_translation([0, 0, -base_height_mm / 2])

        # Move model up by base height
        mesh.apply_translation([0, 0, base_height_mm])

        # Combine
        mesh = trimesh.util.concatenate([mesh, base])

        print(f"\nAdded base plate:")
        print(f"  Size: {base_width:.1f} x {base_depth:.1f} x {base_height_mm:.1f} mm")

    final_dims = mesh.bounding_box.extents
    print(f"\nFinal model:")
    print(f"  Dimensions: {final_dims[0]:.2f} x {final_dims[1]:.2f} x {final_dims[2]:.2f} mm")
    print(f"  Faces: {len(mesh.faces):,}")
    print(f"  Watertight: {mesh.is_watertight}")

    # Check if it fits the build volume
    max_dim = 220  # FlashForge Adventurer 5M
    fits = all(d <= max_dim for d in final_dims)
    print(f"  Fits 220mm build volume: {fits}")

    # Export
    mesh.export(str(output_path))
    file_size = output_path.stat().st_size / (1024 * 1024)
    print(f"\nSaved to: {output_path}")
    print(f"File size: {file_size:.1f} MB")

    return {
        "original_dims": original_dims.tolist(),
        "final_dims": final_dims.tolist(),
        "scale_factor": scale_factor,
        "removed_bodies": removed_bodies,
        "faces": len(mesh.faces),
        "watertight": mesh.is_watertight,
        "fits_build_volume": fits,
        "output_path": str(output_path),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Fix 3D models for printing: scale, remove floating pieces, add base"
    )
    parser.add_argument("input", help="Input STL/GLB/OBJ file")
    parser.add_argument("-o", "--output", help="Output STL file")
    parser.add_argument(
        "--height", type=float, default=80.0,
        help="Target height in mm (default: 80)"
    )
    parser.add_argument(
        "--base", type=float, default=0,
        help="Base plate height in mm (default: 0 = no base)"
    )
    parser.add_argument(
        "--padding", type=float, default=3.0,
        help="Base padding around model in mm (default: 3)"
    )
    parser.add_argument(
        "--keep-floating", action="store_true",
        help="Keep floating/disconnected pieces"
    )
    parser.add_argument(
        "--no-orient", action="store_true",
        help="Disable auto-orientation (model stays in original orientation)"
    )

    args = parser.parse_args()

    fix_model(
        input_path=args.input,
        output_path=args.output,
        target_height_mm=args.height,
        base_height_mm=args.base,
        base_padding_mm=args.padding,
        remove_floating=not args.keep_floating,
        auto_orient=not args.no_orient,
    )


if __name__ == "__main__":
    main()
