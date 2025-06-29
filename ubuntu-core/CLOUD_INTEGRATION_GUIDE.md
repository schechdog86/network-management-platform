# Cloud Integration Guide for Hybrid AI Training

## Overview

This guide shows how to seamlessly integrate cloud GPU rentals (H100s) with your local hardware for cost-effective AI training. The hybrid approach lets you use local GPUs for development and smaller models while bursting to cloud for large-scale training.

---

## 1. Cloud Provider Setup

### Recommended Providers for H100 Access

#### RunPod (Best for Flexibility)
```bash
# Create account at https://runpod.io
# Get API key from dashboard

# Install RunPod CLI
pip install runpodctl

# Configure
export RUNPOD_API_KEY="your-api-key"

# Test connection
runpodctl get pods
```

**Pricing (2024)**:
- H100 On-Demand: $2.99/hour
- H100 Spot: $1.99/hour (can be interrupted)
- Persistent storage: $0.10/GB/month

#### Lambda Labs (Best for Reliability)
```bash
# Create account at https://lambdalabs.com
# Get API key from dashboard

# Install Lambda Cloud CLI
pip install lambda-cloud

# Configure
export LAMBDA_API_KEY="your-api-key"

# List available instances
lambda-cloud instance-types list
```

**Pricing (2024)**:
- H100 80GB: $2.49/hour
- 8x H100 node: $19.92/hour
- Reserved pricing: ~$1.80/hour (commitment required)

#### Vast.ai (Budget Option)
```bash
# Create account at https://vast.ai
# More variable pricing/availability

# Install CLI
pip install vastai

# Configure
vastai set api-key your-api-key

# Search for H100s
vastai search offers "gpu_name=H100 verified=true"
```

**Pricing (2024)**:
- H100: $2.00-2.50/hour (varies by provider)
- Often 20-30% cheaper but less reliable

---

## 2. Hybrid Architecture Setup

### Local + Cloud Configuration

```yaml
# hybrid-config.yaml
compute_resources:
  local:
    gpus:
      - name: "rtx4090_0"
        vram: 24
        compute_capability: 8.9
      - name: "rtx4090_1"
        vram: 24
        compute_capability: 8.9
    total_vram: 48
    cost_per_hour: 0.20  # Electricity cost
    
  cloud:
    providers:
      runpod:
        enabled: true
        api_key: "${RUNPOD_API_KEY}"
        preferred_gpu: "H100_PCIE"
        use_spot: true
        max_spot_price: 2.50
        
      lambda_labs:
        enabled: true
        api_key: "${LAMBDA_API_KEY}"
        preferred_instance: "gpu_1x_h100_pcie"
        
    burst_threshold:
      model_size_gb: 13  # Use cloud for models >13GB
      vram_needed_gb: 40  # Use cloud if need >40GB VRAM
      
storage:
  checkpoint_sync:
    provider: "s3"  # or "gcs", "azure"
    bucket: "my-ai-checkpoints"
    auto_sync: true
    sync_interval_minutes: 30
```

### Automated Decision Logic

```python
# decision_engine.py
class HybridDecisionEngine:
    def __init__(self, config):
        self.config = config
        self.cost_optimizer = CostOptimizer()
        
    def should_use_cloud(self, job):
        """Decide whether to use local or cloud resources"""
        
        # Always use local for these cases
        if job.type in ['development', 'testing', 'small_inference']:
            return False
            
        # Check if model fits locally
        if job.model_size_gb <= 7:  # 7B models fit on single RTX 4090
            return False
            
        if job.model_size_gb <= 13:  # 13B models fit on 2x RTX 4090
            # Use local unless time-critical
            return job.priority == 'critical'
            
        # Large models require cloud
        if job.model_size_gb >= 30:
            return True
            
        # Cost-based decision for medium models
        local_cost = self.estimate_local_cost(job)
        cloud_cost = self.estimate_cloud_cost(job)
        
        return cloud_cost < local_cost * 1.5  # Cloud if not much more expensive
```

---

## 3. Data Synchronization

### Checkpoint Management

```python
# checkpoint_sync.py
import boto3
import os
import hashlib
from datetime import datetime

class CheckpointManager:
    def __init__(self, bucket_name):
        self.s3 = boto3.client('s3')
        self.bucket = bucket_name
        self.local_cache = "/data/checkpoints"
        
    def sync_to_cloud(self, local_path, job_id):
        """Upload checkpoint to S3 for cloud training"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        s3_key = f"checkpoints/{job_id}/{timestamp}/checkpoint.pt"
        
        # Calculate checksum
        checksum = self.calculate_checksum(local_path)
        
        # Upload with metadata
        self.s3.upload_file(
            local_path, 
            self.bucket, 
            s3_key,
            ExtraArgs={
                'Metadata': {
                    'checksum': checksum,
                    'job_id': job_id,
                    'timestamp': timestamp
                }
            }
        )
        
        return f"s3://{self.bucket}/{s3_key}"
        
    def sync_from_cloud(self, s3_path, local_path):
        """Download checkpoint from cloud after training"""
        # Parse S3 path
        bucket, key = self.parse_s3_path(s3_path)
        
        # Download
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        self.s3.download_file(bucket, key, local_path)
        
        return local_path
```

