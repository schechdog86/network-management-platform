#!/bin/bash

# Network Management Platform Remote Save
# Standalone script for saving project to remote locations
# Created: $(date)

set -e

# Remote configuration
RSYNC_HOST="192.168.0.96"
RSYNC_PORT="873"
RSYNC_USER="schechter"
RSYNC_PASSWORD="Sexyredgirl1986"

WEBDAV_HOST="192.168.0.96"
WEBDAV_PORT="474"
WEBDAV_PROTOCOL="https"
WEBDAV_USER="schechter"
WEBDAV_PASSWORD="Sexyredgirl1986"

# Project configuration
PROJECT_NAME="network-management-platform"
PROJECT_DIR="/home/edward/network/network-management-platform"
DOCS_DIR="/home/edward/network"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_NAME="${PROJECT_NAME}_${TIMESTAMP}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

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

# Try different rsync modules
try_rsync_modules() {
    local modules=("backup" "data" "share" "files" "home" "public" "storage")
    
    export RSYNC_PASSWORD="$RSYNC_PASSWORD"
    
    for module in "${modules[@]}"; do
        log_info "Trying rsync module: $module"
        
        if rsync -avz --progress --port="$RSYNC_PORT" \
            "${BACKUP_NAME}.tar.gz" \
            "${RSYNC_USER}@${RSYNC_HOST}::${module}/" 2>/dev/null; then
            log_info "✓ Successfully saved to rsync module: $module"
            unset RSYNC_PASSWORD
            return 0
        fi
    done
    
    # Try without module (direct path)
    log_info "Trying rsync without module..."
    if rsync -avz --progress --port="$RSYNC_PORT" \
        "${BACKUP_NAME}.tar.gz" \
        "${RSYNC_USER}@${RSYNC_HOST}::/" 2>/dev/null; then
        log_info "✓ Successfully saved to rsync root"
        unset RSYNC_PASSWORD
        return 0
    fi
    
    unset RSYNC_PASSWORD
    return 1
}

# Save via WebDAV with better error handling
save_webdav_improved() {
    log_step "Saving to WebDAV server..."
    
    local webdav_url="${WEBDAV_PROTOCOL}://${WEBDAV_HOST}:${WEBDAV_PORT}"
    
    # Try different WebDAV paths
    local paths=(
        "/remote.php/dav/files/${WEBDAV_USER}/"
        "/webdav/"
        "/dav/"
        "/"
    )
    
    for path in "${paths[@]}"; do
        log_info "Trying WebDAV path: $path"
        
        # Test connection
        if curl -X OPTIONS \
            --user "${WEBDAV_USER}:${WEBDAV_PASSWORD}" \
            --insecure \
            --silent \
            --fail \
            "${webdav_url}${path}" >/dev/null 2>&1; then
            
            log_info "✓ WebDAV path accessible: $path"
            
            # Upload archive
            if curl -T "${BACKUP_NAME}.tar.gz" \
                --user "${WEBDAV_USER}:${WEBDAV_PASSWORD}" \
                --insecure \
                --progress-bar \
                "${webdav_url}${path}${BACKUP_NAME}.tar.gz"; then
                log_info "✓ Successfully uploaded to WebDAV: $path"
                return 0
            fi
        fi
    done
    
    log_error "Failed to find accessible WebDAV path"
    return 1
}

# Create comprehensive archive
create_comprehensive_archive() {
    log_step "Creating comprehensive project archive..."
    
    cd /home/edward/network
    
    # Create archive with all project files and documentation
    tar -czf "${BACKUP_NAME}.tar.gz" \
        --exclude="venv" \
        --exclude="node_modules" \
        --exclude="__pycache__" \
        --exclude="*.pyc" \
        --exclude=".git" \
        --exclude="*.log" \
        --exclude="tmp" \
        --exclude="*.tmp" \
        network-management-platform/ \
        *.md 2>/dev/null || true
    
    if [ -f "${BACKUP_NAME}.tar.gz" ]; then
        ARCHIVE_SIZE=$(du -h "${BACKUP_NAME}.tar.gz" | cut -f1)
        log_info "Archive created: ${BACKUP_NAME}.tar.gz (${ARCHIVE_SIZE})"
    else
        log_error "Failed to create archive"
        exit 1
    fi
}

# Save individual files via curl (HTTP PUT)
save_via_http_put() {
    log_step "Attempting HTTP PUT upload..."
    
    local base_url="${WEBDAV_PROTOCOL}://${WEBDAV_HOST}:${WEBDAV_PORT}"
    
    # Try simple HTTP PUT
    if curl -X PUT \
        --user "${WEBDAV_USER}:${WEBDAV_PASSWORD}" \
        --insecure \
        --data-binary "@${BACKUP_NAME}.tar.gz" \
        --progress-bar \
        "${base_url}/upload/${BACKUP_NAME}.tar.gz" 2>/dev/null; then
        log_info "✓ HTTP PUT upload successful"
        return 0
    fi
    
    # Try alternative upload endpoint
    if curl -X PUT \
        --user "${WEBDAV_USER}:${WEBDAV_PASSWORD}" \
        --insecure \
        --data-binary "@${BACKUP_NAME}.tar.gz" \
        --progress-bar \
        "${base_url}/${BACKUP_NAME}.tar.gz" 2>/dev/null; then
        log_info "✓ Direct HTTP PUT upload successful"
        return 0
    fi
    
    return 1
}

