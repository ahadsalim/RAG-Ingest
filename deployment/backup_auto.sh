#!/bin/bash

# =============================================================================
# Automatic Full Backup Script
# Runs every 6 hours via cron, sends backup to remote server
# Includes: Database + .env config + Nginx Proxy Manager
# =============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Load environment variables
if [ -f "$PROJECT_ROOT/.env" ]; then
    source "$PROJECT_ROOT/.env"
elif [ -f "/srv/.env" ]; then
    source "/srv/.env"
else
    echo -e "${RED}Error: .env file not found${NC}"
    exit 1
fi

# Configuration from .env
BACKUP_SERVER_HOST="${BACKUP_SERVER_HOST:-}"
BACKUP_SERVER_USER="${BACKUP_SERVER_USER:-root}"
BACKUP_SERVER_PATH="${BACKUP_SERVER_PATH:-/srv/backup/ingest}"
BACKUP_SSH_KEY="${BACKUP_SSH_KEY:-/root/.ssh/backup_key}"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"

# Local settings
LOCAL_BACKUP_DIR="/tmp/ingest_auto_backup"
LOG_FILE="/var/log/ingest_auto_backup.log"
COMPOSE_FILE="$SCRIPT_DIR/docker-compose.ingest.yml"
ENV_FILE="$PROJECT_ROOT/.env"

# Logging function
log() {
    local level="$1"
    local message="$2"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$timestamp] [$level] $message" | tee -a "$LOG_FILE"
}

print_info() { log "INFO" "$1"; }
print_success() { log "SUCCESS" "$1"; }
print_error() { log "ERROR" "$1"; }
print_warning() { log "WARNING" "$1"; }

# Validate configuration
validate_config() {
    if [ -z "$BACKUP_SERVER_HOST" ]; then
        print_error "BACKUP_SERVER_HOST not configured in .env"
        exit 1
    fi
    
    if [ ! -f "$BACKUP_SSH_KEY" ]; then
        print_error "SSH key not found: $BACKUP_SSH_KEY"
        print_info "Generate with: ssh-keygen -t ed25519 -f $BACKUP_SSH_KEY -N ''"
        print_info "Then copy to server: ssh-copy-id -i $BACKUP_SSH_KEY $BACKUP_SERVER_USER@$BACKUP_SERVER_HOST"
        exit 1
    fi
    
    if [ ! -f "$COMPOSE_FILE" ]; then
        print_error "Docker compose file not found: $COMPOSE_FILE"
        exit 1
    fi
}

# Test SSH connection
test_ssh_connection() {
    print_info "Testing SSH connection to $BACKUP_SERVER_HOST..."
    if ssh -i "$BACKUP_SSH_KEY" -o ConnectTimeout=10 -o BatchMode=yes \
        "$BACKUP_SERVER_USER@$BACKUP_SERVER_HOST" "echo 'Connection OK'" >/dev/null 2>&1; then
        print_success "SSH connection successful"
        return 0
    else
        print_error "SSH connection failed"
        return 1
    fi
}