### Efficient Data Pipeline

```yaml
# data_pipeline.yaml
datasets:
  small:  # <10GB - Keep local
    storage: "local"
    path: "/data/datasets/small"
    
  medium:  # 10-100GB - Cache locally, backup S3
    storage: "hybrid"
    local_cache: "/data/datasets/cache"
    s3_backup: "s3://my-datasets/medium"
    cache_policy: "lru"
    max_cache_size: "100GB"
    
  large:  # >100GB - Stream from S3
    storage: "s3"
    path: "s3://my-datasets/large"
    streaming: true
    prefetch_size: "1GB"
```

---

## 4. Cloud Burst Automation

### Automatic Cloud Scaling

```python
# auto_burst.py
class CloudBurstManager:
    def __init__(self):
        self.providers = {
            'runpod': RunPodClient(),
            'lambda': LambdaLabsClient(),
            'vast': VastAIClient()
        }
        self.active_instances = {}
        
    def burst_to_cloud(self, job, reason="capacity"):
        """Automatically burst to cloud when needed"""
        
        print(f"Bursting to cloud: {reason}")
        
        # Find cheapest available option
        best_option = self.find_best_cloud_option(job)
        
        if not best_option:
            raise Exception("No cloud capacity available")
            
        # Prepare job for cloud
        cloud_job = self.prepare_cloud_job(job)
        
        # Launch instance
        instance = self.launch_instance(best_option, cloud_job)
        
        # Track for monitoring
        self.active_instances[job.id] = instance
        
        return instance
        
    def prepare_cloud_job(self, job):
        """Package job for cloud execution"""
        
        # Create job script
        job_script = f"""
#!/bin/bash
# Auto-generated training script

# Download checkpoint if resuming
if [ -n "$CHECKPOINT_S3_PATH" ]; then
    aws s3 cp $CHECKPOINT_S3_PATH /tmp/checkpoint.pt
fi

# Run training with optimizations
python train.py \\
    --model {job.model_name} \\
    --dataset $DATASET_S3_PATH \\
    --batch-size {job.batch_size} \\
    --mixed-precision fp16 \\
    --gradient-checkpointing \\
    --output-dir /tmp/output

# Upload results
aws s3 sync /tmp/output $OUTPUT_S3_PATH
"""
        
        return {
            'script': job_script,
            'docker_image': 'your-dockerhub/ai-trainer:latest',
            'env_vars': {
                'CHECKPOINT_S3_PATH': job.checkpoint_s3_path,
                'DATASET_S3_PATH': job.dataset_s3_path,
                'OUTPUT_S3_PATH': job.output_s3_path
            }
        }
```

### Spot Instance Management

```python
# spot_manager.py
class SpotInstanceManager:
    def __init__(self):
        self.checkpointing_interval = 1800  # 30 minutes
        self.min_price_savings = 0.3  # Require 30% savings for spot
        
    def should_use_spot(self, job):
        """Decide if spot instances are appropriate"""
        
        # Don't use spot for critical or short jobs
        if job.priority == 'critical' or job.estimated_hours < 2:
            return False
            
        # Check if job is checkpoint-friendly
        if not job.supports_resume:
            return False
            
        # Compare prices
        on_demand_price = self.get_on_demand_price(job.gpu_type)
        spot_price = self.get_spot_price(job.gpu_type)
        
        savings = (on_demand_price - spot_price) / on_demand_price
        
        return savings >= self.min_price_savings
        
    def handle_spot_interruption(self, instance_id):
        """Handle spot instance termination"""
        
        print(f"Spot instance {instance_id} interrupted!")
        
        # Force checkpoint save
        self.force_checkpoint(instance_id)
        
        # Wait for checkpoint upload
        time.sleep(60)
        
        # Launch replacement
        job = self.get_job_for_instance(instance_id)
        new_instance = self.launch_replacement(job)
        
        print(f"Launched replacement: {new_instance}")
```

---

## 5. Cost Optimization Strategies

### Smart Scheduling

```python
# cost_scheduler.py
class CostAwareScheduler:
    def __init__(self):
        self.price_history = PriceHistory()
        self.job_queue = PriorityQueue()
        
    def schedule_jobs(self):
        """Schedule jobs based on cost optimization"""
        
        while not self.job_queue.empty():
            job = self.job_queue.get()
            
            # Check if we should wait for better prices
            if self.should_defer(job):
                self.job_queue.put(job)  # Re-queue
                continue
                
            # Select execution strategy
            if job.size == 'small':
                self.execute_local(job)
            elif job.size == 'medium':
                if self.get_spot_price() < 2.00:
                    self.execute_cloud_spot(job)
                else:
                    self.execute_local_quantized(job)
            else:  # large
                self.execute_cloud_optimized(job)
                
    def should_defer(self, job):
        """Check if we should wait for better prices"""
        
        if job.priority == 'critical':
            return False
            
        current_price = self.get_spot_price()
        predicted_price = self.price_history.predict_price(hours_ahead=4)
        
        # Wait if prices expected to drop >20%
        return predicted_price < current_price * 0.8
```

