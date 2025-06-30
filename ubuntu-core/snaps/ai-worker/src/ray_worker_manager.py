#!/usr/bin/env python3
"""
Ray worker manager for AI worker nodes.
Manages Ray worker lifecycle, task execution, and resource allocation.
"""

import os
import ray
import asyncio
import json
import logging
import psutil
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
import aiohttp

logger = logging.getLogger(__name__)


@dataclass
class WorkerConfig:
    """Ray worker configuration"""
    node_id: str
    ray_head_address: str
    num_cpus: Optional[int] = None
    num_gpus: Optional[int] = None
    memory: Optional[int] = None  # In bytes
    object_store_memory: Optional[int] = None  # In bytes
    resources: Optional[Dict[str, float]] = None
    labels: Optional[Dict[str, str]] = None
    max_tasks: Optional[int] = None
    max_calls: Optional[int] = None
    

@dataclass
class TaskResult:
    """Result of a Ray task execution"""
    task_id: str
    status: str  # 'success', 'failed', 'timeout'
    result: Optional[Any] = None
    error: Optional[str] = None
    start_time: datetime = None
    end_time: datetime = None
    duration_seconds: float = 0.0
    

class RayWorkerManager:
    """Manages Ray worker operations and task execution"""
    
    def __init__(self, config: WorkerConfig):
        self.config = config
        self.connected = False
        self.worker_id = None
        self.management_url = os.getenv("MANAGEMENT_SERVER_URL", "http://localhost:8000")
        self.session: Optional[aiohttp.ClientSession] = None
        self.task_history: List[TaskResult] = []
        self.max_history = 100
        
    async def initialize(self):
        """Initialize Ray worker connection"""
        try:
            # Build Ray init arguments
            init_kwargs = {
                "address": self.config.ray_head_address,
                "ignore_reinit_error": True,
            }
            
            # Add resource constraints if specified
            if self.config.num_cpus is not None:
                init_kwargs["num_cpus"] = self.config.num_cpus
            if self.config.num_gpus is not None:
                init_kwargs["num_gpus"] = self.config.num_gpus
            if self.config.memory is not None:
                init_kwargs["_memory"] = self.config.memory
            if self.config.object_store_memory is not None:
                init_kwargs["object_store_memory"] = self.config.object_store_memory
                
            # Add custom resources
            if self.config.resources:
                init_kwargs["resources"] = self.config.resources
                
            # Add labels
            if self.config.labels:
                init_kwargs["labels"] = self.config.labels
                
            # Initialize Ray
            ray.init(**init_kwargs)
            
            self.connected = True
            self.worker_id = ray.get_runtime_context().get_worker_id()
            
            # Create aiohttp session
            self.session = aiohttp.ClientSession()
            
            logger.info(f"Ray worker initialized: {self.worker_id}")
            logger.info(f"Connected to Ray head: {self.config.ray_head_address}")
            
            # Report successful connection
            await self._report_status("connected")
            
        except Exception as e:
            logger.error(f"Failed to initialize Ray worker: {e}")
            await self._report_status("failed", error=str(e))
            raise
            
    async def shutdown(self):
        """Shutdown Ray worker gracefully"""
        try:
            if self.connected:
                # Report shutdown
                await self._report_status("shutting_down")
                
                # Shutdown Ray
                ray.shutdown()
                self.connected = False
                
            # Close aiohttp session
            if self.session:
                await self.session.close()
                
            logger.info("Ray worker shutdown complete")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
            
    async def _report_status(self, status: str, error: Optional[str] = None):
        """Report worker status to management server"""
        if not self.session:
            return
            
        try:
            data = {
                "node_id": self.config.node_id,
                "worker_id": self.worker_id,
                "status": status,
                "timestamp": datetime.utcnow().isoformat(),
                "resources": {
                    "cpus": self.config.num_cpus,
                    "gpus": self.config.num_gpus,
                    "memory": self.config.memory,
                },
                "labels": self.config.labels,
            }
            
            if error:
                data["error"] = error
                
            await self.session.post(
                f"{self.management_url}/api/v1/ray/worker/status",
                json=data,
                timeout=aiohttp.ClientTimeout(total=10)
            )
            
        except Exception as e:
            logger.error(f"Failed to report status: {e}")
            
    def get_available_resources(self) -> Dict[str, Any]:
        """Get available resources on this worker"""
        if not self.connected:
            return {}
            
        return ray.available_resources()
        
    def get_cluster_resources(self) -> Dict[str, Any]:
        """Get total cluster resources"""
        if not self.connected:
            return {}
            
        return ray.cluster_resources()
        
    async def execute_task(self, task_func: Callable, *args, **kwargs) -> TaskResult:
        """Execute a task on this worker"""
        task_id = f"{self.config.node_id}_{datetime.utcnow().timestamp()}"
        result = TaskResult(task_id=task_id, start_time=datetime.utcnow())
        
        try:
            # Convert function to Ray task if not already
            if not hasattr(task_func, "remote"):
                task_func = ray.remote(task_func)
                
            # Execute task
            future = task_func.remote(*args, **kwargs)
            
            # Wait for result with timeout
            timeout = kwargs.get("_timeout", 3600)  # Default 1 hour timeout
            task_result = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None, ray.get, future
                ),
                timeout=timeout
            )
            
            result.status = "success"
            result.result = task_result
            
        except asyncio.TimeoutError:
            result.status = "timeout"
            result.error = f"Task timed out after {timeout} seconds"
            
        except Exception as e:
            result.status = "failed"
            result.error = str(e)
            logger.error(f"Task execution failed: {e}")
            
        finally:
            result.end_time = datetime.utcnow()
            result.duration_seconds = (result.end_time - result.start_time).total_seconds()
            
            # Add to history
            self.task_history.append(result)
            if len(self.task_history) > self.max_history:
                self.task_history = self.task_history[-self.max_history:]
                
            # Report task completion
            await self._report_task_completion(result)
            
        return result
        
    async def _report_task_completion(self, result: TaskResult):
        """Report task completion to management server"""
        if not self.session:
            return
            
        try:
            data = {
                "node_id": self.config.node_id,
                "worker_id": self.worker_id,
                "task_id": result.task_id,
                "status": result.status,
                "duration_seconds": result.duration_seconds,
                "start_time": result.start_time.isoformat(),
                "end_time": result.end_time.isoformat(),
            }
            
            if result.error:
                data["error"] = result.error
                
            await self.session.post(
                f"{self.management_url}/api/v1/ray/task/complete",
                json=data,
                timeout=aiohttp.ClientTimeout(total=10)
            )
            
        except Exception as e:
            logger.error(f"Failed to report task completion: {e}")
            
    async def register_named_actor(self, actor_class, name: str, *args, **kwargs):
        """Register a named Ray actor"""
        if not self.connected:
            raise RuntimeError("Ray worker not connected")
            
        try:
            # Create actor
            actor = ray.remote(actor_class).options(name=name).remote(*args, **kwargs)
            
            logger.info(f"Registered named actor: {name}")
            
            # Report actor registration
            await self._report_actor_registration(name, "registered")
            
            return actor
            
        except Exception as e:
            logger.error(f"Failed to register actor {name}: {e}")
            await self._report_actor_registration(name, "failed", error=str(e))
            raise
            
    async def _report_actor_registration(self, name: str, status: str, error: Optional[str] = None):
        """Report actor registration to management server"""
        if not self.session:
            return
            
        try:
            data = {
                "node_id": self.config.node_id,
                "worker_id": self.worker_id,
                "actor_name": name,
                "status": status,
                "timestamp": datetime.utcnow().isoformat(),
            }
            
            if error:
                data["error"] = error
                
            await self.session.post(
                f"{self.management_url}/api/v1/ray/actor/register",
                json=data,
                timeout=aiohttp.ClientTimeout(total=10)
            )
            
        except Exception as e:
            logger.error(f"Failed to report actor registration: {e}")
            
    def get_worker_stats(self) -> Dict[str, Any]:
        """Get worker statistics"""
        stats = {
            "node_id": self.config.node_id,
            "worker_id": self.worker_id,
            "connected": self.connected,
            "ray_version": ray.__version__ if self.connected else None,
            "tasks_completed": len(self.task_history),
            "resources": {
                "configured": {
                    "cpus": self.config.num_cpus,
                    "gpus": self.config.num_gpus,
                    "memory": self.config.memory,
                },
                "available": self.get_available_resources() if self.connected else {},
            },
            "recent_tasks": [
                {
                    "task_id": t.task_id,
                    "status": t.status,
                    "duration": t.duration_seconds,
                    "timestamp": t.start_time.isoformat(),
                }
                for t in self.task_history[-10:]  # Last 10 tasks
            ],
            "system": {
                "cpu_percent": psutil.cpu_percent(interval=1),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_percent": psutil.disk_usage('/').percent,
            }
        }
        
        return stats


