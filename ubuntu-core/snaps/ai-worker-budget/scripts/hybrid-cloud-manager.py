#!/usr/bin/env python3
"""
Hybrid Cloud Manager for Budget-Conscious AI Training
Seamlessly switches between local RTX GPUs and cloud H100s
"""

import os
import json
import yaml
import time
import subprocess
from datetime import datetime
from dataclasses import dataclass
from typing import List, Dict, Optional
import requests

# Cloud provider clients
try:
    import runpod
    RUNPOD_AVAILABLE = True
except:
    RUNPOD_AVAILABLE = False

@dataclass
class TrainingJob:
    job_id: str
    model_name: str
    model_size_gb: float
    dataset_size_gb: float
    estimated_hours: float
    priority: str  # 'high', 'medium', 'low'
    checkpoint_path: str
    resume_from_checkpoint: bool = False

@dataclass
class ComputeResource:
    name: str
    type: str  # 'local' or 'cloud'
    gpu_model: str
    gpu_count: int
    vram_per_gpu_gb: int
    cost_per_hour: float
    available: bool

class HybridCloudManager:
    def __init__(self, config_path="hybrid-config.yaml"):
        self.config = self.load_config(config_path)
        self.local_resources = self.detect_local_gpus()
        self.cloud_providers = self.init_cloud_providers()
        self.cost_tracker = CostTracker()
        
    def load_config(self, config_path):
        """Load configuration from YAML file"""
        default_config = {
            'budget': {
                'monthly_limit': 1000,
                'alert_threshold': 0.8
            },
            'cloud_providers': {
                'runpod': {
                    'api_key': os.environ.get('RUNPOD_API_KEY', ''),
                    'preferred_gpu': 'H100_PCIE',
                    'use_spot': True
                },
                'lambda_labs': {
                    'api_key': os.environ.get('LAMBDA_API_KEY', ''),
                    'preferred_instance': 'gpu_1x_h100_pcie'
                },
                'vast_ai': {
                    'api_key': os.environ.get('VAST_API_KEY', ''),
                    'min_reliability': 0.95
                }
            },
            'optimization': {
                'quantization_enabled': True,
                'gradient_checkpointing': True,
                'mixed_precision': 'fp16'
            }
        }
        
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                user_config = yaml.safe_load(f)
                default_config.update(user_config)
                
        return default_config
    
    def detect_local_gpus(self):
        """Detect local NVIDIA GPUs"""
        resources = []
        
        try:
            # Get GPU info using nvidia-smi
            result = subprocess.run(
                ['nvidia-smi', '--query-gpu=name,memory.total', '--format=csv,noheader,nounits'],
                capture_output=True, text=True
            )
            
            if result.returncode == 0:
                for i, line in enumerate(result.stdout.strip().split('\n')):
                    name, memory = line.split(', ')
                    
                    # Estimate cost based on power consumption
                    power_draw = 450 if '4090' in name else 350  # Watts
                    electricity_cost = 0.12  # $/kWh
                    cost_per_hour = (power_draw / 1000) * electricity_cost
                    
                    resources.append(ComputeResource(
                        name=f"local_gpu_{i}",
                        type="local",
                        gpu_model=name.strip(),
                        gpu_count=1,
                        vram_per_gpu_gb=int(memory) // 1024,
                        cost_per_hour=cost_per_hour,
                        available=True
                    ))
                    
        except Exception as e:
            print(f"Error detecting local GPUs: {e}")
            
        # Aggregate local GPUs into cluster
        if resources:
            total_vram = sum(r.vram_per_gpu_gb for r in resources)
            total_cost = sum(r.cost_per_hour for r in resources)
            
            resources.append(ComputeResource(
                name="local_cluster",
                type="local",
                gpu_model="Mixed_RTX",
                gpu_count=len(resources),
                vram_per_gpu_gb=total_vram,
                cost_per_hour=total_cost,
                available=True
            ))
            
        return resources
    
    def init_cloud_providers(self):
        """Initialize cloud provider clients"""
        providers = {}
        
        # RunPod
        if RUNPOD_AVAILABLE and self.config['cloud_providers']['runpod']['api_key']:
            providers['runpod'] = RunPodProvider(self.config['cloud_providers']['runpod'])
            
        # Lambda Labs
        if self.config['cloud_providers']['lambda_labs']['api_key']:
            providers['lambda_labs'] = LambdaLabsProvider(self.config['cloud_providers']['lambda_labs'])
            
        # Vast.ai
        if self.config['cloud_providers']['vast_ai']['api_key']:
            providers['vast_ai'] = VastAIProvider(self.config['cloud_providers']['vast_ai'])
            
        return providers
    
    def estimate_requirements(self, job: TrainingJob):
        """Estimate compute requirements for a job"""
        # Base memory requirement
        model_memory = job.model_size_gb * 2  # Model + gradients
        
        # Add optimizer state
        if not self.config['optimization']['quantization_enabled']:
            model_memory *= 2  # Adam optimizer states
            
        # Add activation memory
        activation_memory = job.model_size_gb * 0.5
        
        # Total with safety margin
        total_memory = (model_memory + activation_memory) * 1.2
        
        # Estimate compute time multiplier based on hardware
        compute_multipliers = {
            'H100': 1.0,
            'A100': 1.5,
            'RTX 4090': 2.5,
            'RTX 3090': 3.5
        }
        
        return {
            'min_vram_gb': total_memory,
            'compute_multipliers': compute_multipliers,
            'supports_quantization': job.model_size_gb > 7  # Use quantization for models >7B
        }
    
    def select_compute_resource(self, job: TrainingJob):
        """Select optimal compute resource for job"""
        requirements = self.estimate_requirements(job)
        candidates = []
        
        # Check local resources first
        for resource in self.local_resources:
            if resource.available and resource.vram_per_gpu_gb >= requirements['min_vram_gb']:
                # Calculate effective cost including time
                gpu_type = resource.gpu_model.split()[0]
                time_multiplier = requirements['compute_multipliers'].get(gpu_type, 3.0)
                effective_cost = resource.cost_per_hour * job.estimated_hours * time_multiplier
                
                candidates.append({
                    'resource': resource,
                    'effective_cost': effective_cost,
                    'estimated_hours': job.estimated_hours * time_multiplier
                })
        
        # Check cloud resources if needed or if high priority
        if not candidates or job.priority == 'high':
            cloud_options = self.get_cloud_options(requirements['min_vram_gb'])
            
            for option in cloud_options:
                effective_cost = option['cost_per_hour'] * job.estimated_hours
                candidates.append({
                    'resource': option['resource'],
                    'effective_cost': effective_cost,
                    'estimated_hours': job.estimated_hours
                })
        
        # Sort by cost and select cheapest
        if candidates:
            candidates.sort(key=lambda x: x['effective_cost'])
            selected = candidates[0]
            
            # Check budget
            if self.cost_tracker.can_afford(selected['effective_cost']):
                return selected
            else:
                print(f"Warning: Job would exceed budget. Estimated cost: ${selected['effective_cost']:.2f}")
                return None
                
        return None
    
    def get_cloud_options(self, min_vram_gb):
        """Get available cloud GPU options"""
        options = []
        
        for provider_name, provider in self.cloud_providers.items():
            try:
                available_gpus = provider.get_available_gpus(min_vram_gb)
                options.extend(available_gpus)
            except Exception as e:
                print(f"Error querying {provider_name}: {e}")
                
        return options
    
    def prepare_job_for_cloud(self, job: TrainingJob):
        """Prepare job for cloud execution"""
        # Create job package
        job_package = {
            'job_id': job.job_id,
            'model_name': job.model_name,
            'checkpoint_path': job.checkpoint_path,
            'config': {
                'quantization': self.config['optimization']['quantization_enabled'],
                'gradient_checkpointing': self.config['optimization']['gradient_checkpointing'],
                'mixed_precision': self.config['optimization']['mixed_precision']
            }
        }
        
        # Upload checkpoint if resuming
        if job.resume_from_checkpoint and os.path.exists(job.checkpoint_path):
            # In production, upload to S3 or similar
            print(f"Uploading checkpoint from {job.checkpoint_path}")
            
        return job_package
    
    def execute_job(self, job: TrainingJob):
        """Execute training job on selected resource"""
        # Select resource
        selected = self.select_compute_resource(job)
        
        if not selected:
            raise ValueError("No suitable compute resource available")
            
        resource = selected['resource']
        print(f"Selected {resource.name} for job {job.job_id}")
        print(f"Estimated cost: ${selected['effective_cost']:.2f}")
        print(f"Estimated time: {selected['estimated_hours']:.1f} hours")
        
        # Execute based on resource type
        if resource.type == 'local':
            return self.execute_local(job, resource)
        else:
            job_package = self.prepare_job_for_cloud(job)
            return self.execute_cloud(job, resource, job_package)
    
    def execute_local(self, job: TrainingJob, resource: ComputeResource):
        """Execute job on local GPUs"""
        print(f"Starting local execution on {resource.gpu_count} GPUs")
        
        # Set up environment
        env = os.environ.copy()
        env['CUDA_VISIBLE_DEVICES'] = ','.join(str(i) for i in range(resource.gpu_count))
        
        # Build command
        cmd = [
            'python', '-m', 'torch.distributed.launch',
            '--nproc_per_node', str(resource.gpu_count),
            'train.py',
            '--model', job.model_name,
            '--checkpoint', job.checkpoint_path,
            '--mixed-precision', self.config['optimization']['mixed_precision']
        ]
        
        if self.config['optimization']['quantization_enabled']:
            cmd.extend(['--quantization', '4bit'])
            
        # Start training
        process = subprocess.Popen(cmd, env=env)
        
        # Monitor progress
        return self.monitor_local_job(job, process)
    
    def execute_cloud(self, job: TrainingJob, resource: ComputeResource, job_package):
        """Execute job on cloud GPU"""
        provider_name = resource.name.split('_')[0]  # Extract provider from resource name
        provider = self.cloud_providers.get(provider_name)
        
        if not provider:
            raise ValueError(f"Unknown cloud provider: {provider_name}")
            
        # Start cloud instance
        instance_id = provider.start_instance(resource, job_package)
        
        # Monitor progress
        return self.monitor_cloud_job(job, provider, instance_id)
    
    def monitor_local_job(self, job: TrainingJob, process):
        """Monitor local training job"""
        start_time = time.time()
        
        while process.poll() is None:
            # Check GPU utilization
            gpu_stats = self.get_gpu_stats()
            
            # Log progress
            elapsed = (time.time() - start_time) / 3600
            print(f"Job {job.job_id}: {elapsed:.1f} hours, GPU util: {gpu_stats['avg_utilization']:.1f}%")
            
            # Save periodic checkpoints
            if elapsed % 0.5 < 0.1:  # Every 30 minutes
                self.save_checkpoint(job)
                
            time.sleep(60)  # Check every minute
            
        return process.returncode == 0
    
    def monitor_cloud_job(self, job: TrainingJob, provider, instance_id):
        """Monitor cloud training job"""
        start_time = time.time()
        
        while True:
            status = provider.get_instance_status(instance_id)
            
            if status['state'] == 'completed':
                # Download results
                provider.download_results(instance_id, job.checkpoint_path)
                provider.terminate_instance(instance_id)
                return True
                
            elif status['state'] == 'failed':
                print(f"Cloud job failed: {status.get('error', 'Unknown error')}")
                provider.terminate_instance(instance_id)
                return False
                
            # Log progress
            elapsed = (time.time() - start_time) / 3600
            cost = elapsed * status['cost_per_hour']
            print(f"Job {job.job_id}: {elapsed:.1f} hours, Cost: ${cost:.2f}")
            
            time.sleep(60)
    
    def get_gpu_stats(self):
        """Get current GPU statistics"""
        try:
            result = subprocess.run(
                ['nvidia-smi', '--query-gpu=utilization.gpu', '--format=csv,noheader,nounits'],
                capture_output=True, text=True
            )
            
            if result.returncode == 0:
                utils = [float(u) for u in result.stdout.strip().split('\n')]
                return {
                    'avg_utilization': sum(utils) / len(utils),
                    'per_gpu': utils
                }
        except:
            pass
            
        return {'avg_utilization': 0, 'per_gpu': []}
    
    def save_checkpoint(self, job: TrainingJob):
        """Save training checkpoint"""
        checkpoint_dir = os.path.dirname(job.checkpoint_path)
        os.makedirs(checkpoint_dir, exist_ok=True)
        
        # In practice, this would trigger the training script to save
        print(f"Saving checkpoint to {job.checkpoint_path}")
        