# Create full backup (DB + config + NPM)
create_full_backup() {
    local date=$(date +%Y%m%d_%H%M%S)
    local backup_name="ingest_auto_${date}"
    local backup_dir="$LOCAL_BACKUP_DIR/$backup_name"
    local backup_path="$LOCAL_BACKUP_DIR/${backup_name}.tar.gz"
    
    mkdir -p "$backup_dir"
    
    # 1. Database
    print_info "[1/3] Creating database backup..."
    if docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T db \
        pg_dump -U "${POSTGRES_USER:-ingest}" "${POSTGRES_DB:-ingest}" | gzip > "$backup_dir/database.sql.gz"; then
        print_success "Database backup done"
    else
        print_error "Database backup failed"
        rm -rf "$backup_dir"
        return 1
    fi
    
    # 2. Environment file
    print_info "[2/3] Backing up configuration..."
    mkdir -p "$backup_dir/config"
    if [ -f "$ENV_FILE" ]; then
        cp "$ENV_FILE" "$backup_dir/config/.env"
        print_success ".env file backed up"
    fi
    
    # 3. Nginx Proxy Manager
    print_info "[3/3] Backing up Nginx Proxy Manager..."
    local npm_volume=$(docker volume ls --format "{{.Name}}" | grep -E "npm_data$" | head -1)
    if [ -n "$npm_volume" ]; then
        if docker run --rm -v "$npm_volume:/data:ro" alpine tar -czf - /data > "$backup_dir/npm_data.tar.gz" 2>/dev/null; then
            print_success "NPM data backed up"
        else
            print_warning "NPM backup failed (continuing...)"
        fi
    fi
    
    local npm_ssl_volume=$(docker volume ls --format "{{.Name}}" | grep -E "npm_letsencrypt$" | head -1)
    if [ -n "$npm_ssl_volume" ]; then
        if docker run --rm -v "$npm_ssl_volume:/data:ro" alpine tar -czf - /data > "$backup_dir/npm_letsencrypt.tar.gz" 2>/dev/null; then
            print_success "NPM SSL certificates backed up"
        else
            print_warning "NPM SSL backup failed (continuing...)"
        fi
    fi
    
    # Create metadata
    cat > "$backup_dir/backup_info.json" << EOF
{
    "backup_date": "$(date -Iseconds)",
    "backup_type": "auto_full",
    "server_hostname": "$(hostname)",
    "postgres_db": "${POSTGRES_DB:-ingest}"
}
EOF
    
    # Compress everything
    print_info "Compressing backup..."
    cd "$LOCAL_BACKUP_DIR"
    tar -czf "${backup_name}.tar.gz" "${backup_name}/"
    rm -rf "${backup_name}/"
    
    # Create checksum
    sha256sum "${backup_name}.tar.gz" > "${backup_name}.tar.gz.sha256"
    
    local size=$(du -sh "$backup_path" | cut -f1)
    print_success "Full backup created: ${backup_name}.tar.gz ($size)"
    
    # Return path (don't use echo, set a global variable)
    BACKUP_FILE_PATH="$backup_path"
    return 0
}

# Send backup to remote server
send_to_remote() {
    local backup_file="$1"
    local backup_name=$(basename "$backup_file")
    
    print_info "Sending backup to remote server..."
    
    # Ensure remote directory exists
    ssh -i "$BACKUP_SSH_KEY" "$BACKUP_SERVER_USER@$BACKUP_SERVER_HOST" \
        "mkdir -p $BACKUP_SERVER_PATH"
    
    # Send backup file
    if scp -i "$BACKUP_SSH_KEY" "$backup_file" "${backup_file}.sha256" \
        "$BACKUP_SERVER_USER@$BACKUP_SERVER_HOST:$BACKUP_SERVER_PATH/"; then
        print_success "Backup sent to $BACKUP_SERVER_HOST:$BACKUP_SERVER_PATH/$backup_name"
        return 0
    else
        print_error "Failed to send backup to remote server"
        return 1
    fi
}

# Cleanup old backups on remote server
cleanup_remote_backups() {
    print_info "Cleaning up old backups on remote server (older than $BACKUP_RETENTION_DAYS days)..."
    
    ssh -i "$BACKUP_SSH_KEY" "$BACKUP_SERVER_USER@$BACKUP_SERVER_HOST" \
        "find $BACKUP_SERVER_PATH -name 'ingest_auto_*.tar.gz*' -mtime +$BACKUP_RETENTION_DAYS -delete 2>/dev/null || true"
    
    # Count remaining backups
    local count=$(ssh -i "$BACKUP_SSH_KEY" "$BACKUP_SERVER_USER@$BACKUP_SERVER_HOST" \
        "ls -1 $BACKUP_SERVER_PATH/ingest_auto_*.tar.gz 2>/dev/null | wc -l")
    
    print_info "Remote server has $count backup(s)"
}