# Example Ray tasks and actors

@ray.remote
def example_cpu_task(n: int) -> int:
    """Example CPU-bound task"""
    import time
    import numpy as np
    
    # Simulate CPU work
    result = 0
    for i in range(n):
        result += np.sum(np.random.rand(1000, 1000))
        
    return result


@ray.remote(num_gpus=1)
def example_gpu_task(matrix_size: int = 1000) -> float:
    """Example GPU task using PyTorch"""
    try:
        import torch
        
        # Check if GPU is available
        if not torch.cuda.is_available():
            raise RuntimeError("GPU not available")
            
        # Create random matrices on GPU
        device = torch.device("cuda")
        a = torch.randn(matrix_size, matrix_size, device=device)
        b = torch.randn(matrix_size, matrix_size, device=device)
        
        # Perform matrix multiplication
        c = torch.matmul(a, b)
        
        # Return sum
        return float(c.sum().cpu())
        
    except ImportError:
        # Fallback to numpy if torch not available
        import numpy as np
        a = np.random.randn(matrix_size, matrix_size)
        b = np.random.randn(matrix_size, matrix_size)
        c = np.matmul(a, b)
        return float(c.sum())


@ray.remote
class ModelServingActor:
    """Example actor for model serving"""
    
    def __init__(self, model_name: str):
        self.model_name = model_name
        self.requests_served = 0
        logger.info(f"Model serving actor initialized: {model_name}")
        
    def predict(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Make prediction"""
        self.requests_served += 1
        
        # Simulate model prediction
        import time
        import random
        time.sleep(random.uniform(0.01, 0.1))  # Simulate inference time
        
        return {
            "model": self.model_name,
            "prediction": random.random(),
            "confidence": random.uniform(0.8, 0.99),
            "requests_served": self.requests_served,
        }
        
    def get_stats(self) -> Dict[str, Any]:
        """Get actor statistics"""
        return {
            "model_name": self.model_name,
            "requests_served": self.requests_served,
        }


async def main():
    """Test Ray worker manager"""
    logging.basicConfig(level=logging.INFO)
    
    # Create configuration
    config = WorkerConfig(
        node_id=os.getenv("NODE_ID", "test-node"),
        ray_head_address=os.getenv("RAY_HEAD_ADDRESS", "auto"),
        num_cpus=4,
        num_gpus=1 if os.path.exists("/dev/nvidia0") else 0,
        labels={"node_type": "ai-worker", "test": "true"}
    )
    
    # Create manager
    manager = RayWorkerManager(config)
    
    try:
        # Initialize
        await manager.initialize()
        
        # Print cluster resources
        print("Cluster resources:", manager.get_cluster_resources())
        print("Available resources:", manager.get_available_resources())
        
        # Execute example tasks
        print("\nExecuting CPU task...")
        cpu_result = await manager.execute_task(example_cpu_task, 10)
        print(f"CPU task result: {cpu_result.status}")
        
        if config.num_gpus > 0:
            print("\nExecuting GPU task...")
            gpu_result = await manager.execute_task(example_gpu_task, 500)
            print(f"GPU task result: {gpu_result.status}")
            
        # Register actor
        print("\nRegistering model serving actor...")
        await manager.register_named_actor(
            ModelServingActor, 
            "test-model-server",
            "test-model-v1"
        )
        
        # Get stats
        print("\nWorker stats:")
        print(json.dumps(manager.get_worker_stats(), indent=2))
        
    finally:
        await manager.shutdown()


if __name__ == "__main__":
    asyncio.run(main())