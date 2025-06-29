#!/bin/bash

# Remote Save Script for Network Management Platform
# Saves project to rsync and webdav endpoints

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

# Project info
PROJECT_NAME="network-management-platform"
PROJECT_DIR="/home/edward/network/network-management-platform"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_NAME="${PROJECT_NAME}_${TIMESTAMP}"

# Colors for output
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

# Check if project directory exists
check_project() {
    if [ ! -d "$PROJECT_DIR" ]; then
        log_error "Project directory not found: $PROJECT_DIR"
        exit 1
    fi
    log_info "Project directory found: $PROJECT_DIR"
}

# Create archive of project
create_archive() {
    log_step "Creating project archive..."
    
    cd /home/edward/network
    
    # Create tar.gz archive excluding unnecessary files
    tar -czf "${BACKUP_NAME}.tar.gz" \
        --exclude="venv" \
        --exclude="node_modules" \
        --exclude="__pycache__" \
        --exclude="*.pyc" \
        --exclude=".git" \
        --exclude="*.log" \
        --exclude="tmp" \
        --exclude="*.tmp" \
        network-management-platform/
    
    if [ -f "${BACKUP_NAME}.tar.gz" ]; then
        ARCHIVE_SIZE=$(du -h "${BACKUP_NAME}.tar.gz" | cut -f1)
        log_info "Archive created: ${BACKUP_NAME}.tar.gz (${ARCHIVE_SIZE})"
    else
        log_error "Failed to create archive"
        exit 1
    fi
}

# Save via rsync
save_rsync() {
    log_step "Saving to rsync server..."
    
    # Check if rsync is installed
    if ! command -v rsync >/dev/null 2>&1; then
        log_error "rsync not installed. Installing..."
        sudo apt update && sudo apt install -y rsync
    fi
    
    # Set rsync password
    export RSYNC_PASSWORD="$RSYNC_PASSWORD"
    
    cd /home/edward/network
    
    # Try to sync the archive
    if rsync -avz --progress --port="$RSYNC_PORT" \
        "${BACKUP_NAME}.tar.gz" \
        "${RSYNC_USER}@${RSYNC_HOST}::backup/"; then
        log_info "✓ Successfully saved to rsync server"
    else
        log_error "✗ Failed to save to rsync server"
        return 1
    fi
    
    # Also sync the entire project directory
    if rsync -avz --progress --port="$RSYNC_PORT" \
        --exclude="venv/" \
        --exclude="node_modules/" \
        --exclude="__pycache__/" \
        --exclude="*.pyc" \
        --exclude=".git/" \
        --exclude="*.log" \
        --exclude="tmp/" \
        --exclude="*.tmp" \
        "$PROJECT_DIR/" \
        "${RSYNC_USER}@${RSYNC_HOST}::backup/${PROJECT_NAME}/"; then
        log_info "✓ Successfully synced project directory to rsync server"
    else
        log_error "✗ Failed to sync project directory to rsync server"
        return 1
    fi
    
    unset RSYNC_PASSWORD
}

# Save via WebDAV
save_webdav() {
    log_step "Saving to WebDAV server..."
    
    # Check if curl is installed
    if ! command -v curl >/dev/null 2>&1; then
        log_error "curl not installed. Installing..."
        sudo apt update && sudo apt install -y curl
    fi
    
    cd /home/edward/network
    
    # Upload archive via WebDAV
    local webdav_url="${WEBDAV_PROTOCOL}://${WEBDAV_HOST}:${WEBDAV_PORT}/remote.php/dav/files/${WEBDAV_USER}/"
    
    # Create backup directory
    if curl -X MKCOL \
        --user "${WEBDAV_USER}:${WEBDAV_PASSWORD}" \
        --insecure \
        "${webdav_url}backups/" 2>/dev/null; then
        log_info "Backup directory created/exists on WebDAV server"
    fi
    
    # Upload the archive
    if curl -T "${BACKUP_NAME}.tar.gz" \
        --user "${WEBDAV_USER}:${WEBDAV_PASSWORD}" \
        --insecure \
        --progress-bar \
        "${webdav_url}backups/${BACKUP_NAME}.tar.gz"; then
        log_info "✓ Successfully uploaded archive to WebDAV server"
    else
        log_error "✗ Failed to upload archive to WebDAV server"
        return 1
    fi
    
    # Create project-specific directory and upload key files
    if curl -X MKCOL \
        --user "${WEBDAV_USER}:${WEBDAV_PASSWORD}" \
        --insecure \
        "${webdav_url}${PROJECT_NAME}/" 2>/dev/null; then
        log_info "Project directory created/exists on WebDAV server"
    fi
    
    # Upload key project files
    local key_files=(
        "README.md"
        "docker-compose.yml"
        "PROJECT_CHECKLIST.md"
        "COMPREHENSIVE_PROJECT_CHECKLIST.md"
        "DETAILED_IMPLEMENTATION_PLAN.md"
        "HARDWARE_OPTIMIZED_PLAN.md"
        "UBUNTU_CORE_INTEGRATION_PLAN.md"
        "ADVANCED_RESEARCH_FINDINGS.md"
        "RECOMMENDED_MCP_TOOLS.md"
        "ZERO_BUDGET_MCP_TOOLS.md"
        "BOOTSTRAP_DEVELOPMENT_PLAN.md"
    )
    
    for file in "${key_files[@]}"; do
        if [ -f "/home/edward/network/$file" ]; then
            if curl -T "/home/edward/network/$file" \
                --user "${WEBDAV_USER}:${WEBDAV_PASSWORD}" \
                --insecure \
                "${webdav_url}${PROJECT_NAME}/$file" >/dev/null 2>&1; then
                log_info "✓ Uploaded $file"
            else
                log_warn "✗ Failed to upload $file"
            fi
        fi
    done
}

