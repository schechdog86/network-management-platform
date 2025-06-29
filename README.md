# Network Management Platform with Ubuntu Core 24

A comprehensive network management platform designed for Ubuntu Core 24, featuring AI-powered capabilities, GPU support, and distributed computing.

## Overview

This project implements a complete network management solution with:
- **Ubuntu Core 24 Integration**: Fully snap-based architecture
- **AI Capabilities**: Ray cluster integration for distributed AI workloads
- **GPU Support**: Optimized for NVIDIA GPUs with CUDA support
- **Modern Web UI**: React-based dashboard with real-time monitoring
- **Enterprise Features**: PostgreSQL + TimescaleDB, FastAPI backend, comprehensive API

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   network-web   │────▶│ network-manager │────▶│   network-db    │
│  (React UI)     │     │ (FastAPI Server)│     │  (PostgreSQL)   │
└─────────────────┘     └─────────────────┘     └─────────────────┘
         │                       │                        │
         └──────────────────────▶│    ray-head     │◀────┘
                                │ (AI Orchestrator)│
                                └─────────────────┘
                                         │
                                ┌────────▼────────┐
                                │   ai-worker     │
                                │  (GPU Workers)  │
                                └─────────────────┘
```

## Components

### Snaps
- **network-db**: PostgreSQL 16 with TimescaleDB for time-series metrics
- **network-manager-server**: FastAPI backend with comprehensive REST API
- **network-web**: React frontend with modern dashboard
- **ray-head**: Ray cluster head for AI orchestration
- **ai-worker**: GPU-enabled worker nodes (3 variants: basic, pro, budget)

### Features
- Device discovery and management
- Real-time metrics collection and visualization
- Wake-on-LAN support
- PXE boot management
- AI-powered predictive maintenance
- Backup and restore capabilities
- GPU monitoring and optimization
- Distributed AI training support

## Quick Start

### Prerequisites
- Ubuntu Core 24 or Ubuntu 22.04/24.04
- Snapcraft (`sudo snap install snapcraft --classic`)
- 8GB+ RAM, 50GB+ storage
- NVIDIA GPU (optional but recommended)

### Installation

1. **Clone the repository**:
```bash
git clone <repository-url>
cd network-management-platform
```

2. **Build all snaps**:
```bash
cd ubuntu-core
./scripts/build-all-snaps.sh
```

3. **Install snaps** (in order):
```bash
sudo snap install --dangerous build/snaps/network-db_*.snap
sudo snap install --dangerous build/snaps/network-manager-server_*.snap
sudo snap install --dangerous build/snaps/network-web_*.snap
sudo snap install --dangerous build/snaps/ray-head_*.snap
sudo snap install --dangerous build/snaps/ai-worker_*.snap
```

4. **Connect interfaces**:
```bash
sudo snap connect network-manager-server:postgres-db network-db:postgres-socket
sudo snap connect network-web:api-connection network-manager-server:network-manager-api
sudo snap connect ray-head:network-api network-manager-server:network-manager-api
sudo snap connect ai-worker:ray-cluster ray-head:ray-cluster
```

5. **Access the platform**:
- Web UI: http://localhost:3000
- API: http://localhost:8000/docs
- Ray Dashboard: http://localhost:8265

### Testing

Run the inter-snap communication test:
```bash
./ubuntu-core/scripts/test-inter-snap-communication.sh
```

## Development

### Project Structure
```
.
├── network-management-platform/    # Main application
│   ├── backend/                   # FastAPI backend
│   ├── frontend/                  # React frontend
│   └── docs/                      # Documentation
├── ubuntu-core/                   # Ubuntu Core integration
│   ├── snaps/                     # Snap packages
│   ├── scripts/                   # Build and deployment scripts
│   └── docs/                      # Ubuntu Core documentation
└── README.md
```

### Building Individual Snaps
```bash
cd ubuntu-core/snaps/<snap-name>
snapcraft
```

### Running Tests
```bash
# Backend tests
cd network-management-platform/backend
pytest

# Frontend tests
cd network-management-platform/frontend
npm test
```

## Documentation

- [Ubuntu Core Development Setup](ubuntu-core/docs/DEVELOPMENT_SETUP.md)
- [Bare Metal Deployment Guide](ubuntu-core/docs/BARE_METAL_DEPLOYMENT.md)
- [Inter-Snap Communication](ubuntu-core/docs/INTER_SNAP_COMMUNICATION.md)
- [AI Worker Deployment](ubuntu-core/docs/AI_WORKER_DEPLOYMENT_GUIDE.md)
- [API Documentation](network-management-platform/backend/API_DOCUMENTATION.md)

## AI Capabilities

The platform includes advanced AI features:
- Distributed training with Ray
- GPU optimization for H100/H200/RTX 4090
- Hybrid cloud support (local + cloud bursting)
- Model serving and inference
- Predictive maintenance algorithms

See [AI System Improvement Plans](ubuntu-core/) for detailed architecture.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request

## License

[License information to be added]

## Support

For issues and questions:
- Create an issue in the GitHub repository
- Check the troubleshooting guides in the documentation

## Acknowledgments

Built with Ubuntu Core 24, leveraging the power of snaps for a secure, modular architecture.