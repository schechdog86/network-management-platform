"""
GPU optimization service for maximizing GPU utilization during AI workloads.
"""

import os
import subprocess
import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class GPUOptimizationProfile(str, Enum):
    """GPU optimization profiles"""
    CONSERVATIVE = "conservative"  # 50-60% utilization
    BALANCED = "balanced"  # 70-80% utilization
    AGGRESSIVE = "aggressive"  # 85-95% utilization
    MAXIMUM = "maximum"  # 95-100% utilization


@dataclass
class GPUSettings:
    """GPU optimization settings"""
    profile: GPUOptimizationProfile = GPUOptimizationProfile.BALANCED
    
    # Batch size multipliers
    batch_size_multiplier: float = 1.0
    
    # Memory settings
    memory_growth: bool = True
    memory_fraction: float = 0.8  # Fraction of GPU memory to use
    
    # Compute settings
    mixed_precision: bool = True  # Use FP16/BF16 for faster computation
    xla_jit: bool = True  # XLA JIT compilation
    cudnn_benchmark: bool = True  # CuDNN auto-tuner
    
    # Multi-GPU settings
    multi_gpu_strategy: str = "mirrored"  # or "multi_worker_mirrored"
    
    # Threading settings
    num_threads: Optional[int] = None  # OMP_NUM_THREADS
    inter_op_threads: Optional[int] = None
    intra_op_threads: Optional[int] = None
    
    # Power settings
    power_limit: Optional[int] = None  # Watts
    gpu_clock: Optional[int] = None  # MHz
    memory_clock: Optional[int] = None  # MHz
    
    # Inference optimization
    tensorrt_optimization: bool = False
    dynamic_batching: bool = True
    
    # Training optimization
    gradient_accumulation_steps: int = 1
    gradient_checkpointing: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "profile": self.profile.value,
            "batch_size_multiplier": self.batch_size_multiplier,
            "memory_growth": self.memory_growth,
            "memory_fraction": self.memory_fraction,
            "mixed_precision": self.mixed_precision,
            "xla_jit": self.xla_jit,
            "cudnn_benchmark": self.cudnn_benchmark,
            "multi_gpu_strategy": self.multi_gpu_strategy,
            "num_threads": self.num_threads,
            "inter_op_threads": self.inter_op_threads,
            "intra_op_threads": self.intra_op_threads,
            "power_limit": self.power_limit,
            "gpu_clock": self.gpu_clock,
            "memory_clock": self.memory_clock,
            "tensorrt_optimization": self.tensorrt_optimization,
            "dynamic_batching": self.dynamic_batching,
            "gradient_accumulation_steps": self.gradient_accumulation_steps,
            "gradient_checkpointing": self.gradient_checkpointing,
        }