# Cleanup temporary files
cleanup() {
    log_step "Cleaning up temporary files..."
    
    cd /home/edward/network
    
    if [ -f "${BACKUP_NAME}.tar.gz" ]; then
        rm "${BACKUP_NAME}.tar.gz"
        log_info "Temporary archive removed"
    fi
}

# Test connectivity
test_connectivity() {
    log_step "Testing connectivity to remote servers..."
    
    # Test rsync server
    if nc -z "$RSYNC_HOST" "$RSYNC_PORT" 2>/dev/null; then
        log_info "✓ Rsync server reachable"
    else
        log_warn "✗ Rsync server not reachable"
    fi
    
    # Test WebDAV server
    if nc -z "$WEBDAV_HOST" "$WEBDAV_PORT" 2>/dev/null; then
        log_info "✓ WebDAV server reachable"
    else
        log_warn "✗ WebDAV server not reachable"
    fi
}

# Generate save report
generate_report() {
    log_step "Generating save report..."
    
    local report_file="/home/edward/network/save_report_${TIMESTAMP}.txt"
    
    cat > "$report_file" << EOF
Network Management Platform - Save Report
Generated: $(date)
========================================

Project: $PROJECT_NAME
Source: $PROJECT_DIR
Archive: ${BACKUP_NAME}.tar.gz

Remote Locations:
- Rsync: ${RSYNC_USER}@${RSYNC_HOST}:${RSYNC_PORT}
- WebDAV: ${WEBDAV_PROTOCOL}://${WEBDAV_HOST}:${WEBDAV_PORT}

Files Saved:
- Complete project archive
- Project directory sync (rsync)
- Key documentation files (webdav)

Timestamp: $TIMESTAMP
EOF
    
    log_info "Save report created: $report_file"
}

# Main save function
main() {
    local save_method="${1:-both}"
    
    log_info "Starting remote save process..."
    log_info "Save method: $save_method"
    
    check_project
    test_connectivity
    create_archive
    
    case "$save_method" in
        "rsync")
            save_rsync
            ;;
        "webdav")
            save_webdav
            ;;
        "both"|*)
            save_rsync
            save_webdav
            ;;
    esac
    
    generate_report
    cleanup
    
    log_info "Remote save process completed!"
    log_info "Project saved with timestamp: $TIMESTAMP"
}

# Help function
show_help() {
    echo "Usage: $0 [method]"
    echo ""
    echo "Methods:"
    echo "  rsync   - Save only to rsync server"
    echo "  webdav  - Save only to WebDAV server"
    echo "  both    - Save to both servers (default)"
    echo ""
    echo "Remote servers:"
    echo "  Rsync:  ${RSYNC_HOST}:${RSYNC_PORT}"
    echo "  WebDAV: ${WEBDAV_PROTOCOL}://${WEBDAV_HOST}:${WEBDAV_PORT}"
    echo ""
}

# Handle command line arguments
case "${1:-}" in
    "-h"|"--help"|"help")
        show_help
        exit 0
        ;;
    *)
        main "$@"
        ;;
esac