# Cleanup local temp files
cleanup_local() {
    print_info "Cleaning up local temporary files..."
    rm -rf "$LOCAL_BACKUP_DIR"
}

# Setup cron job
setup_cron() {
    print_info "Setting up cron job for automatic backup every 6 hours..."
    
    local cron_job="0 */6 * * * $SCRIPT_DIR/backup_auto.sh >> $LOG_FILE 2>&1"
    
    # Remove existing job if present
    crontab -l 2>/dev/null | grep -v "backup_auto.sh" | crontab - 2>/dev/null || true
    
    # Add new job
    (crontab -l 2>/dev/null; echo "$cron_job") | crontab -
    
    print_success "Cron job installed: every 6 hours (0:00, 6:00, 12:00, 18:00)"
    print_info "View logs: tail -f $LOG_FILE"
}

# Show status
show_status() {
    echo -e "${BLUE}=== Automatic Backup Status ===${NC}"
    echo ""
    echo "Configuration:"
    echo "  Remote Server: $BACKUP_SERVER_USER@$BACKUP_SERVER_HOST"
    echo "  Remote Path: $BACKUP_SERVER_PATH"
    echo "  SSH Key: $BACKUP_SSH_KEY"
    echo "  Retention: $BACKUP_RETENTION_DAYS days"
    echo ""
    
    # Check cron
    if crontab -l 2>/dev/null | grep -q "backup_auto.sh"; then
        echo -e "  Cron Status: ${GREEN}Active${NC}"
    else
        echo -e "  Cron Status: ${YELLOW}Not configured${NC}"
    fi
    
    # Test SSH
    if ssh -i "$BACKUP_SSH_KEY" -o ConnectTimeout=5 -o BatchMode=yes \
        "$BACKUP_SERVER_USER@$BACKUP_SERVER_HOST" "true" 2>/dev/null; then
        echo -e "  SSH Connection: ${GREEN}OK${NC}"
        
        # Show remote backups
        local count=$(ssh -i "$BACKUP_SSH_KEY" "$BACKUP_SERVER_USER@$BACKUP_SERVER_HOST" \
            "ls -1 $BACKUP_SERVER_PATH/ingest_auto_*.tar.gz 2>/dev/null | wc -l")
        echo "  Remote Backups: $count file(s)"
    else
        echo -e "  SSH Connection: ${RED}Failed${NC}"
    fi
    
    echo ""
}

# Main execution
main() {
    case "${1:-}" in
        --setup)
            validate_config
            test_ssh_connection || exit 1
            setup_cron
            ;;
        --status)
            show_status
            ;;
        --test)
            validate_config
            test_ssh_connection
            ;;
        --help|-h)
            echo "Usage: $0 [OPTION]"
            echo ""
            echo "Options:"
            echo "  (no option)  Run full backup and send to remote server"
            echo "  --setup      Setup cron job for automatic backup every 6 hours"
            echo "  --status     Show backup system status"
            echo "  --test       Test SSH connection to remote server"
            echo "  --help       Show this help"
            echo ""
            echo "Environment variables (in .env):"
            echo "  BACKUP_SERVER_HOST     Remote server hostname"
            echo "  BACKUP_SERVER_USER     SSH username (default: root)"
            echo "  BACKUP_SERVER_PATH     Remote backup directory"
            echo "  BACKUP_SSH_KEY         Path to SSH private key"
            echo "  BACKUP_RETENTION_DAYS  Days to keep backups (default: 30)"
            ;;
        *)
            # Run backup
            print_info "========== Starting Automatic Backup =========="
            
            validate_config
            test_ssh_connection || exit 1
            
            create_full_backup || exit 1
            send_to_remote "$BACKUP_FILE_PATH" || exit 1
            cleanup_remote_backups
            cleanup_local
            
            print_success "========== Automatic Backup Completed =========="
            ;;
    esac
}

main "$@"
