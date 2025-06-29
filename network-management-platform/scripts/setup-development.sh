#!/bin/bash

# Network Management Platform - Development Environment Setup
# Sets up complete development environment with Ray cluster and Ubuntu Core

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# Check if running with sufficient privileges
check_privileges() {
    if [[ $EUID -eq 0 ]]; then
        log_error "This script should not be run as root"
        exit 1
    fi
    
    if ! sudo -n true 2>/dev/null; then
        log_warn "This script requires sudo privileges"
        sudo -v
    fi
}

# Check system requirements
check_system_requirements() {
    log_step "Checking system requirements..."
    
    # Check Ubuntu version
    if ! lsb_release -d | grep -q "Ubuntu"; then
        log_error "This setup script is designed for Ubuntu. Other distributions may require manual setup."
        exit 1
    fi
    
    # Check for GPU availability
    if command -v nvidia-smi >/dev/null 2>&1; then
        if nvidia-smi >/dev/null 2>&1; then
            GPU_COUNT=$(nvidia-smi --list-gpus | wc -l)
            log_info "GPU support detected: $GPU_COUNT GPU(s) available"
        else
            log_warn "NVIDIA drivers found but no GPU detected"
        fi
    else
        log_warn "No GPU support detected - some features will run in CPU mode"
    fi
    
    # Check available memory
    MEMORY_GB=$(free -g | awk '/^Mem:/{print $2}')
    if [ "$MEMORY_GB" -lt 16 ]; then
        log_warn "System has ${MEMORY_GB}GB RAM. Recommended minimum is 16GB for optimal performance."
    else
        log_info "System memory: ${MEMORY_GB}GB"
    fi
    
    # Check available disk space
    DISK_SPACE_GB=$(df -BG . | tail -1 | awk '{print $4}' | sed 's/G//')
    if [ "$DISK_SPACE_GB" -lt 50 ]; then
        log_error "Insufficient disk space. Need at least 50GB free, have ${DISK_SPACE_GB}GB"
        exit 1
    else
        log_info "Available disk space: ${DISK_SPACE_GB}GB"
    fi
}

# Install system dependencies
install_system_dependencies() {
    log_step "Installing system dependencies..."
    
    # Update package lists
    sudo apt update
    
    # Install core development tools
    sudo apt install -y \
        python3.11 \
        python3.11-dev \
        python3.11-venv \
        python3-pip \
        build-essential \
        cmake \
        git \
        curl \
        wget \
        vim \
        htop \
        tree \
        jq
    
    # Install network tools
    sudo apt install -y \
        nmap \
        snmp \
        snmp-mibs-downloader \
        iproute2 \
        iputils-ping \
        tcpdump \
        wireshark-common \
        net-tools \
        openssh-client \
        openssh-server
    
    # Install container tools
    sudo apt install -y \
        docker.io \
        docker-compose \
        containerd
    
    # Install Node.js for frontend development
    curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
    sudo apt install -y nodejs
    
    # Install snapcraft for snap development
    sudo snap install snapcraft --classic
    sudo snap install multipass
    
    log_info "System dependencies installed successfully"
}

# Install CUDA and GPU drivers (if needed)
install_gpu_support() {
    if command -v nvidia-smi >/dev/null 2>&1; then
        log_info "NVIDIA drivers already installed"
        return 0
    fi
    
    if ! lspci | grep -i nvidia >/dev/null; then
        log_info "No NVIDIA GPU detected, skipping GPU driver installation"
        return 0
    fi
    
    log_step "Installing NVIDIA drivers and CUDA..."
    
    # Add NVIDIA repository
    wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-keyring_1.0-1_all.deb
    sudo dpkg -i cuda-keyring_1.0-1_all.deb
    rm cuda-keyring_1.0-1_all.deb
    
    sudo apt update
    sudo apt install -y cuda-drivers-535 cuda-toolkit-12-1
    
    # Add CUDA to PATH
    echo 'export PATH=/usr/local/cuda-12.1/bin:$PATH' >> ~/.bashrc
    echo 'export LD_LIBRARY_PATH=/usr/local/cuda-12.1/lib64:$LD_LIBRARY_PATH' >> ~/.bashrc
    
    log_info "GPU support installed. Please reboot before continuing."
    log_warn "After reboot, run this script again to complete setup"
    exit 0
}

# Set up Python virtual environment
setup_python_environment() {
    log_step "Setting up Python virtual environment..."
    
    # Create virtual environment
    python3.11 -m venv venv
    source venv/bin/activate
    
    # Upgrade pip
    pip install --upgrade pip setuptools wheel
    
    # Install backend dependencies
    cd backend
    pip install -r requirements.txt
    
    # Install PyTorch with CUDA support if available
    if command -v nvidia-smi >/dev/null 2>&1; then
        pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
        pip install cupy-cuda12x
    else
        pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
    fi
    
    cd ..
    
    log_info "Python environment set up successfully"
}

# Set up Docker environment
setup_docker_environment() {
    log_step "Setting up Docker environment..."
    
    # Add user to docker group
    sudo usermod -aG docker "$USER"
    
    # Enable and start Docker service
    sudo systemctl enable docker
    sudo systemctl start docker
    
    # Install NVIDIA Container Toolkit if GPU available
    if command -v nvidia-smi >/dev/null 2>&1; then
        log_info "Installing NVIDIA Container Toolkit..."
        
        distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
        curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
        curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
            sudo tee /etc/apt/sources.list.d/nvidia-docker.list
        
        sudo apt update
        sudo apt install -y nvidia-container-toolkit
        sudo systemctl restart docker
    fi
    
    log_info "Docker environment configured"
}