class GPUOptimizer:
    """GPU optimization service"""
    
    # Profile presets
    PROFILE_PRESETS = {
        GPUOptimizationProfile.CONSERVATIVE: {
            "batch_size_multiplier": 0.8,
            "memory_fraction": 0.6,
            "mixed_precision": False,
            "xla_jit": False,
            "cudnn_benchmark": False,
            "gradient_accumulation_steps": 1,
        },
        GPUOptimizationProfile.BALANCED: {
            "batch_size_multiplier": 1.0,
            "memory_fraction": 0.8,
            "mixed_precision": True,
            "xla_jit": True,
            "cudnn_benchmark": True,
            "gradient_accumulation_steps": 2,
        },
        GPUOptimizationProfile.AGGRESSIVE: {
            "batch_size_multiplier": 1.5,
            "memory_fraction": 0.9,
            "mixed_precision": True,
            "xla_jit": True,
            "cudnn_benchmark": True,
            "gradient_accumulation_steps": 4,
            "gradient_checkpointing": True,
        },
        GPUOptimizationProfile.MAXIMUM: {
            "batch_size_multiplier": 2.0,
            "memory_fraction": 0.95,
            "mixed_precision": True,
            "xla_jit": True,
            "cudnn_benchmark": True,
            "tensorrt_optimization": True,
            "dynamic_batching": True,
            "gradient_accumulation_steps": 8,
            "gradient_checkpointing": True,
        }
    }
    
    def __init__(self):
        self.current_settings = GPUSettings()
        self._original_env = {}
        
    def apply_profile(self, profile: GPUOptimizationProfile) -> GPUSettings:
        """Apply an optimization profile"""
        preset = self.PROFILE_PRESETS.get(profile, {})
        
        # Update settings from preset
        for key, value in preset.items():
            if hasattr(self.current_settings, key):
                setattr(self.current_settings, key, value)
                
        self.current_settings.profile = profile
        
        # Apply the settings
        self._apply_settings()
        
        return self.current_settings
        
    def update_settings(self, **kwargs) -> GPUSettings:
        """Update individual settings"""
        for key, value in kwargs.items():
            if hasattr(self.current_settings, key):
                setattr(self.current_settings, key, value)
                
        # Apply the settings
        self._apply_settings()
        
        return self.current_settings
        
    def _apply_settings(self):
        """Apply GPU optimization settings"""
        # Set environment variables
        self._set_environment_variables()
        
        # Apply NVIDIA settings if available
        self._apply_nvidia_settings()
        
        logger.info(f"Applied GPU settings: {self.current_settings.profile.value}")
        
    def _set_environment_variables(self):
        """Set environment variables for GPU optimization"""
        env_vars = {}
        
        # CUDA settings
        if self.current_settings.cudnn_benchmark:
            env_vars["TF_CUDNN_USE_AUTOTUNE"] = "1"
            env_vars["PYTORCH_CUDNN_BENCHMARK"] = "1"
            
        # XLA settings
        if self.current_settings.xla_jit:
            env_vars["TF_XLA_FLAGS"] = "--tf_xla_auto_jit=2"
            
        # Memory growth
        if self.current_settings.memory_growth:
            env_vars["TF_FORCE_GPU_ALLOW_GROWTH"] = "true"
            
        # Threading
        if self.current_settings.num_threads:
            env_vars["OMP_NUM_THREADS"] = str(self.current_settings.num_threads)
            
        # Mixed precision
        if self.current_settings.mixed_precision:
            env_vars["TF_ENABLE_AUTO_MIXED_PRECISION"] = "1"
            
        # Apply environment variables
        for key, value in env_vars.items():
            if key not in self._original_env:
                self._original_env[key] = os.environ.get(key)
            os.environ[key] = value
            
    def _apply_nvidia_settings(self):
        """Apply NVIDIA GPU settings using nvidia-smi"""
        try:
            # Check if nvidia-smi is available
            result = subprocess.run(["which", "nvidia-smi"], capture_output=True)
            if result.returncode != 0:
                return
                
            # Apply power limit
            if self.current_settings.power_limit:
                subprocess.run([
                    "nvidia-smi", 
                    "-pl", 
                    str(self.current_settings.power_limit)
                ], check=True)
                
            # Apply GPU clocks
            if self.current_settings.gpu_clock and self.current_settings.memory_clock:
                subprocess.run([
                    "nvidia-smi",
                    "-ac",
                    f"{self.current_settings.memory_clock},{self.current_settings.gpu_clock}"
                ], check=True)
                
        except subprocess.CalledProcessError as e:
            logger.error(f"Error applying NVIDIA settings: {e}")
            
    def get_optimization_recommendations(self, workload_type: str = "inference") -> Dict[str, Any]:
        """Get optimization recommendations based on workload type"""
        recommendations = {
            "workload_type": workload_type,
            "current_profile": self.current_settings.profile.value,
            "recommendations": []
        }
        
        if workload_type == "inference":
            recommendations["recommendations"] = [
                {
                    "setting": "batch_size_multiplier",
                    "current": self.current_settings.batch_size_multiplier,
                    "recommended": 1.5,
                    "reason": "Increase batch size for better GPU utilization during inference"
                },
                {
                    "setting": "tensorrt_optimization",
                    "current": self.current_settings.tensorrt_optimization,
                    "recommended": True,
                    "reason": "TensorRT can significantly speed up inference"
                },
                {
                    "setting": "dynamic_batching",
                    "current": self.current_settings.dynamic_batching,
                    "recommended": True,
                    "reason": "Dynamic batching improves throughput for variable-size inputs"
                }
            ]
        elif workload_type == "training":
            recommendations["recommendations"] = [
                {
                    "setting": "gradient_accumulation_steps",
                    "current": self.current_settings.gradient_accumulation_steps,
                    "recommended": 4,
                    "reason": "Gradient accumulation allows larger effective batch sizes"
                },
                {
                    "setting": "mixed_precision",
                    "current": self.current_settings.mixed_precision,
                    "recommended": True,
                    "reason": "Mixed precision training is faster with minimal accuracy loss"
                },
                {
                    "setting": "gradient_checkpointing",
                    "current": self.current_settings.gradient_checkpointing,
                    "recommended": True,
                    "reason": "Gradient checkpointing trades compute for memory"
                }
            ]
            
        return recommendations
        
    def estimate_batch_size(self, model_size_mb: float, 
                          available_memory_mb: float) -> int:
        """Estimate optimal batch size based on model and memory"""
        # Rule of thumb: each sample uses ~2x model size in memory during training
        memory_per_sample = model_size_mb * 2
        
        # Reserve some memory for gradients and optimizer states
        usable_memory = available_memory_mb * self.current_settings.memory_fraction * 0.7
        
        # Calculate base batch size
        base_batch_size = int(usable_memory / memory_per_sample)
        
        # Apply multiplier
        optimal_batch_size = int(base_batch_size * self.current_settings.batch_size_multiplier)
        
        # Ensure it's at least 1
        return max(1, optimal_batch_size)
        
    def get_pytorch_optimization_config(self) -> Dict[str, Any]:
        """Get PyTorch-specific optimization configuration"""
        config = {
            "torch.backends.cudnn.benchmark": self.current_settings.cudnn_benchmark,
            "torch.backends.cuda.matmul.allow_tf32": True,
            "torch.backends.cudnn.allow_tf32": True,
        }
        
        if self.current_settings.mixed_precision:
            config["amp_enabled"] = True
            config["amp_opt_level"] = "O2"  # Mixed precision
            
        return config
        
    def get_tensorflow_optimization_config(self) -> Dict[str, Any]:
        """Get TensorFlow-specific optimization configuration"""
        config = {
            "mixed_precision_policy": "mixed_float16" if self.current_settings.mixed_precision else "float32",
            "xla_jit_compilation": self.current_settings.xla_jit,
            "memory_growth": self.current_settings.memory_growth,
            "gpu_memory_fraction": self.current_settings.memory_fraction,
        }
        
        if self.current_settings.tensorrt_optimization:
            config["tensorrt_enabled"] = True
            config["tensorrt_precision_mode"] = "FP16"
            
        return config
        
    def reset_to_defaults(self):
        """Reset all settings to defaults"""
        self.current_settings = GPUSettings()
        
        # Restore original environment variables
        for key, value in self._original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
                
        self._original_env.clear()
        
        logger.info("Reset GPU settings to defaults")


# Global optimizer instance
gpu_optimizer = GPUOptimizer()