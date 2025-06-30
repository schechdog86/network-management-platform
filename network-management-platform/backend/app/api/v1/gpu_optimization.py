"""
GPU optimization API endpoints.
"""

from fastapi import APIRouter, HTTPException, Depends, Body
from typing import Dict, Any, Optional
from app.services.gpu_optimizer import (
    gpu_optimizer, 
    GPUOptimizationProfile, 
    GPUSettings
)
from app.api.deps import get_current_user
from app.models.user import User
from app.core.logging_config import logger

router = APIRouter(prefix="/gpu", tags=["gpu-optimization"])


@router.get("/settings")
async def get_gpu_settings(
    current_user: User = Depends(get_current_user)
):
    """
    Get current GPU optimization settings.
    """
    return {
        "settings": gpu_optimizer.current_settings.to_dict(),
        "profiles": [profile.value for profile in GPUOptimizationProfile],
        "current_profile": gpu_optimizer.current_settings.profile.value
    }


@router.post("/profile/{profile}")
async def apply_gpu_profile(
    profile: GPUOptimizationProfile,
    current_user: User = Depends(get_current_user)
):
    """
    Apply a GPU optimization profile.
    
    Profiles:
    - conservative: 50-60% GPU utilization, stable but slower
    - balanced: 70-80% GPU utilization, good performance/stability balance
    - aggressive: 85-95% GPU utilization, faster but may be less stable
    - maximum: 95-100% GPU utilization, maximum performance
    """
    try:
        settings = gpu_optimizer.apply_profile(profile)
        return {
            "status": "success",
            "message": f"Applied {profile.value} GPU optimization profile",
            "settings": settings.to_dict()
        }
    except Exception as e:
        logger.error(f"Error applying GPU profile: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/settings")