# Set up database
setup_database() {
    log_step "Setting up database services..."
    
    # Create docker-compose override for development
    cat > docker-compose.override.yml << EOF
version: '3.8'
services:
  database:
    ports:
      - "5432:5432"
    environment:
      POSTGRES_PASSWORD: dev_password_123
  
  redis:
    ports:
      - "6379:6379"
EOF
    
    # Start database services
    docker-compose up -d database redis
    
    # Wait for database to be ready
    log_info "Waiting for database to be ready..."
    sleep 30
    
    # Test database connection
    if docker-compose exec -T database pg_isready -U netmgmt; then
        log_info "Database is ready"
    else
        log_error "Database failed to start properly"
        return 1
    fi
}

# Set up Ray cluster
setup_ray_cluster() {
    log_step "Setting up Ray cluster..."
    
    # Start Ray head node
    docker-compose up -d ray-head
    
    # Wait for Ray to be ready
    log_info "Waiting for Ray cluster to be ready..."
    sleep 60
    
    # Test Ray connection
    if curl -f http://localhost:8265 >/dev/null 2>&1; then
        log_info "Ray cluster is ready"
        log_info "Ray Dashboard available at: http://localhost:8265"
    else
        log_error "Ray cluster failed to start properly"
        return 1
    fi
}

# Set up frontend development environment
setup_frontend() {
    log_step "Setting up frontend development environment..."
    
    cd frontend
    
    # Initialize React project if not exists
    if [ ! -f package.json ]; then
        npx create-react-app . --template typescript
    fi
    
    # Install additional dependencies
    npm install @mui/material @emotion/react @emotion/styled
    npm install @mui/icons-material
    npm install axios socket.io-client
    npm install chart.js react-chartjs-2
    npm install @types/node @types/react @types/react-dom
    
    cd ..
    
    log_info "Frontend environment set up successfully"
}

# Create development configuration
create_development_config() {
    log_step "Creating development configuration..."
    
    # Create .env file for development
    cat > .env << EOF
# Development Environment Configuration
ENVIRONMENT=development
SECRET_KEY=dev-secret-key-change-in-production
DATABASE_URL=postgresql://netmgmt:dev_password_123@localhost:5432/network_mgmt
REDIS_URL=redis://localhost:6379
RAY_ADDRESS=ray://localhost:10001
CUDA_VISIBLE_DEVICES=0,1,2,3
LOG_LEVEL=DEBUG
EOF
    
    # Create development docker-compose override
    if [ ! -f docker-compose.override.yml ]; then
        cat > docker-compose.override.yml << EOF
version: '3.8'
services:
  backend:
    environment:
      - ENVIRONMENT=development
      - LOG_LEVEL=DEBUG
    volumes:
      - ./backend:/app
    ports:
      - "8000:8000"
  
  frontend:
    environment:
      - NODE_ENV=development
    volumes:
      - ./frontend:/app
      - /app/node_modules
    ports:
      - "3000:3000"
EOF
    fi
    
    log_info "Development configuration created"
}

# Validate installation
validate_installation() {
    log_step "Validating installation..."
    
    local all_good=true
    
    # Check Python environment
    if source venv/bin/activate && python -c "import ray, torch, fastapi"; then
        log_info "✓ Python environment OK"
    else
        log_error "✗ Python environment has issues"
        all_good=false
    fi
    
    # Check Docker services
    if docker-compose ps | grep -q "Up"; then
        log_info "✓ Docker services OK"
    else
        log_error "✗ Docker services not running"
        all_good=false
    fi
    
    # Check database
    if docker-compose exec -T database pg_isready -U netmgmt >/dev/null 2>&1; then
        log_info "✓ Database OK"
    else
        log_error "✗ Database not accessible"
        all_good=false
    fi
    
    # Check Ray cluster
    if curl -f http://localhost:8265 >/dev/null 2>&1; then
        log_info "✓ Ray cluster OK"
    else
        log_error "✗ Ray cluster not accessible"
        all_good=false
    fi
    
    if [ "$all_good" = true ]; then
        log_info "All components validated successfully!"
        return 0
    else
        log_error "Some components failed validation"
        return 1
    fi
}

# Print next steps
print_next_steps() {
    log_step "Setup complete! Next steps:"
    
    echo ""
    echo "1. Activate Python environment:"
    echo "   source venv/bin/activate"
    echo ""
    echo "2. Start development servers:"
    echo "   docker-compose up -d"
    echo ""
    echo "3. Access services:"
    echo "   • Ray Dashboard: http://localhost:8265"
    echo "   • Backend API: http://localhost:8000"
    echo "   • Frontend: http://localhost:3000"
    echo "   • Grafana: http://localhost:3001"
    echo ""
    echo "4. Run backend server:"
    echo "   cd backend && python -m uvicorn app.main:app --reload"
    echo ""
    echo "5. Run frontend development server:"
    echo "   cd frontend && npm start"
    echo ""
    echo "6. Build snap packages:"
    echo "   ./scripts/build-snaps.sh"
    echo ""
    echo "For more information, see:"
    echo "   • README.md"
    echo "   • docs/development.md"
    echo ""
}

# Main setup function
main() {
    log_info "Starting Network Management Platform development setup..."
    
    check_privileges
    check_system_requirements
    install_system_dependencies
    install_gpu_support
    setup_docker_environment
    setup_python_environment
    setup_database
    setup_ray_cluster
    setup_frontend
    create_development_config
    
    if validate_installation; then
        print_next_steps
        log_info "Development environment setup completed successfully!"
    else
        log_error "Setup completed with some issues. Check the logs above."
        exit 1
    fi
}

# Run main function
main "$@"