# Create project status file
create_project_status() {
    local status_file="project_status_${TIMESTAMP}.txt"
    
    cat > "$status_file" << EOF
Network Management Platform - Project Status
Generated: $(date)
===========================================

PROJECT OVERVIEW:
- Enterprise-grade network management platform
- Ray cluster integration with 12 GPU support
- Ubuntu Core deployment with snap packages
- Dual GUI (Qt desktop + React web)
- AI-powered automation and analysis

CURRENT PROGRESS:
✓ Project structure created
✓ Ray cluster configuration (12 GPUs)
✓ PostgreSQL + TimescaleDB database setup
✓ FastAPI backend foundation
✓ Ubuntu Core snap packages
✓ Docker containerization
✓ Development environment setup
✓ Comprehensive documentation

IN PROGRESS:
- FastAPI endpoints implementation
- GPU-accelerated network discovery
- Basic GUI interfaces

PENDING:
- AI automation implementation
- Full backup system
- Production deployment
- CI/CD pipeline

HARDWARE SETUP:
- 3 servers + 3 custom PCs
- 12 GPUs (4 per server cluster)
- Ray distributed computing cluster
- Ubuntu Core 24 deployment targets

TIMELINE:
- Phase 1 (Weeks 1-2): Foundation ✓
- Phase 2 (Weeks 3-4): Core features (in progress)
- Phase 3 (Weeks 5-6): Production deployment

FILES INCLUDED:
- Complete project source code
- Docker configurations
- Snap package definitions
- Ray cluster setup
- Database schemas
- Development scripts
- Comprehensive documentation

REMOTE SAVE LOCATIONS:
- Rsync: ${RSYNC_HOST}:${RSYNC_PORT}
- WebDAV: ${WEBDAV_PROTOCOL}://${WEBDAV_HOST}:${WEBDAV_PORT}

Archive: ${BACKUP_NAME}.tar.gz
Timestamp: $TIMESTAMP
EOF
    
    log_info "Project status file created: $status_file"
}

# Main execution
main() {
    log_info "Starting Network Management Platform remote save..."
    log_info "Timestamp: $TIMESTAMP"
    
    # Check if project exists
    if [ ! -d "$PROJECT_DIR" ]; then
        log_error "Project directory not found: $PROJECT_DIR"
        exit 1
    fi
    
    cd /home/edward/network
    
    # Create comprehensive archive
    create_comprehensive_archive
    
    # Create project status
    create_project_status
    
    # Try rsync with different modules
    log_step "Attempting rsync save..."
    if try_rsync_modules; then
        log_info "✓ Rsync save successful"
    else
        log_warn "✗ Rsync save failed - trying alternative methods"
    fi
    
    # Try WebDAV save
    if save_webdav_improved; then
        log_info "✓ WebDAV save successful"
    elif save_via_http_put; then
        log_info "✓ HTTP PUT save successful"
    else
        log_warn "✗ All WebDAV methods failed"
    fi
    
    # Show available files for manual transfer
    log_info "Available files for manual transfer:"
    ls -lh "${BACKUP_NAME}.tar.gz" "project_status_${TIMESTAMP}.txt" 2>/dev/null || true
    
    # Cleanup
    log_step "Cleaning up..."
    # Keep files for manual transfer if needed
    
    log_info "Remote save process completed!"
    log_info "Archive: ${BACKUP_NAME}.tar.gz"
    log_info "Status: project_status_${TIMESTAMP}.txt"
    
    # Display final summary
    echo ""
    echo "=== SAVE SUMMARY ==="
    echo "Project: $PROJECT_NAME"
    echo "Archive: ${BACKUP_NAME}.tar.gz"
    echo "Size: $(du -h "${BACKUP_NAME}.tar.gz" | cut -f1)"
    echo "Timestamp: $TIMESTAMP"
    echo ""
    echo "Remote targets:"
    echo "- Rsync: ${RSYNC_USER}@${RSYNC_HOST}:${RSYNC_PORT}"
    echo "- WebDAV: ${WEBDAV_PROTOCOL}://${WEBDAV_HOST}:${WEBDAV_PORT}"
    echo ""
    echo "Files ready for manual transfer if needed:"
    echo "- ${BACKUP_NAME}.tar.gz"
    echo "- project_status_${TIMESTAMP}.txt"
    echo "==================="
}

# Execute main function
main "$@"