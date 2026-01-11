"""
Tripo AI API backend for image-to-3D generation.

API Documentation: https://www.tripo3d.ai/api
Pricing: $0.20-$0.40 per model
"""

import os
import time
import tempfile
from pathlib import Path
from typing import Optional, Literal
import requests

from ..router import BaseBackend


class TripoBackend(BaseBackend):
    """
    Tripo AI cloud API backend.
    
    Generates 3D meshes from images using Tripo's image-to-3D API.
    
    Pricing:
        - $0.20 per model (no texture)
        - $0.30 per model (standard texture)
        - $0.40 per model (HD texture)
    
    Example:
        backend = TripoBackend(api_key="your_key")
        mesh = backend.generate("input.png")
    """
    
    BASE_URL = "https://api.tripo3d.ai/v2/openapi"
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model_version: str = "v2.5",
        texture: Literal["none", "standard", "hd"] = "standard",
        timeout: int = 300,
        verbose: bool = False
    ):
        """
        Initialize Tripo API backend.
        
        Args:
            api_key: Tripo API key (or use TRIPO_API_KEY env var)
            model_version: Model version to use
            texture: Texture quality (none, standard, hd)
            timeout: Request timeout in seconds
            verbose: Enable verbose output
        """
        super().__init__(verbose=verbose)
        
        self.api_key = api_key or os.environ.get("TRIPO_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Tripo API key required. Set TRIPO_API_KEY environment variable "
                "or pass api_key parameter."
            )
        
        self.model_version = model_version
        self.texture = texture
        self.timeout = timeout
        
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    def generate(self, image) -> "trimesh.Trimesh":
        """
        Generate 3D mesh from image using Tripo API.
        
        Args:
            image: Input image (path or numpy array)
            
        Returns:
            trimesh.Trimesh object
        """
        import trimesh
        
        # Load and prepare image
        image_array = self._load_image(image)
        
        # Upload image and get task ID
        if self.verbose:
            print("[Tripo] Uploading image...")
        
        task_id = self._create_task(image_array)
        
        if self.verbose:
            print(f"[Tripo] Task created: {task_id}")
            print("[Tripo] Waiting for generation...")
        
        # Poll for completion
        result = self._wait_for_completion(task_id)
        
        # Download mesh
        if self.verbose:
            print("[Tripo] Downloading mesh...")
        
        mesh_url = result.get("model", {}).get("glb", {}).get("url")
        if not mesh_url:
            raise RuntimeError("No mesh URL in Tripo response")
        
        mesh = self._download_mesh(mesh_url)
        
        if self.verbose:
            print(f"[Tripo] Generated mesh with {len(mesh.vertices)} vertices")
        
        return mesh
    
    def _create_task(self, image_array) -> str:
        """Create image-to-3D task and return task ID."""
        import base64
        from PIL import Image
        import io
        
        # Convert to PNG bytes
        img = Image.fromarray(image_array)
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
            },
            "model_version": self.model_version,
            "texture": self.texture != "none",
            "texture_quality": self.texture if self.texture != "none" else None
        }
        
        response = requests.post(
            f"{self.BASE_URL}/task",
            headers=self.headers,
            json=payload,
            timeout=60
        )
        
        if response.status_code != 200:
            raise RuntimeError(f"Tripo API error: {response.status_code} - {response.text}")
        
        data = response.json()
        if data.get("code") != 0:
            raise RuntimeError(f"Tripo task creation failed: {data.get('message')}")
        
        return data["data"]["task_id"]
    
    def _wait_for_completion(self, task_id: str, poll_interval: float = 2.0) -> dict:
        """Poll task status until completion."""
        start_time = time.time()
        
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
                raise RuntimeError(f"Tripo status error: {data.get('message')}")
            
            status = data["data"]["status"]
            
            if status == "success":
                return data["data"]["output"]
            elif status == "failed":
                raise RuntimeError(f"Tripo generation failed: {data['data'].get('message')}")
            elif status in ["queued", "running"]:
                if self.verbose:
                    progress = data["data"].get("progress", 0)
                    print(f"[Tripo] Progress: {progress}%")
                time.sleep(poll_interval)
            else:
                raise RuntimeError(f"Unknown Tripo status: {status}")
        
        raise TimeoutError(f"Tripo generation timed out after {self.timeout}s")
    
    def _download_mesh(self, url: str) -> "trimesh.Trimesh":
        """Download and load mesh from URL."""
        import trimesh
        
        response = requests.get(url, timeout=60)
        if response.status_code != 200:
            raise RuntimeError(f"Failed to download mesh: {response.status_code}")
        
        # Save to temp file and load with trimesh
        with tempfile.NamedTemporaryFile(suffix=".glb", delete=False) as f:
            f.write(response.content)
            temp_path = f.name
        
        try:
            mesh = trimesh.load(temp_path)
            # Handle scene vs mesh
            if isinstance(mesh, trimesh.Scene):
                mesh = mesh.to_mesh()
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
        
        data = response.json()
        return data.get("data", {})