async def update_gpu_settings(
    settings: Dict[str, Any] = Body(...),
    current_user: User = Depends(get_current_user)
):
    """
    Update individual GPU optimization settings.
    
    Available settings:
    - batch_size_multiplier: Multiplier for batch sizes (0.5-3.0)
    - memory_fraction: Fraction of GPU memory to use (0.5-0.95)
    - mixed_precision: Enable mixed precision training/inference
    - xla_jit: Enable XLA JIT compilation
    - cudnn_benchmark: Enable CuDNN auto-tuner
    - tensorrt_optimization: Enable TensorRT optimization
    - gradient_accumulation_steps: Number of gradient accumulation steps
    - gradient_checkpointing: Enable gradient checkpointing
    """
    try:
        # Validate settings
        valid_settings = {
            "batch_size_multiplier": (float, 0.5, 3.0),
            "memory_fraction": (float, 0.5, 0.95),
            "mixed_precision": (bool, None, None),
            "xla_jit": (bool, None, None),
            "cudnn_benchmark": (bool, None, None),
            "tensorrt_optimization": (bool, None, None),
            "dynamic_batching": (bool, None, None),
            "gradient_accumulation_steps": (int, 1, 16),
            "gradient_checkpointing": (bool, None, None),
            "power_limit": (int, 100, 500),
            "gpu_clock": (int, 300, 2500),
            "memory_clock": (int, 500, 10000),
        }
        
        validated_settings = {}
        for key, value in settings.items():
            if key in valid_settings:
                expected_type, min_val, max_val = valid_settings[key]
                
                # Type check
                if not isinstance(value, expected_type):
                    raise ValueError(f"{key} must be of type {expected_type.__name__}")
                    
                # Range check for numeric values
                if min_val is not None and value < min_val:
                    raise ValueError(f"{key} must be >= {min_val}")
                if max_val is not None and value > max_val:
                    raise ValueError(f"{key} must be <= {max_val}")
                    
                validated_settings[key] = value
                
        updated_settings = gpu_optimizer.update_settings(**validated_settings)
        
        return {
            "status": "success",
            "message": "GPU settings updated",
            "settings": updated_settings.to_dict()
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating GPU settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recommendations/{workload_type}")
async def get_optimization_recommendations(
    workload_type: str,
    current_user: User = Depends(get_current_user)
):
    """
    Get GPU optimization recommendations for a specific workload type.
    
    Workload types:
    - inference: For model inference/serving
    - training: For model training
    """
    if workload_type not in ["inference", "training"]:
        raise HTTPException(
            status_code=400, 
            detail="Workload type must be 'inference' or 'training'"
        )
        
    recommendations = gpu_optimizer.get_optimization_recommendations(workload_type)
    return recommendations


@router.post("/estimate-batch-size")
async def estimate_batch_size(
    model_size_mb: float = Body(..., description="Model size in MB"),
    available_memory_mb: Optional[float] = Body(None, description="Available GPU memory in MB"),
    current_user: User = Depends(get_current_user)
):
    """
    Estimate optimal batch size based on model size and available memory.
    """
    try:
        # If available memory not provided, try to get it from GPU
        if available_memory_mb is None:
            # This would query actual GPU memory
            # For now, use a default based on common GPUs
            available_memory_mb = 8192  # 8GB default
            
        batch_size = gpu_optimizer.estimate_batch_size(
            model_size_mb, 
            available_memory_mb
        )
        
        return {
            "model_size_mb": model_size_mb,
            "available_memory_mb": available_memory_mb,
            "memory_fraction": gpu_optimizer.current_settings.memory_fraction,
            "batch_size_multiplier": gpu_optimizer.current_settings.batch_size_multiplier,
            "estimated_batch_size": batch_size,
            "notes": [
                f"Using {gpu_optimizer.current_settings.memory_fraction*100:.0f}% of available memory",
                f"Batch size multiplier: {gpu_optimizer.current_settings.batch_size_multiplier}x",
                "Actual optimal batch size may vary based on model architecture"
            ]
        }
        
    except Exception as e:
        logger.error(f"Error estimating batch size: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/framework-config/{framework}")
async def get_framework_config(
    framework: str,
    current_user: User = Depends(get_current_user)
):
    """
    Get framework-specific optimization configuration.
    
    Frameworks:
    - pytorch: PyTorch optimization settings
    - tensorflow: TensorFlow optimization settings
    """
    if framework == "pytorch":
        config = gpu_optimizer.get_pytorch_optimization_config()
    elif framework == "tensorflow":
        config = gpu_optimizer.get_tensorflow_optimization_config()
    else:
        raise HTTPException(
            status_code=400,
            detail="Framework must be 'pytorch' or 'tensorflow'"
        )
        
    return {
        "framework": framework,
        "configuration": config,
        "code_example": _get_framework_example(framework, config)
    }


@router.post("/reset")
async def reset_gpu_settings(
    current_user: User = Depends(get_current_user)
):
    """
    Reset GPU settings to defaults.
    Requires admin privileges.
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Admin privileges required")
        
    gpu_optimizer.reset_to_defaults()
    
    return {
        "status": "success",
        "message": "GPU settings reset to defaults",
        "settings": gpu_optimizer.current_settings.to_dict()
    }


def _get_framework_example(framework: str, config: Dict[str, Any]) -> str:
    """Get code example for framework configuration"""
    if framework == "pytorch":
        return f"""
import torch

# Enable optimization settings
torch.backends.cudnn.benchmark = {config.get('torch.backends.cudnn.benchmark', True)}
torch.backends.cuda.matmul.allow_tf32 = {config.get('torch.backends.cuda.matmul.allow_tf32', True)}
torch.backends.cudnn.allow_tf32 = {config.get('torch.backends.cudnn.allow_tf32', True)}

# Mixed precision training
if {config.get('amp_enabled', False)}:
    from torch.cuda.amp import autocast, GradScaler
    scaler = GradScaler()
    
    # In training loop:
    with autocast():
        output = model(input)
        loss = criterion(output, target)
"""
    else:
        return f"""
import tensorflow as tf

# Set mixed precision policy
tf.keras.mixed_precision.set_global_policy('{config.get('mixed_precision_policy', 'float32')}')

# Configure GPU memory growth
gpus = tf.config.experimental.list_physical_devices('GPU')
if gpus:
    for gpu in gpus:
        tf.config.experimental.set_memory_growth(gpu, {config.get('memory_growth', True)})
        
# Enable XLA JIT compilation
if {config.get('xla_jit_compilation', True)}:
    tf.config.optimizer.set_jit('autoclustering')
"""