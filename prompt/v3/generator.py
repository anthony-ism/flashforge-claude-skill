"""
FlashForge Figurine Generator

Main entry point for image-to-3D generation with automatic backend selection.
"""

import os
from pathlib import Path
from typing import Optional, Union, Literal
from dataclasses import dataclass

from .config import Config, load_config
from .utils.hardware import detect_gpu, GPUInfo
from .backends.router import BackendRouter


@dataclass
class GenerationResult:
    """Result of a figurine generation."""
    success: bool
    mesh_path: Optional[Path]
    backend_used: str
    generation_time: float
    error: Optional[str] = None
    warnings: list[str] = None
    
    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


class FigurineGenerator:
    """
    Main class for generating 3D figurines from images.
    
    Automatically selects between local GPU inference and cloud API
    based on available hardware, or allows explicit backend selection.
    
    Example:
        # Auto-detect best backend
        generator = FigurineGenerator()
        result = generator.generate("input.png")
        
        # Force API backend
        generator = FigurineGenerator(backend="api", provider="tripo")
        result = generator.generate("input.png")
        
        # Force local backend with specific model
        generator = FigurineGenerator(backend="local", model="triposr")
        result = generator.generate("input.png")
    """
    
    SUPPORTED_BACKENDS = ["auto", "local", "api"]
    SUPPORTED_LOCAL_MODELS = ["triposr", "hunyuan", "trellis"]
    SUPPORTED_API_PROVIDERS = ["tripo", "meshy"]
    
    def __init__(
        self,
        backend: Literal["auto", "local", "api"] = "auto",
        model: Optional[str] = None,
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
        config_path: Optional[str] = None,
        verbose: bool = False
    ):
        """
        Initialize the figurine generator.
        
        Args:
            backend: Backend selection - "auto", "local", or "api"
            model: Local model to use (triposr, hunyuan, trellis)
            provider: API provider (tripo, meshy)
            api_key: API key (or use environment variable)
            config_path: Path to config file
            verbose: Enable verbose output
        """
        self.verbose = verbose
        self.config = load_config(config_path)
        
        # Store preferences
        self._requested_backend = backend
        self._requested_model = model
        self._requested_provider = provider
        self._api_key = api_key
        
        # Detect hardware
        self.gpu_info = detect_gpu()
        if self.verbose:
            self._print_gpu_info()
        
        # Initialize backend router
        self.router = BackendRouter(
            config=self.config,
            gpu_info=self.gpu_info,
            verbose=self.verbose
        )
        
        # Resolve actual backend to use
        self.backend, self.backend_config = self._resolve_backend()
        
        if self.verbose:
            print(f"[FigurineGenerator] Using backend: {self.backend}")
    
    def _print_gpu_info(self):
        """Print detected GPU information."""
        if self.gpu_info.available:
            print(f"[GPU] Detected: {self.gpu_info.name}")
            print(f"[GPU] VRAM: {self.gpu_info.vram_gb:.1f} GB")
            print(f"[GPU] Compute Capability: {self.gpu_info.compute_capability}")
            print(f"[GPU] CUDA Available: {self.gpu_info.cuda_available}")
        else:
            print("[GPU] No compatible GPU detected")
    
    def _resolve_backend(self) -> tuple[str, dict]:
        """
        Resolve which backend to use based on request and hardware.
        
        Returns:
            Tuple of (backend_name, backend_config)
        """
        backend = self._requested_backend
        
        if backend == "api":
            # Explicit API request
            provider = self._requested_provider or self.config.api.provider
            return "api", {
                "provider": provider,
                "api_key": self._api_key or self._get_api_key(provider)
            }
        
        if backend == "local":
            # Explicit local request - validate hardware
            if not self.gpu_info.available:
                raise RuntimeError(
                    "Local backend requested but no GPU available. "
                    "Use --backend api instead."
                )
            
            if self.gpu_info.compute_capability < 7.5:
                print(f"[WARNING] GPU compute capability {self.gpu_info.compute_capability} < 7.5")
                print("[WARNING] Modern PyTorch may not support this GPU.")
                print("[WARNING] If generation fails, use --backend api")
            
            model = self._requested_model or self.config.local.model
            return "local", {"model": model}
        
        # Auto-detection
        if backend == "auto":
            return self._auto_select_backend()
        
        raise ValueError(f"Unknown backend: {backend}")
    
    def _auto_select_backend(self) -> tuple[str, dict]:
        """
        Automatically select the best backend based on hardware.
        
        Priority:
        1. Local GPU if available and compatible
        2. API fallback otherwise
        """
        # Check for compatible GPU
        if self.gpu_info.available:
            if self.gpu_info.compute_capability >= 7.5:
                if self.gpu_info.vram_gb >= 6:
                    # Select model based on VRAM
                    if self.gpu_info.vram_gb >= 24:
                        model = "trellis"  # Best quality
                    elif self.gpu_info.vram_gb >= 12:
                        model = "hunyuan"  # Good quality
                    else:
                        model = "triposr"  # Fast, low VRAM
                    
                    if self.verbose:
                        print(f"[Auto] Selected local backend with {model}")
                    return "local", {"model": model}
                else:
                    if self.verbose:
                        print(f"[Auto] GPU VRAM ({self.gpu_info.vram_gb}GB) too low, using API")
            else:
                if self.verbose:
                    print(f"[Auto] GPU compute capability too old, using API")
        else:
            if self.verbose:
                print("[Auto] No GPU detected, using API")
        
        # Fallback to API
        provider = self.config.api.provider
        return "api", {
            "provider": provider,
            "api_key": self._get_api_key(provider)
        }
    
    def _get_api_key(self, provider: str) -> str:
        """Get API key from environment or config."""
        env_var = f"{provider.upper()}_API_KEY"
        key = os.environ.get(env_var)
        
        if key:
            return key
        
        # Check config
        if provider == "tripo" and self.config.api.tripo.api_key:
            return self.config.api.tripo.api_key
        if provider == "meshy" and self.config.api.meshy.api_key:
            return self.config.api.meshy.api_key
        
        raise ValueError(
            f"API key not found for {provider}. "
            f"Set {env_var} environment variable or pass api_key parameter."
        )
    
    def generate(
        self,
        image_path: Union[str, Path],
        output_path: Optional[Union[str, Path]] = None,
        remove_background: bool = True,
        convert_to_matcap: bool = False,
        scale_mm: float = 80,
        add_base: bool = True,
        base_height_mm: float = 2,
        hollow: bool = False,
        wall_thickness_mm: float = 2,
        repair_mesh: bool = True,
        output_format: Literal["stl", "obj", "glb"] = "stl"
    ) -> GenerationResult:
        """
        Generate a 3D figurine from an image.
        
        Args:
            image_path: Path to input image
            output_path: Path for output file (auto-generated if None)
            remove_background: Remove background before processing
            convert_to_matcap: Convert to matcap (gray clay look)
            scale_mm: Target height in millimeters
            add_base: Add flat base for printing
            base_height_mm: Height of base in mm
            hollow: Hollow out the model (saves filament)
            wall_thickness_mm: Wall thickness if hollow
            repair_mesh: Attempt to repair mesh issues
            output_format: Output format (stl, obj, glb)
            
        Returns:
            GenerationResult with mesh path and metadata
        """
        import time
        start_time = time.time()
        
        image_path = Path(image_path)
        if not image_path.exists():
            return GenerationResult(
                success=False,
                mesh_path=None,
                backend_used=self.backend,
                generation_time=0,
                error=f"Input image not found: {image_path}"
            )
        
        # Generate output path if not provided
        if output_path is None:
            output_path = image_path.with_suffix(f".{output_format}")
        else:
            output_path = Path(output_path)
        
        warnings = []
        
        try:
            # Step 1: Preprocess image
            if self.verbose:
                print(f"[1/4] Preprocessing {image_path.name}...")
            
            processed_image = self._preprocess(
                image_path,
                remove_background=remove_background,
                convert_to_matcap=convert_to_matcap
            )
            
            # Step 2: Generate 3D mesh
            if self.verbose:
                print(f"[2/4] Generating 3D mesh via {self.backend}...")
            
            raw_mesh = self.router.generate(
                processed_image,
                backend=self.backend,
                config=self.backend_config
            )
            
            # Step 3: Post-process mesh
            if self.verbose:
                print("[3/4] Post-processing mesh...")
            
            processed_mesh, repair_warnings = self._postprocess(
                raw_mesh,
                repair=repair_mesh,
                scale_mm=scale_mm,
                add_base=add_base,
                base_height_mm=base_height_mm,
                hollow=hollow,
                wall_thickness_mm=wall_thickness_mm
            )
            warnings.extend(repair_warnings)
            
            # Step 4: Export
            if self.verbose:
                print(f"[4/4] Exporting to {output_path}...")
            
            self._export(processed_mesh, output_path, output_format)
            
            generation_time = time.time() - start_time
            
            if self.verbose:
                print(f"[Done] Generated in {generation_time:.1f}s")
            
            return GenerationResult(
                success=True,
                mesh_path=output_path,
                backend_used=self.backend,
                generation_time=generation_time,
                warnings=warnings
            )
            
        except Exception as e:
            generation_time = time.time() - start_time
            return GenerationResult(
                success=False,
                mesh_path=None,
                backend_used=self.backend,
                generation_time=generation_time,
                error=str(e),
                warnings=warnings
            )
    
    def _preprocess(
        self,
        image_path: Path,
        remove_background: bool,
        convert_to_matcap: bool
    ):
        """Preprocess image for 3D generation."""
        from .preprocessing import ImagePreprocessor
        
        preprocessor = ImagePreprocessor()
        return preprocessor.process(
            image_path,
            remove_background=remove_background,
            convert_to_matcap=convert_to_matcap,
            target_resolution=self.config.preprocessing.target_resolution
        )
    
    def _postprocess(
        self,
        mesh,
        repair: bool,
        scale_mm: float,
        add_base: bool,
        base_height_mm: float,
        hollow: bool,
        wall_thickness_mm: float
    ) -> tuple:
        """Post-process mesh for printing."""
        from .postprocessing import MeshPostprocessor, PrintOptimizer
        
        warnings = []
        
        # Repair mesh
        if repair:
            postprocessor = MeshPostprocessor()
            mesh, repair_warnings = postprocessor.repair(mesh)
            warnings.extend(repair_warnings)
        
        # Optimize for printing
        optimizer = PrintOptimizer(
            build_volume=self.config.printer.build_volume
        )
        mesh = optimizer.process(
            mesh,
            target_height_mm=scale_mm,
            add_base=add_base,
            base_height_mm=base_height_mm,
            hollow=hollow,
            wall_thickness_mm=wall_thickness_mm
        )
        
        return mesh, warnings
    
    def _export(self, mesh, output_path: Path, format: str):
        """Export mesh to file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        if format == "stl":
            mesh.export(str(output_path), file_type="stl")
        elif format == "obj":
            mesh.export(str(output_path), file_type="obj")
        elif format == "glb":
            mesh.export(str(output_path), file_type="glb")
        else:
            raise ValueError(f"Unsupported format: {format}")