class CostTracker:
    """Track and manage training costs"""
    
    def __init__(self, budget_file="training_costs.json"):
        self.budget_file = budget_file
        self.costs = self.load_costs()
        
    def load_costs(self):
        """Load cost history"""
        if os.path.exists(self.budget_file):
            with open(self.budget_file, 'r') as f:
                return json.load(f)
        return {
            'current_month': datetime.now().strftime('%Y-%m'),
            'monthly_costs': {},
            'total_spent': 0
        }
    
    def save_costs(self):
        """Save cost history"""
        with open(self.budget_file, 'w') as f:
            json.dump(self.costs, f, indent=2)
    
    def add_cost(self, amount, description):
        """Add a cost entry"""
        month = datetime.now().strftime('%Y-%m')
        
        if month != self.costs['current_month']:
            # New month, reset
            self.costs['current_month'] = month
            self.costs['monthly_costs'][month] = 0
            
        self.costs['monthly_costs'].setdefault(month, 0)
        self.costs['monthly_costs'][month] += amount
        self.costs['total_spent'] += amount
        
        # Log entry
        with open('cost_log.txt', 'a') as f:
            f.write(f"{datetime.now()}: ${amount:.2f} - {description}\n")
            
        self.save_costs()
    
    def can_afford(self, amount, monthly_limit=1000):
        """Check if we can afford a cost"""
        month = datetime.now().strftime('%Y-%m')
        current_spent = self.costs['monthly_costs'].get(month, 0)
        
        return (current_spent + amount) <= monthly_limit
    
    def get_monthly_summary(self):
        """Get current month's spending summary"""
        month = datetime.now().strftime('%Y-%m')
        spent = self.costs['monthly_costs'].get(month, 0)
        
        return {
            'month': month,
            'spent': spent,
            'remaining': 1000 - spent,
            'percentage': (spent / 1000) * 100
        }


