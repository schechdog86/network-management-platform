# Hybrid AI Training Quick Reference

## Decision Matrix

| Model Size | Local Hardware | Strategy | Estimated Cost |
|------------|---------------|----------|----------------|
| <7B | 1x RTX 4090 | Local only | $0.20/hour |
| 7-13B | 2x RTX 4090 | Local with quantization | $0.40/hour |
| 13-30B | 4x RTX 4090 | Local with QLoRA or Cloud spot | $0.80/hour local, $2/hour cloud |
| 30-70B | Cloud required | H100 spot instance | $2-3/hour |
| >70B | Cloud required | Multi-H100 or quantized | $8-20/hour |

## Cloud Provider Cheat Sheet

### RunPod (Best Overall)
```bash
# Quick H100 spot instance
runpodctl create pod \
  --name "training-job" \
  --gpu "H100" \
  --spot \
  --container "pytorch/pytorch:2.1.0-cuda12.1-cudnn8-runtime"

# Prices: On-demand $2.99, Spot $1.99
```

### Lambda Labs (Most Reliable)
```bash
# Reserve H100 for guaranteed availability
lambda-cloud instance create \
  --type gpu_1x_h100_pcie \
  --name "stable-training"

# Price: $2.49/hour
```

### Vast.ai (Budget Option)
```bash
# Find cheapest H100
vastai search offers "gpu_name=H100 rentable=true" | sort -k5 -n | head -5

# Prices: $2.00-2.50/hour (varies)
```

## Cost Optimization Commands

### Local Training with Quantization
```bash
# 4-bit QLoRA training (70B model on 2x RTX 4090)
python train.py \
  --model meta-llama/Llama-2-70b-hf \
  --load-in-4bit \
  --use-qlora \
  --qlora-r 64 \
  --qlora-alpha 16 \
  --batch-size 1 \
  --gradient-accumulation 16
```

### Hybrid Execution
```bash
# Auto-select best compute option
python hybrid_train.py \
  --auto-compute \
  --budget-limit 100 \
  --prefer-spot \
  --checkpoint-freq 30min
```

### Emergency Checkpoint Save
```bash
# When spot instance termination warning
python emergency_save.py --upload-s3 --compress
```

## Memory Requirements

### Without Optimization
- 7B model: ~28GB VRAM (model + gradients + optimizer)
- 13B model: ~52GB VRAM
- 70B model: ~280GB VRAM

### With Optimization (QLoRA)
- 7B model: ~6GB VRAM
- 13B model: ~10GB VRAM  
- 70B model: ~35GB VRAM

### With DeepSpeed ZeRO-3
- Divide by number of GPUs
- Add 20% for communication overhead

## Network Transfer Costs

| Provider | Download | Upload | Between Regions |
|----------|----------|--------|-----------------|
| AWS S3 | Free | $0.023/GB | $0.02/GB |
| RunPod | Free | Free | N/A |
| Lambda | Free | $0.01/GB | N/A |

## Monitoring Commands

```bash
# Local GPU monitoring
watch -n 1 nvidia-smi

# Cloud cost tracking
python cost_monitor.py --current-month

# Training progress
tensorboard --logdir logs/

# Checkpoint size
du -sh checkpoints/ | sort -h
```

## Common Issues & Solutions

### Out of Memory (OOM)
```bash
# Progressive solutions:
1. Enable gradient checkpointing
2. Reduce batch size
3. Enable CPU offloading
4. Use QLoRA/GPTQ quantization
5. Burst to cloud
```

### Slow Training
```bash
# Check bottlenecks:
nvidia-smi dmon -s pucvmet  # GPU metrics
iotop -o  # Disk I/O
htop  # CPU usage
iftop  # Network usage
```

### High Costs
```bash
# Cost reduction:
1. Use spot instances (save 30-40%)
2. Train during off-peak hours
3. Use gradient accumulation instead of large batches
4. Implement early stopping
5. Use smaller models with better data
```

## Budget Templates

### $100/month Budget
- Local: 4x RTX 4090 setup (~$20 electricity)
- Cloud: 40 hours H100 spot (~$80)
- Best for: Research, prototyping

### $500/month Budget  
- Local: 4x RTX 4090 setup (~$50 electricity)
- Cloud: 225 hours H100 spot (~$450)
- Best for: Serious development

### $1000/month Budget
- Local: 8x RTX 4090 setup (~$100 electricity)
- Cloud: 450 hours H100 spot (~$900)
- Best for: Production training

## Emergency Procedures

### Spot Instance Termination
```bash
#!/bin/bash
# Add to training script
trap 'python save_checkpoint.py --emergency; aws s3 sync checkpoints/ s3://backup/' SIGTERM
```

### Budget Exceeded
```python
# Auto-pause when over budget
if cost_tracker.monthly_total > BUDGET_LIMIT:
    trainer.pause()
    notify_admin("Budget exceeded, training paused")
```

### Local GPU Failure
```python
# Automatic failover to cloud
try:
    train_local()
except GPUError:
    checkpoint = save_checkpoint()
    resume_on_cloud(checkpoint)
```

## Performance Tips

1. **Data Loading**: Use fast SSD, multiple workers
2. **Mixed Precision**: Always use fp16/bf16
3. **Compilation**: Use `torch.compile()` for 10-30% speedup
4. **Efficient Attention**: Use FlashAttention-2
5. **Profiling**: Profile before long runs

## Quick Calculations

### Training Time Estimates
- 1B parameters @ 1T tokens: ~2 weeks on H100
- 7B parameters @ 100B tokens: ~1 week on H100
- 70B parameters @ 10B tokens: ~1 week on 8x H100

### Cost Estimates
- Fine-tuning 7B: $20-50
- Fine-tuning 70B: $200-500
- Pre-training 7B: $5,000-10,000
- Pre-training 70B: $100,000+

Remember: **Always start small and scale up!**