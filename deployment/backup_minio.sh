#!/bin/bash

# =============================================================================
# MinIO Backup & Restore Script
# Independent backup system for MinIO object storage
# =============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m'

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Load environment variables
if [ -f "$PROJECT_ROOT/.env" ]; then
    source "$PROJECT_ROOT/.env"
elif [ -f "/srv/.env" ]; then
    source "/srv/.env"
fi

# Configuration
LOCAL_BACKUP_DIR="/opt/backups/minio"
COMPOSE_FILE="$SCRIPT_DIR/docker-compose.ingest.yml"
ENV_FILE="$PROJECT_ROOT/.env"
LOG_FILE="/var/log/minio_backup.log"

# Remote backup settings (from .env)
BACKUP_SERVER_HOST="${BACKUP_SERVER_HOST:-}"
BACKUP_SERVER_USER="${BACKUP_SERVER_USER:-root}"
BACKUP_SERVER_PATH="${BACKUP_SERVER_PATH:-/srv/backup/ingest}"
BACKUP_SSH_KEY="${BACKUP_SSH_KEY:-/root/.ssh/backup_key}"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"

# MinIO remote path (separate from database backups)
MINIO_REMOTE_PATH="${BACKUP_SERVER_PATH}/minio"

# Ensure directories exist
mkdir -p "$LOCAL_BACKUP_DIR"

# Helper functions
print_header() {
    echo -e "${PURPLE}================================${NC}"
    echo -e "${PURPLE}$1${NC}"
    echo -e "${PURPLE}================================${NC}"
}

print_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
print_success() { echo -e "${GREEN}✅ $1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
print_error() { echo -e "${RED}❌ $1${NC}"; }

log() {
    local level="$1"
    local message="$2"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$timestamp] [$level] $message" | tee -a "$LOG_FILE"
}

# Get MinIO volume name
get_minio_volume() {
    local volume=$(docker volume ls --format "{{.Name}}" | grep -E "minio_data$" | head -1)
    if [ -z "$volume" ]; then
        volume="deployment_minio_data"
    fi
    echo "$volume"
}

# =============================================================================
# BACKUP FUNCTIONS
# =============================================================================

# Create MinIO backup
create_backup() {
    local date=$(date +%Y%m%d_%H%M%S)
    local backup_name="minio_backup_${date}.tar.gz"
    local backup_path="$LOCAL_BACKUP_DIR/$backup_name"
    
    print_info "Creating MinIO backup..."
    
    local volume=$(get_minio_volume)
    print_info "Using volume: $volume"
    
    # Check if volume exists
    if ! docker volume inspect "$volume" >/dev/null 2>&1; then
        print_error "MinIO volume not found: $volume"
        return 1
    fi
    
    # Get volume size estimate
    local size_estimate=$(docker run --rm -v "$volume:/data:ro" alpine du -sh /data 2>/dev/null | cut -f1)
    print_info "Estimated data size: $size_estimate"
    
    # Create backup
    if docker run --rm -v "$volume:/data:ro" alpine tar -czf - /data > "$backup_path" 2>/dev/null; then
        # Verify backup is not empty
        local backup_size=$(stat -c%s "$backup_path" 2>/dev/null || echo 0)
        if [ "$backup_size" -lt 100 ]; then
            print_warning "Backup file is very small - MinIO might be empty"
        fi
        
        # Create checksum
        sha256sum "$backup_path" > "${backup_path}.sha256"
        
        local size=$(du -sh "$backup_path" | cut -f1)
        print_success "MinIO backup created successfully"
        echo ""
        echo -e "${GREEN}📁 Backup file: $backup_path${NC}"
        echo -e "${GREEN}📦 Size: $size${NC}"
        
        echo "$backup_path"
        return 0
    else
        print_error "MinIO backup failed"
        rm -f "$backup_path"
        return 1
    fi
}