# Cloud Provider Implementations

class RunPodProvider:
    """RunPod cloud provider implementation"""
    
    def __init__(self, config):
        self.config = config
        self.api_key = config['api_key']
        
    def get_available_gpus(self, min_vram_gb):
        """Get available GPU options from RunPod"""
        options = []
        
        # RunPod GPU types (prices as of 2024)
        gpu_types = {
            'H100_PCIE': {'vram': 80, 'cost': 2.99, 'spot_cost': 1.99},
            'A100_PCIE': {'vram': 80, 'cost': 1.89, 'spot_cost': 1.29},
            'RTX_4090': {'vram': 24, 'cost': 0.74, 'spot_cost': 0.54},
            'RTX_A6000': {'vram': 48, 'cost': 1.28, 'spot_cost': 0.89}
        }
        
        for gpu_name, specs in gpu_types.items():
            if specs['vram'] >= min_vram_gb:
                cost = specs['spot_cost'] if self.config['use_spot'] else specs['cost']
                
                options.append({
                    'resource': ComputeResource(
                        name=f"runpod_{gpu_name}",
                        type="cloud",
                        gpu_model=gpu_name,
                        gpu_count=1,
                        vram_per_gpu_gb=specs['vram'],
                        cost_per_hour=cost,
                        available=True
                    ),
                    'cost_per_hour': cost
                })
                
        return options
    
    def start_instance(self, resource, job_package):
        """Start a RunPod instance"""
        # In production, use RunPod API
        print(f"Starting RunPod instance with {resource.gpu_model}")
        return f"runpod_instance_{job_package['job_id']}"
    
    def get_instance_status(self, instance_id):
        """Get RunPod instance status"""
        # Simulate for demo
        return {
            'state': 'running',
            'cost_per_hour': 1.99
        }
    
    def download_results(self, instance_id, local_path):
        """Download results from RunPod"""
        print(f"Downloading results from {instance_id} to {local_path}")
        
    def terminate_instance(self, instance_id):
        """Terminate RunPod instance"""
        print(f"Terminating {instance_id}")


