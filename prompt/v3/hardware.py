"""
Hardware detection utilities for GPU capability checking.
"""

from dataclasses import dataclass
from typing import Optional
import subprocess
import re


@dataclass
class GPUInfo:
    """Information about available GPU hardware."""
    available: bool
    name: Optional[str] = None
    vram_gb: float = 0.0
    compute_capability: float = 0.0
    cuda_available: bool = False
    cuda_version: Optional[str] = None
    driver_version: Optional[str] = None
    
    @property
    def supports_modern_pytorch(self) -> bool:
        """Check if GPU supports PyTorch 2.5+."""
        return self.compute_capability >= 7.5
    
    @property
    def supports_triposr(self) -> bool:
        """Check if GPU can run TripoSR."""
        return self.available and self.vram_gb >= 6
    
    @property
    def supports_hunyuan(self) -> bool:
        """Check if GPU can run Hunyuan3D."""
        return self.available and self.vram_gb >= 6
    
    @property
    def supports_hunyuan_texture(self) -> bool:
        """Check if GPU can run Hunyuan3D with texture generation."""
        return self.available and self.vram_gb >= 16
    
    @property
    def supports_trellis(self) -> bool:
        """Check if GPU can run TRELLIS.2."""
        return self.available and self.vram_gb >= 24


def detect_gpu() -> GPUInfo:
    """
    Detect available GPU and its capabilities.
    
    Returns:
        GPUInfo with hardware details
    """
    # Try PyTorch detection first (most accurate)
    try:
        return _detect_via_pytorch()
    except ImportError:
        pass
    
    # Fallback to nvidia-smi
    try:
        return _detect_via_nvidia_smi()
    except Exception:
        pass
    
    # No GPU detected
    return GPUInfo(available=False)


def _detect_via_pytorch() -> GPUInfo:
    """Detect GPU using PyTorch."""
    import torch
    
    if not torch.cuda.is_available():
        return GPUInfo(available=False, cuda_available=False)
    
    device_id = 0
    props = torch.cuda.get_device_properties(device_id)
    
    return GPUInfo(
        available=True,
        name=props.name,
        vram_gb=props.total_memory / (1024 ** 3),
        compute_capability=float(f"{props.major}.{props.minor}"),
        cuda_available=True,
        cuda_version=torch.version.cuda
    )


def _detect_via_nvidia_smi() -> GPUInfo:
    """Detect GPU using nvidia-smi command."""
    try:
        # Get GPU name and memory
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,compute_cap", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode != 0:
            return GPUInfo(available=False)
        
        line = result.stdout.strip().split("\n")[0]
        parts = [p.strip() for p in line.split(",")]
        
        name = parts[0]
        vram_mb = float(parts[1])
        compute_cap = parts[2]
        
        # Get driver version
        driver_result = subprocess.run(
            ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=10
        )
        driver_version = driver_result.stdout.strip().split("\n")[0] if driver_result.returncode == 0 else None
        
        return GPUInfo(
            available=True,
            name=name,
            vram_gb=vram_mb / 1024,
            compute_capability=float(compute_cap),
            cuda_available=True,
            driver_version=driver_version
        )
        
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return GPUInfo(available=False)


def check_pytorch_cuda_compatibility(gpu_info: GPUInfo) -> dict:
    """
    Check if current PyTorch installation supports the detected GPU.
    
    Returns:
        Dict with compatibility info and recommendations
    """
    result = {
        "compatible": False,
        "warnings": [],
        "recommendations": []
    }
    
    if not gpu_info.available:
        result["warnings"].append("No GPU detected")
        result["recommendations"].append("Use --backend api for cloud processing")
        return result
    
    try:
        import torch
        
        # Check CUDA availability
        if not torch.cuda.is_available():
            result["warnings"].append("PyTorch CUDA not available")
            result["recommendations"].append("Install PyTorch with CUDA support")
            return result
        
        # Test actual tensor operation
        try:
            test_tensor = torch.zeros(1, device="cuda")
            del test_tensor
            result["compatible"] = True
        except RuntimeError as e:
            error_msg = str(e)
            
            if "no kernel image" in error_msg.lower():
                result["warnings"].append(
                    f"GPU compute capability {gpu_info.compute_capability} not supported by current PyTorch"
                )
                result["recommendations"].append(
                    "Install PyTorch 2.1 with CUDA 11.8: "
                    "pip install torch==2.1.2 --index-url https://download.pytorch.org/whl/cu118"
                )
            else:
                result["warnings"].append(f"CUDA error: {error_msg}")
            
            return result
        
        # Check compute capability
        if gpu_info.compute_capability < 7.5:
            result["warnings"].append(
                f"GPU compute capability {gpu_info.compute_capability} is below recommended 7.5"
            )
            result["recommendations"].append(
                "Some models may not work. Consider using --backend api"
            )
        
        return result
        
    except ImportError:
        result["warnings"].append("PyTorch not installed")
        result["recommendations"].append("Install PyTorch: pip install torch")
        return result


def get_recommended_model(gpu_info: GPUInfo) -> str:
    """
    Get recommended local model based on GPU capabilities.
    
    Args:
        gpu_info: Detected GPU information
        
    Returns:
        Recommended model name or None if API recommended
    """
    if not gpu_info.available:
        return None
    
    if not gpu_info.supports_modern_pytorch:
        return None  # Recommend API
    
    if gpu_info.supports_trellis:
        return "trellis"
    elif gpu_info.supports_hunyuan_texture:
        return "hunyuan"
    elif gpu_info.supports_triposr:
        return "triposr"
    else:
        return None


def print_hardware_summary(gpu_info: GPUInfo):
    """Print a human-readable hardware summary."""
    print("=" * 60)
    print("HARDWARE DETECTION SUMMARY")
    print("=" * 60)
    
    if not gpu_info.available:
        print("GPU: Not detected")
        print("Recommendation: Use --backend api")
        print("=" * 60)
        return
    
    print(f"GPU: {gpu_info.name}")
    print(f"VRAM: {gpu_info.vram_gb:.1f} GB")
    print(f"Compute Capability: {gpu_info.compute_capability}")
    print(f"CUDA Available: {gpu_info.cuda_available}")
    
    if gpu_info.cuda_version:
        print(f"CUDA Version: {gpu_info.cuda_version}")
    if gpu_info.driver_version:
        print(f"Driver Version: {gpu_info.driver_version}")
    
    print("-" * 60)
    print("Model Support:")
    print(f"  TripoSR:         {'✓' if gpu_info.supports_triposr else '✗'}")
    print(f"  Hunyuan3D:       {'✓' if gpu_info.supports_hunyuan else '✗'}")
    print(f"  Hunyuan+Texture: {'✓' if gpu_info.supports_hunyuan_texture else '✗'}")
    print(f"  TRELLIS.2:       {'✓' if gpu_info.supports_trellis else '✗'}")
    print("-" * 60)
    
    recommended = get_recommended_model(gpu_info)
    if recommended:
        print(f"Recommended: --backend local --model {recommended}")
    else:
        print("Recommended: --backend api")
    
    if not gpu_info.supports_modern_pytorch:
        print("")
        print("⚠️  WARNING: GPU compute capability < 7.5")
        print("   Modern PyTorch may not support this GPU.")
        print("   Try: pip install torch==2.1.2 --index-url https://download.pytorch.org/whl/cu118")
    
    print("=" * 60)