# Send backup to remote server
send_to_remote() {
    local backup_file="$1"
    
    if [ -z "$BACKUP_SERVER_HOST" ]; then
        print_error "BACKUP_SERVER_HOST not configured in .env"
        return 1
    fi
    
    if [ ! -f "$BACKUP_SSH_KEY" ]; then
        print_error "SSH key not found: $BACKUP_SSH_KEY"
        return 1
    fi
    
    print_info "Sending backup to remote server..."
    
    # Ensure remote directory exists
    ssh -i "$BACKUP_SSH_KEY" "$BACKUP_SERVER_USER@$BACKUP_SERVER_HOST" \
        "mkdir -p $MINIO_REMOTE_PATH"
    
    # Send backup
    if scp -i "$BACKUP_SSH_KEY" "$backup_file" "${backup_file}.sha256" \
        "$BACKUP_SERVER_USER@$BACKUP_SERVER_HOST:$MINIO_REMOTE_PATH/"; then
        print_success "Backup sent to $BACKUP_SERVER_HOST:$MINIO_REMOTE_PATH/"
        return 0
    else
        print_error "Failed to send backup to remote server"
        return 1
    fi
}

# Cleanup old backups
cleanup_old_backups() {
    local days="${1:-$BACKUP_RETENTION_DAYS}"
    
    print_info "Cleaning up backups older than $days days..."
    
    # Local cleanup
    local local_count=$(find "$LOCAL_BACKUP_DIR" -name "minio_backup_*.tar.gz" -mtime +$days 2>/dev/null | wc -l)
    if [ "$local_count" -gt 0 ]; then
        find "$LOCAL_BACKUP_DIR" -name "minio_backup_*.tar.gz*" -mtime +$days -delete
        print_info "Deleted $local_count old local backup(s)"
    fi
    
    # Remote cleanup
    if [ -n "$BACKUP_SERVER_HOST" ] && [ -f "$BACKUP_SSH_KEY" ]; then
        ssh -i "$BACKUP_SSH_KEY" "$BACKUP_SERVER_USER@$BACKUP_SERVER_HOST" \
            "find $MINIO_REMOTE_PATH -name 'minio_backup_*.tar.gz*' -mtime +$days -delete 2>/dev/null || true"
        print_info "Remote cleanup completed"
    fi
}

# =============================================================================
# RESTORE FUNCTIONS
# =============================================================================

# Restore from local file
restore_local() {
    local backup_file="$1"
    
    if [ ! -f "$backup_file" ]; then
        print_error "Backup file not found: $backup_file"
        return 1
    fi
    
    print_warning "This will REPLACE all MinIO data!"
    read -p "Continue? (y/N): " confirm
    if [[ ! $confirm =~ ^[Yy]$ ]]; then
        print_info "Operation cancelled"
        return 0
    fi
    
    print_info "Restoring MinIO from: $backup_file"
    
    local volume=$(get_minio_volume)
    
    # Stop MinIO
    print_info "Stopping MinIO..."
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" stop minio 2>/dev/null || true
    sleep 3
    
    # Clear existing data
    print_info "Clearing existing data..."
    docker run --rm -v "$volume:/data" alpine sh -c "rm -rf /data/* /data/.* 2>/dev/null || true"
    
    # Restore data
    print_info "Restoring data..."
    if docker run --rm -v "$volume:/data" -v "$(dirname "$backup_file"):/backup:ro" alpine \
        sh -c "cd /data && tar -xzf /backup/$(basename "$backup_file") --strip-components=1 2>/dev/null || tar -xzf /backup/$(basename "$backup_file")"; then
        
        # Fix permissions
        docker run --rm -v "$volume:/data" alpine sh -c "chown -R 1000:1000 /data 2>/dev/null || true"
        
        print_success "Data restored"
    else
        print_error "Failed to restore data"
    fi
    
    # Start MinIO
    print_info "Starting MinIO..."
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" start minio
    sleep 5
    
    # Verify
    if docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T minio curl -sf http://127.0.0.1:9000/minio/health/live >/dev/null 2>&1; then
        print_success "MinIO is healthy"
    else
        print_warning "MinIO health check failed - please verify manually"
    fi
    
    print_success "MinIO restore completed"
}

