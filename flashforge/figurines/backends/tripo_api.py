"""
Tripo AI API client for image-to-3D generation.

API Documentation: https://platform.tripo3d.ai/docs
Free tier: 300 credits/month (~300 models)
"""

import os
import time
import base64
import tempfile
from pathlib import Path
from typing import Optional

import requests
from PIL import Image
import numpy as np


class TripoClient:
    """
    Tripo AI API client for generating 3D meshes from images.

    Usage:
        client = TripoClient()  # Uses TRIPO_API_KEY env var
        mesh = client.generate("input.png")
        mesh.export("output.stl")
    """

    BASE_URL = "https://api.tripo3d.ai/v2/openapi"

    def __init__(
        self,
        api_key: Optional[str] = None,
        timeout: int = 300,
        verbose: bool = True
    ):
        """
        Initialize Tripo API client.

        Args:
            api_key: Tripo API key (or set TRIPO_API_KEY env var)
            timeout: Max wait time for generation (seconds)
            verbose: Print progress updates
        """
        self.api_key = (
            api_key or
            os.environ.get("TRIPO_API_KEY") or
            os.environ.get("TRIPO_3D_API_TOKEN")
        )
        if not self.api_key:
            raise ValueError(
                "Tripo API key required.\n"
                "1. Sign up at https://tripo3d.ai (free: 300 models/month)\n"
                "2. Get your API key from the dashboard\n"
                "3. Set: export TRIPO_API_KEY='your_key'"
            )

        self.timeout = timeout
        self.verbose = verbose
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
        }

    def generate(self, image_path: str) -> "trimesh.Trimesh":
        """
        Generate 3D mesh from an image.

        Args:
            image_path: Path to input image (PNG, JPG, WebP)

        Returns:
            trimesh.Trimesh object ready for export
        """
        import trimesh

        # Step 1: Upload image and create task
        if self.verbose:
            print(f"[Tripo] Uploading image: {image_path}")

        task_id = self._create_task(image_path)

        if self.verbose:
            print(f"[Tripo] Task created: {task_id}")
            print("[Tripo] Generating 3D model (this takes 30-60 seconds)...")

        # Step 2: Wait for completion
        result = self._wait_for_task(task_id)

        # Step 3: Download mesh
        if self.verbose:
            print("[Tripo] Downloading mesh...")

        # Get GLB URL from result
        model_data = result.get("model", result.get("pbr_model", {}))
        mesh_url = None

        # Try different formats in preference order
        for fmt in ["glb", "obj", "fbx"]:
            if fmt in model_data:
                mesh_url = model_data[fmt].get("url") if isinstance(model_data[fmt], dict) else model_data[fmt]
                if mesh_url:
                    break

        if not mesh_url:
            raise RuntimeError(f"No mesh URL in Tripo response. Got: {result}")

        mesh = self._download_mesh(mesh_url)

        if self.verbose:
            print(f"[Tripo] Success! Mesh has {len(mesh.vertices)} vertices, {len(mesh.faces)} faces")

        return mesh

    def _create_task(self, image_path: str) -> str:
        """Upload image and create generation task."""
        # Read and encode image
        img = Image.open(image_path)

        # Convert to RGB if necessary (remove alpha channel)
        if img.mode == 'RGBA':
            background = Image.new('RGB', img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[3])
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')

        # Save to bytes
        import io
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        image_bytes = buffer.getvalue()

        # Base64 encode
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")

        # Create task
        payload = {
            "type": "image_to_model",
            "file": {
                "type": "png",
                "data": image_b64
            }
        }

        response = requests.post(
            f"{self.BASE_URL}/task",
            headers={**self.headers, "Content-Type": "application/json"},
            json=payload,
            timeout=60
        )

        if response.status_code != 200:
            raise RuntimeError(f"Tripo API error: {response.status_code} - {response.text}")

        data = response.json()
        if data.get("code") != 0:
            raise RuntimeError(f"Tripo task creation failed: {data.get('message')}")

        return data["data"]["task_id"]

    def _wait_for_task(self, task_id: str, poll_interval: float = 3.0) -> dict:
        """Poll task status until completion."""
        start_time = time.time()
        last_progress = -1

        while time.time() - start_time < self.timeout:
            response = requests.get(
                f"{self.BASE_URL}/task/{task_id}",
                headers=self.headers,
                timeout=30
            )

            if response.status_code != 200:
                raise RuntimeError(f"Tripo status check failed: {response.status_code}")

            data = response.json()
            if data.get("code") != 0:
                raise RuntimeError(f"Tripo error: {data.get('message')}")

            task_data = data["data"]
            status = task_data["status"]

            if status == "success":
                return task_data["output"]
            elif status == "failed":
                raise RuntimeError(f"Tripo generation failed: {task_data.get('message', 'Unknown error')}")
            elif status in ["queued", "running"]:
                progress = task_data.get("progress", 0)
                if self.verbose and progress != last_progress:
                    print(f"[Tripo] Progress: {progress}%")
                    last_progress = progress
                time.sleep(poll_interval)
            else:
                raise RuntimeError(f"Unknown Tripo status: {status}")

        raise TimeoutError(f"Tripo generation timed out after {self.timeout}s")

    def _download_mesh(self, url: str) -> "trimesh.Trimesh":
        """Download mesh from URL and load with trimesh."""
        import trimesh

        response = requests.get(url, timeout=120)
        if response.status_code != 200:
            raise RuntimeError(f"Failed to download mesh: {response.status_code}")

        # Determine file extension from URL
        ext = ".glb"
        if ".obj" in url.lower():
            ext = ".obj"
        elif ".fbx" in url.lower():
            ext = ".fbx"

        # Save to temp file and load
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as f:
            f.write(response.content)
            temp_path = f.name

        try:
            scene_or_mesh = trimesh.load(temp_path)

            # Handle scene (multiple meshes) vs single mesh
            if isinstance(scene_or_mesh, trimesh.Scene):
                # Combine all meshes into one
                meshes = []
                for name, geom in scene_or_mesh.geometry.items():
                    if isinstance(geom, trimesh.Trimesh):
                        meshes.append(geom)
                if meshes:
                    mesh = trimesh.util.concatenate(meshes)
                else:
                    raise RuntimeError("No valid meshes in downloaded file")
            else:
                mesh = scene_or_mesh

            return mesh
        finally:
            os.unlink(temp_path)

    def get_balance(self) -> dict:
        """Get current API credit balance."""
        response = requests.get(
            f"{self.BASE_URL}/user/balance",
            headers=self.headers,
            timeout=30
        )

        if response.status_code != 200:
            raise RuntimeError(f"Failed to get balance: {response.status_code}")

        return response.json().get("data", {})


