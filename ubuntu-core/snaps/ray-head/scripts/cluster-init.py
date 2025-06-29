#!/usr/bin/env python3
"""
Ray Cluster Initialization Script
"""

import os
import yaml
import json
from pathlib import Path

def create_cluster_config():
    """Create initial cluster configuration"""
    
    config = {
        "cluster_name": "network-ai-cluster",
        "max_workers": int(os.environ.get("RAY_MAX_WORKER_NODES", "100")),
        "min_workers": int(os.environ.get("RAY_MIN_WORKER_NODES", "0")),
        
        "docker": {
            "image": "rayproject/ray:latest",
            "container_name": "ray_container",
            "pull_before_run": True,
        },
        
        "provider": {
            "type": "local",
            "head_ip": os.environ.get("RAY_HEAD_NODE_IP", "0.0.0.0"),
        },
        
        "auth": {
            "ssh_user": "ubuntu",
        },
        
        "available_node_types": {
            "ray.head.default": {
                "resources": {
                    "CPU": os.cpu_count(),
                    "memory": os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES'),
                },
                "node_config": {},
                "max_workers": 0,
            },
            "ray.worker.gpu": {
                "resources": {
                    "CPU": 8,
                    "GPU": 1,
                    "memory": 64 * 1024 * 1024 * 1024,  # 64GB
                },
                "node_config": {},
                "min_workers": 0,
                "max_workers": 10,
            },
            "ray.worker.cpu": {
                "resources": {
                    "CPU": 16,
                    "memory": 32 * 1024 * 1024 * 1024,  # 32GB
                },
                "node_config": {},
                "min_workers": 0,
                "max_workers": 20,
            },
        },
        
        "head_node_type": "ray.head.default",
        
        "file_mounts": {
            "/tmp/ray_tmp": os.path.join(os.environ['SNAP_DATA'], "ray"),
        },
        
        "cluster_synced_files": [],
        
        "initialization_commands": [
            "echo 'Ray cluster initialized'",
        ],
        
        "setup_commands": [],
        
        "head_setup_commands": [],
        
        "worker_setup_commands": [],
        
        "head_start_ray_commands": [],
        
        "worker_start_ray_commands": [],
    }
    
    # Save configuration
    config_path = Path(os.environ['SNAP_DATA']) / "cluster" / "cluster-config.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(config_path, 'w') as f:
        yaml.dump(config, f, default_flow_style=False)
    
    print(f"Cluster configuration saved to {config_path}")
    
    # Create autoscaler config
    autoscaler_config = {
        "autoscaling_config": {
            "autoscaling_mode": "default",
            "idle_timeout_minutes": 5,
            "upscaling_speed": 1.0,
            "downscaling_speed": 1.0,
        },
        
        "resource_demand_scheduler": {
            "enabled": True,
            "policy": "PACK",
        },
        
        "node_resources": {
            "worker_gpu": {
                "CPU": 8,
                "GPU": 1,
                "memory": 64 * 1024 * 1024 * 1024,
            },
            "worker_cpu": {
                "CPU": 16,
                "memory": 32 * 1024 * 1024 * 1024,
            },
        },
        
        "scaling_policies": {
            "gpu_priority": {
                "priority": 1,
                "node_type": "ray.worker.gpu",
                "trigger": {
                    "gpu_demand": 0.8,
                },
            },
            "cpu_scaling": {
                "priority": 2,
                "node_type": "ray.worker.cpu",
                "trigger": {
                    "cpu_demand": 0.7,
                },
            },
        },
    }
    
    autoscaler_path = Path(os.environ['SNAP_DATA']) / "cluster" / "autoscaler-config.yaml"
    with open(autoscaler_path, 'w') as f:
        yaml.dump(autoscaler_config, f, default_flow_style=False)
    
    print(f"Autoscaler configuration saved to {autoscaler_path}")
    
    # Create monitoring configuration
    monitoring_config = {
        "prometheus": {
            "enabled": True,
            "port": 9090,
            "metrics_export_port": 8080,
        },
        
        "grafana": {
            "enabled": True,
            "port": 3000,
            "dashboards": [
                "ray-cluster-overview",
                "ray-node-metrics",
                "ray-job-metrics",
            ],
        },
        
        "alerts": {
            "node_failure": {
                "enabled": True,
                "threshold": 1,
                "action": "email",
            },
            "high_memory_usage": {
                "enabled": True,
                "threshold": 0.9,
                "action": "scale_up",
            },
            "job_failure_rate": {
                "enabled": True,
                "threshold": 0.1,
                "action": "alert",
            },
        },
    }
    
    monitoring_path = Path(os.environ['SNAP_DATA']) / "cluster" / "monitoring-config.yaml"
    with open(monitoring_path, 'w') as f:
        yaml.dump(monitoring_config, f, default_flow_style=False)
    
    print(f"Monitoring configuration saved to {monitoring_path}")

if __name__ == "__main__":
    create_cluster_config()