# Restore from remote server
restore_remote() {
    if [ -z "$BACKUP_SERVER_HOST" ]; then
        print_error "BACKUP_SERVER_HOST not configured"
        return 1
    fi
    
    print_info "Fetching backup list from remote server..."
    
    # List remote backups
    local backups=$(ssh -i "$BACKUP_SSH_KEY" "$BACKUP_SERVER_USER@$BACKUP_SERVER_HOST" \
        "ls -t $MINIO_REMOTE_PATH/minio_backup_*.tar.gz 2>/dev/null" | head -10)
    
    if [ -z "$backups" ]; then
        print_error "No backups found on remote server"
        return 1
    fi
    
    echo ""
    echo "Available remote backups:"
    local index=1
    while IFS= read -r backup; do
        local size=$(ssh -i "$BACKUP_SSH_KEY" "$BACKUP_SERVER_USER@$BACKUP_SERVER_HOST" \
            "du -sh '$backup' 2>/dev/null | cut -f1")
        echo "  $index) $(basename "$backup") ($size)"
        index=$((index + 1))
    done <<< "$backups"
    
    echo ""
    read -p "Select backup number to restore (or 0 to cancel): " selection
    
    if [ "$selection" == "0" ]; then
        print_info "Operation cancelled"
        return 0
    fi
    
    local selected_backup=$(echo "$backups" | sed -n "${selection}p")
    if [ -z "$selected_backup" ]; then
        print_error "Invalid selection"
        return 1
    fi
    
    print_info "Downloading backup..."
    local temp_file="/tmp/$(basename "$selected_backup")"
    
    if scp -i "$BACKUP_SSH_KEY" "$BACKUP_SERVER_USER@$BACKUP_SERVER_HOST:$selected_backup" "$temp_file"; then
        restore_local "$temp_file"
        rm -f "$temp_file"
    else
        print_error "Failed to download backup"
        return 1
    fi
}

# =============================================================================
# AUTO BACKUP (for cron)
# =============================================================================

auto_backup() {
    log "INFO" "========== Starting MinIO Auto Backup =========="
    
    # Create backup
    local backup_file=$(create_backup)
    if [ $? -ne 0 ]; then
        log "ERROR" "Backup creation failed"
        exit 1
    fi
    
    # Send to remote if configured
    if [ -n "$BACKUP_SERVER_HOST" ] && [ -f "$BACKUP_SSH_KEY" ]; then
        send_to_remote "$backup_file"
    fi
    
    # Cleanup old backups
    cleanup_old_backups
    
    # Optionally remove local backup after sending to remote
    if [ "${BACKUP_KEEP_LOCAL:-true}" != "true" ] && [ -n "$BACKUP_SERVER_HOST" ]; then
        rm -f "$backup_file" "${backup_file}.sha256"
        log "INFO" "Local backup removed (BACKUP_KEEP_LOCAL=false)"
    fi
    
    log "INFO" "========== MinIO Auto Backup Completed =========="
}

# Setup cron job
setup_cron() {
    print_info "Setting up cron job for automatic MinIO backup..."
    
    # Run daily at 3:00 AM (offset from database backup)
    local cron_job="0 3 * * * $SCRIPT_DIR/backup_minio.sh --auto >> $LOG_FILE 2>&1"
    
    # Remove existing job
    crontab -l 2>/dev/null | grep -v "backup_minio.sh" | crontab - 2>/dev/null || true
    
    # Add new job
    (crontab -l 2>/dev/null; echo "$cron_job") | crontab -
    
    print_success "Cron job installed: daily at 3:00 AM"
    print_info "View logs: tail -f $LOG_FILE"
}

# =============================================================================
# STATUS & LIST
# =============================================================================

