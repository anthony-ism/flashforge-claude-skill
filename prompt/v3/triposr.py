"""
TripoSR local GPU backend for image-to-3D generation.

Repository: https://github.com/VAST-AI-Research/TripoSR
License: MIT
Requirements: 6GB+ VRAM, CUDA compute capability 7.5+ (or 6.1 with PyTorch 2.1)
"""

import os
from pathlib import Path
from typing import Optional
import numpy as np

from ..router import BaseBackend


class TripoSRBackend(BaseBackend):
    """
    TripoSR local GPU backend.
    
    Fast, lightweight image-to-3D using the open-source TripoSR model.
    
    Requirements:
        - 6GB+ VRAM
        - CUDA compute capability 7.5+ (or 6.1 with PyTorch 2.1)
        - PyTorch with CUDA support
    
    Example:
        backend = TripoSRBackend()
        mesh = backend.generate("input.png")
    """
    
    MODEL_REPO = "stabilityai/TripoSR"
    
    def __init__(
        self,
        device: str = "cuda:0",
        dtype: str = "float16",
        chunk_size: int = 8192,
        verbose: bool = False
    ):
        """
        Initialize TripoSR backend.
        
        Args:
            device: CUDA device to use
            dtype: Data type (float16 or float32)
            chunk_size: Chunk size for marching cubes
            verbose: Enable verbose output
        """
        super().__init__(verbose=verbose)
        
        self.device = device
        self.dtype = dtype
        self.chunk_size = chunk_size
        
        self._model = None
        self._initialized = False
    
    def _ensure_initialized(self):
        """Lazy initialization of model."""
        if self._initialized:
            return
        
        if self.verbose:
            print("[TripoSR] Loading model...")
        
        try:
            import torch
            from tsr.system import TSR
            
            # Check CUDA
            if not torch.cuda.is_available():
                raise RuntimeError(
                    "CUDA not available. TripoSR requires a CUDA-capable GPU. "
                    "Use --backend api for cloud processing."
                )
            
            # Load model
            self._model = TSR.from_pretrained(
                self.MODEL_REPO,
                config_name="config.yaml",
                weight_name="model.ckpt"
            )
            
            # Set dtype
            if self.dtype == "float16":
                self._model.to(torch.float16)
            
            # Move to device
            self._model.to(self.device)
            self._model.eval()
            
            self._initialized = True
            
            if self.verbose:
                print(f"[TripoSR] Model loaded on {self.device}")
                
        except ImportError as e:
            raise ImportError(
                "TripoSR not installed. Install with:\n"
                "  git clone https://github.com/VAST-AI-Research/TripoSR\n"
                "  cd TripoSR && pip install -r requirements.txt"
            ) from e
    
    def generate(self, image) -> "trimesh.Trimesh":
        """
        Generate 3D mesh from image using TripoSR.
        
        Args:
            image: Input image (path or numpy array)
            
        Returns:
            trimesh.Trimesh object
        """
        import torch
        import trimesh
        from PIL import Image
        
        self._ensure_initialized()
        
        # Load image
        if isinstance(image, (str, Path)):
            image = Image.open(image).convert("RGB")
        elif isinstance(image, np.ndarray):
            image = Image.fromarray(image).convert("RGB")
        
        if self.verbose:
            print(f"[TripoSR] Processing image: {image.size}")
        
        # Run inference
        with torch.no_grad():
            # Preprocess
            scene_codes = self._model([image], device=self.device)
            
            # Generate mesh
            meshes = self._model.extract_mesh(
                scene_codes,
                resolution=256,
                threshold=25.0
            )
        
        mesh = meshes[0]
        
        if self.verbose:
            print(f"[TripoSR] Generated mesh: {len(mesh.vertices)} vertices, {len(mesh.faces)} faces")
        
        # Convert to trimesh
        trimesh_mesh = trimesh.Trimesh(
            vertices=mesh.vertices,
            faces=mesh.faces,
            vertex_colors=mesh.vertex_colors if hasattr(mesh, 'vertex_colors') else None
        )
        
        return trimesh_mesh
    
    def generate_with_options(
        self,
        image,
        resolution: int = 256,
        threshold: float = 25.0,
        remove_background: bool = True
    ) -> "trimesh.Trimesh":
        """
        Generate with additional options.
        
        Args:
            image: Input image
            resolution: Marching cubes resolution
            threshold: Density threshold
            remove_background: Auto-remove background
            
        Returns:
            trimesh.Trimesh object
        """
        import torch
        import trimesh
        from PIL import Image
        
        self._ensure_initialized()
        
        # Load image
        if isinstance(image, (str, Path)):
            image = Image.open(image).convert("RGB")
        elif isinstance(image, np.ndarray):
            image = Image.fromarray(image).convert("RGB")
        
        # Optional background removal
        if remove_background:
            try:
                import rembg
                image = rembg.remove(image)
                image = image.convert("RGB")
            except ImportError:
                if self.verbose:
                    print("[TripoSR] rembg not installed, skipping background removal")
        
        # Run inference
        with torch.no_grad():
            scene_codes = self._model([image], device=self.device)
            meshes = self._model.extract_mesh(
                scene_codes,
                resolution=resolution,
                threshold=threshold
            )
        
        mesh = meshes[0]
        
        return trimesh.Trimesh(
            vertices=mesh.vertices,
            faces=mesh.faces,
            vertex_colors=mesh.vertex_colors if hasattr(mesh, 'vertex_colors') else None
        )


class TripoSRBackendFallback(BaseBackend):
    """
    Fallback TripoSR backend that attempts to use PyTorch 2.1 for older GPUs.
    
    Use this if you have a GTX 1080 Ti or similar with compute capability < 7.5.
    """
    
    def __init__(self, verbose: bool = False):
        super().__init__(verbose=verbose)
        self._check_pytorch_version()
    
    def _check_pytorch_version(self):
        """Check PyTorch version and warn if needed."""
        try:
            import torch
            version = torch.__version__
            
            if version.startswith("2.1"):
                if self.verbose:
                    print(f"[TripoSR] Using PyTorch {version} (compatible with older GPUs)")
            elif version.startswith("2."):
                major_minor = ".".join(version.split(".")[:2])
                if float(major_minor[2:]) > 2.1:
                    print(f"[WARNING] PyTorch {version} may not support GPUs with compute < 7.5")
                    print("[WARNING] If you get errors, install PyTorch 2.1:")
                    print("  pip install torch==2.1.2 --index-url https://download.pytorch.org/whl/cu118")
        except ImportError:
            pass
    
    def generate(self, image) -> "trimesh.Trimesh":
        """Delegate to standard backend."""
        backend = TripoSRBackend(verbose=self.verbose)
        return backend.generate(image)