def generate_figurine(
    image_path: str,
    output_path: str = None,
    scale_mm: float = 80,
    add_base: bool = True,
    base_height_mm: float = 2,
    api_key: str = None,
    verbose: bool = True
) -> str:
    """
    High-level function to generate a 3D figurine from an image.

    Args:
        image_path: Path to input image
        output_path: Path for output STL (default: input_name.stl)
        scale_mm: Target height in mm
        add_base: Add flat base for printing
        base_height_mm: Base height in mm
        api_key: Tripo API key (or use env var)
        verbose: Print progress

    Returns:
        Path to generated STL file
    """
    import trimesh

    # Default output path
    if output_path is None:
        output_path = str(Path(image_path).with_suffix(".stl"))

    # Generate mesh via API
    client = TripoClient(api_key=api_key, verbose=verbose)
    mesh = client.generate(image_path)

    # Scale to target height
    bounds = mesh.bounds
    current_height = bounds[1, 2] - bounds[0, 2]
    if current_height > 0:
        scale_factor = scale_mm / current_height
        mesh.apply_scale(scale_factor)
        if verbose:
            print(f"[Post] Scaled to {scale_mm}mm height")

    # Center on XY origin
    centroid = mesh.centroid
    mesh.vertices[:, 0] -= centroid[0]
    mesh.vertices[:, 1] -= centroid[1]

    # Move to sit on Z=0
    mesh.vertices[:, 2] -= mesh.bounds[0, 2]

    # Add base if requested
    if add_base:
        bounds = mesh.bounds
        base_width = (bounds[1, 0] - bounds[0, 0]) * 1.2
        base_depth = (bounds[1, 1] - bounds[0, 1]) * 1.2

        base = trimesh.creation.box([base_width, base_depth, base_height_mm])
        base.apply_translation([0, 0, base_height_mm / 2])

        # Move mesh up
        mesh.vertices[:, 2] += base_height_mm

        # Combine
        mesh = trimesh.util.concatenate([base, mesh])
        if verbose:
            print(f"[Post] Added {base_height_mm}mm base")

    # Export
    mesh.export(output_path)

    if verbose:
        final_bounds = mesh.bounds
        dims = final_bounds[1] - final_bounds[0]
        print(f"[Done] Exported: {output_path}")
        print(f"[Done] Dimensions: {dims[0]:.1f} x {dims[1]:.1f} x {dims[2]:.1f} mm")

    return output_path