show_status() {
    print_header "📊 MinIO Backup Status"
    echo ""
    
    local volume=$(get_minio_volume)
    echo "Configuration:"
    echo "  MinIO Volume: $volume"
    echo "  Local Backup Dir: $LOCAL_BACKUP_DIR"
    echo "  Remote Server: ${BACKUP_SERVER_HOST:-Not configured}"
    echo "  Remote Path: $MINIO_REMOTE_PATH"
    echo ""
    
    # Check MinIO health
    if docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T minio curl -sf http://127.0.0.1:9000/minio/health/live >/dev/null 2>&1; then
        echo -e "  MinIO Status: ${GREEN}Healthy${NC}"
    else
        echo -e "  MinIO Status: ${RED}Not running${NC}"
    fi
    
    # Check cron
    if crontab -l 2>/dev/null | grep -q "backup_minio.sh"; then
        echo -e "  Auto Backup: ${GREEN}Enabled${NC}"
    else
        echo -e "  Auto Backup: ${YELLOW}Disabled${NC}"
    fi
    
    # Volume size
    local vol_size=$(docker run --rm -v "$volume:/data:ro" alpine du -sh /data 2>/dev/null | cut -f1)
    echo "  Current Data Size: $vol_size"
    
    # Local backups
    local local_count=$(ls -1 "$LOCAL_BACKUP_DIR"/minio_backup_*.tar.gz 2>/dev/null | wc -l)
    echo "  Local Backups: $local_count"
    
    # Remote backups
    if [ -n "$BACKUP_SERVER_HOST" ] && [ -f "$BACKUP_SSH_KEY" ]; then
        local remote_count=$(ssh -i "$BACKUP_SSH_KEY" -o ConnectTimeout=5 "$BACKUP_SERVER_USER@$BACKUP_SERVER_HOST" \
            "ls -1 $MINIO_REMOTE_PATH/minio_backup_*.tar.gz 2>/dev/null | wc -l" 2>/dev/null || echo "N/A")
        echo "  Remote Backups: $remote_count"
    fi
    
    echo ""
}

list_backups() {
    print_header "📋 MinIO Backups"
    echo ""
    
    echo "Local Backups ($LOCAL_BACKUP_DIR):"
    if ls "$LOCAL_BACKUP_DIR"/minio_backup_*.tar.gz >/dev/null 2>&1; then
        ls -lh "$LOCAL_BACKUP_DIR"/minio_backup_*.tar.gz | awk '{print "  " $9 " (" $5 ")"}'
    else
        echo "  None"
    fi
    
    echo ""
    
    if [ -n "$BACKUP_SERVER_HOST" ] && [ -f "$BACKUP_SSH_KEY" ]; then
        echo "Remote Backups ($BACKUP_SERVER_HOST:$MINIO_REMOTE_PATH):"
        ssh -i "$BACKUP_SSH_KEY" -o ConnectTimeout=5 "$BACKUP_SERVER_USER@$BACKUP_SERVER_HOST" \
            "ls -lh $MINIO_REMOTE_PATH/minio_backup_*.tar.gz 2>/dev/null | awk '{print \"  \" \$9 \" (\" \$5 \")\"}'" 2>/dev/null || echo "  Unable to connect"
    fi
    
    echo ""
}

# =============================================================================
# MAIN
# =============================================================================

show_help() {
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  backup              Create MinIO backup (local)"
    echo "  backup --remote     Create backup and send to remote server"
    echo "  restore <file>      Restore from local backup file"
    echo "  restore --remote    Restore from remote server (interactive)"
    echo "  list                List available backups"
    echo "  status              Show backup system status"
    echo "  setup               Setup automatic daily backup (cron)"
    echo "  cleanup [days]      Remove backups older than N days"
    echo "  --auto              Run automatic backup (for cron)"
    echo ""
    echo "Examples:"
    echo "  $0 backup"
    echo "  $0 backup --remote"
    echo "  $0 restore /opt/backups/minio/minio_backup_20241224.tar.gz"
    echo "  $0 restore --remote"
    echo ""
}

main() {
    case "${1:-}" in
        backup)
            backup_file=$(create_backup)
            if [ "${2:-}" == "--remote" ] && [ $? -eq 0 ]; then
                send_to_remote "$backup_file"
            fi
            ;;
        restore)
            if [ "${2:-}" == "--remote" ]; then
                restore_remote
            elif [ -n "${2:-}" ]; then
                restore_local "$2"
            else
                print_error "Please specify backup file or --remote"
                echo "Usage: $0 restore <file> OR $0 restore --remote"
            fi
            ;;
        list)
            list_backups
            ;;
        status)
            show_status
            ;;
        setup)
            setup_cron
            ;;
        cleanup)
            cleanup_old_backups "${2:-$BACKUP_RETENTION_DAYS}"
            ;;
        --auto)
            auto_backup
            ;;
        --help|-h|help|"")
            show_help
            ;;
        *)
            show_help
            ;;
    esac
}

main "$@"