class LambdaLabsProvider:
    """Lambda Labs cloud provider implementation"""
    
    def __init__(self, config):
        self.config = config
        self.api_key = config['api_key']
        
    def get_available_gpus(self, min_vram_gb):
        """Get available GPU options from Lambda Labs"""
        # Implementation similar to RunPod
        return []


class VastAIProvider:
    """Vast.ai cloud provider implementation"""
    
    def __init__(self, config):
        self.config = config
        self.api_key = config['api_key']
        
    def get_available_gpus(self, min_vram_gb):
        """Get available GPU options from Vast.ai"""
        # Implementation would query Vast.ai API
        return []


def main():
    """Example usage"""
    manager = HybridCloudManager()
    
    # Example job
    job = TrainingJob(
        job_id="train_001",
        model_name="meta-llama/Llama-2-7b-hf",
        model_size_gb=7,
        dataset_size_gb=10,
        estimated_hours=2,
        priority="medium",
        checkpoint_path="/data/checkpoints/llama2-7b"
    )
    
    # Show available resources
    print("Local GPUs detected:")
    for resource in manager.local_resources:
        print(f"  {resource.name}: {resource.gpu_model} ({resource.vram_per_gpu_gb}GB) - ${resource.cost_per_hour:.2f}/hour")
    
    # Get cost summary
    cost_summary = manager.cost_tracker.get_monthly_summary()
    print(f"\nMonthly budget: ${cost_summary['spent']:.2f} / $1000 ({cost_summary['percentage']:.1f}%)")
    
    # Execute job
    print(f"\nExecuting job {job.job_id}...")
    success = manager.execute_job(job)
    
    if success:
        print("Job completed successfully!")
    else:
        print("Job failed!")


if __name__ == "__main__":
    main()