### Budget Tracking Dashboard

```python
# budget_dashboard.py
import plotly.graph_objects as go
from datetime import datetime, timedelta

class BudgetDashboard:
    def __init__(self):
        self.cost_data = self.load_cost_data()
        
    def generate_report(self):
        """Generate cost analysis report"""
        
        report = {
            'current_month': {
                'local_compute': self.calculate_local_costs(),
                'cloud_compute': self.calculate_cloud_costs(),
                'storage': self.calculate_storage_costs(),
                'total': 0
            },
            'projections': {
                'end_of_month': self.project_monthly_cost(),
                'quarterly': self.project_quarterly_cost()
            },
            'optimization_suggestions': self.get_suggestions()
        }
        
        report['current_month']['total'] = sum(report['current_month'].values())
        
        return report
        
    def get_suggestions(self):
        """Get cost optimization suggestions"""
        
        suggestions = []
        
        # Analyze usage patterns
        cloud_usage = self.get_cloud_usage_hours()
        local_usage = self.get_local_usage_hours()
        
        if cloud_usage > 100:  # >100 hours/month
            suggestions.append({
                'action': 'Consider reserved H100 instances',
                'savings': '$500-800/month',
                'effort': 'medium'
            })
            
        if local_usage < 50:  # Underutilized local
            suggestions.append({
                'action': 'Increase local GPU utilization',
                'savings': '$200-300/month',
                'effort': 'low'
            })
            
        return suggestions
```

---

## 6. Practical Examples

### Example 1: Fine-tuning Llama 2 7B

```bash
# Runs locally on RTX 4090
python train.py \
    --model meta-llama/Llama-2-7b-hf \
    --dataset local/my-dataset \
    --use-qlora \
    --batch-size 4 \
    --gradient-accumulation 8

# Cost: ~$2 electricity
# Time: ~8 hours
```

### Example 2: Training 70B Model

```bash
# Automatically bursts to cloud
python train.py \
    --model meta-llama/Llama-2-70b-hf \
    --dataset s3://my-bucket/large-dataset \
    --distributed \
    --cloud-burst-enabled

# Detects model size > local capacity
# Provisions H100 spot instance
# Cost: ~$50 (24 hours spot)
# Time: ~24 hours
```

### Example 3: Batch Inference

```bash
# Hybrid execution - dev on local, production on cloud
python inference.py \
    --model my-finetuned-model \
    --input-dir s3://requests/pending \
    --execution-mode hybrid \
    --max-cloud-spend 100

# Processes first 1000 requests locally
# Bursts to cloud for remaining if under budget
# Cost: $5 local + $95 cloud
```

---

## 7. Monitoring and Alerts

### Set Up Alerts

```yaml
# alerts.yaml
alerts:
  budget:
    - name: "Daily spend exceeded"
      condition: "daily_spend > 50"
      action: "email"
      
    - name: "Monthly budget 80%"
      condition: "monthly_spend > 800"
      action: "pause_non_critical"
      
  performance:
    - name: "Low GPU utilization"
      condition: "gpu_util < 50% for 30min"
      action: "investigate"
      
  spot:
    - name: "Spot termination warning"
      condition: "spot_termination_notice"
      action: "emergency_checkpoint"
```

---

## 8. Quick Start Commands

### Initialize Hybrid Environment

```bash
# Clone the hybrid manager
git clone https://github.com/your-repo/hybrid-ai-trainer
cd hybrid-ai-trainer

# Install dependencies
pip install -r requirements.txt

# Configure providers
export RUNPOD_API_KEY="your-key"
export LAMBDA_API_KEY="your-key"
export AWS_ACCESS_KEY_ID="your-key"
export AWS_SECRET_ACCESS_KEY="your-secret"

# Test setup
python test_hybrid_setup.py

# Start web dashboard
python dashboard.py --port 8080
```

### First Hybrid Training Run

```bash
# Start with a medium model (13B)
python hybrid_train.py \
    --model teknium/OpenHermes-13B \
    --dataset your-dataset \
    --auto-select-compute \
    --max-hourly-spend 5.00

# Monitor via dashboard
open http://localhost:8080
```

---

## Key Takeaways

1. **Use Local First**: Always prefer local GPUs for development and smaller models
2. **Burst Intelligently**: Only use cloud for large models or time-critical training
3. **Leverage Spot**: Save 30-40% with spot instances for fault-tolerant workloads
4. **Monitor Costs**: Track spending in real-time to avoid surprises
5. **Optimize Transfers**: Minimize data movement between local and cloud

With this hybrid approach, you can achieve 80% of the performance of a full cloud setup at 20% of the cost.