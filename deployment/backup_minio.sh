#!/bin/bash

# =============================================================================
# MinIO Backup & Restore Script (External MinIO Server)
# Uses mc (MinIO Client) to backup from external MinIO server via S3 API
# Note: Excludes temp-userfile bucket (temporary user files)
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
LOG_FILE="/var/log/minio_backup.log"
MC_ALIAS="ingest-minio"

# MinIO connection (from .env)
MINIO_ENDPOINT="${AWS_S3_ENDPOINT_URL:-}"
MINIO_ACCESS_KEY="${AWS_ACCESS_KEY_ID:-}"
MINIO_SECRET_KEY="${AWS_SECRET_ACCESS_KEY:-}"
MINIO_BUCKET="${AWS_STORAGE_BUCKET_NAME:-ingest-system}"

# Remote backup settings (from .env)
BACKUP_SERVER_HOST="${BACKUP_SERVER_HOST:-}"
BACKUP_SERVER_USER="${BACKUP_SERVER_USER:-root}"
BACKUP_SERVER_PATH_MINIO="${BACKUP_SERVER_PATH_MINIO:-/srv/backup/minio}"
BACKUP_SSH_KEY="${BACKUP_SSH_KEY:-/root/.ssh/backup_key}"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"

# Buckets to exclude from backup (temporary files)
EXCLUDED_BUCKETS="temp-userfile"

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

# Check mc is installed, install if needed
ensure_mc() {
    if ! command -v mc &>/dev/null; then
        print_info "Installing MinIO Client (mc)..."
        curl -sSL https://dl.min.io/client/mc/release/linux-amd64/mc -o /usr/local/bin/mc
        chmod +x /usr/local/bin/mc
    fi
}

# Configure mc alias
configure_mc() {
    if [ -z "$MINIO_ENDPOINT" ]; then
        print_error "AWS_S3_ENDPOINT_URL not set in .env"
        return 1
    fi
    mc alias set "$MC_ALIAS" "$MINIO_ENDPOINT" "$MINIO_ACCESS_KEY" "$MINIO_SECRET_KEY" --api s3v4 2>/dev/null
}

# =============================================================================
# BACKUP FUNCTIONS
# =============================================================================

create_backup() {
    local date=$(date +%Y%m%d_%H%M%S)
    local backup_name="minio_backup_${date}"
    local backup_dir="$LOCAL_BACKUP_DIR/$backup_name"
    local backup_path="$LOCAL_BACKUP_DIR/${backup_name}.tar.gz"
    
    print_info "Creating MinIO backup from external server..." >&2
    print_info "Endpoint: $MINIO_ENDPOINT" >&2
    print_info "Excluding buckets: $EXCLUDED_BUCKETS" >&2
    
    ensure_mc
    configure_mc || return 1
    
    # Create temp directory
    mkdir -p "$backup_dir"
    
    # List buckets and mirror each (excluding temp buckets)
    local buckets=$(mc ls "$MC_ALIAS/" --json 2>/dev/null | python3 -c "
import sys, json
for line in sys.stdin:
    try:
        obj = json.loads(line)
        if obj.get('type') == 'folder':
            print(obj['key'].rstrip('/'))
    except: pass
" 2>/dev/null)
    
    if [ -z "$buckets" ]; then
        print_warning "No buckets found or unable to list buckets" >&2
        rm -rf "$backup_dir"
        return 1
    fi
    
    for bucket in $buckets; do
        # Check if excluded
        local skip=false
        for excl in $EXCLUDED_BUCKETS; do
            if [ "$bucket" = "$excl" ]; then
                skip=true
                break
            fi
        done
        
        if [ "$skip" = true ]; then
            print_info "Skipping excluded bucket: $bucket" >&2
            continue
        fi
        
        print_info "Mirroring bucket: $bucket" >&2
        mc mirror --quiet "$MC_ALIAS/$bucket" "$backup_dir/$bucket" 2>/dev/null || {
            print_warning "Failed to mirror bucket: $bucket" >&2
        }
    done
    
    # Create tar.gz
    if tar -czf "$backup_path" -C "$LOCAL_BACKUP_DIR" "$backup_name" 2>/dev/null; then
        # Create checksum
        sha256sum "$backup_path" > "${backup_path}.sha256"
        
        local size=$(du -sh "$backup_path" | cut -f1)
        print_success "MinIO backup created successfully" >&2
        echo -e "${GREEN}📁 Backup file: $backup_path${NC}" >&2
        echo -e "${GREEN}📦 Size: $size${NC}" >&2
        
        # Cleanup temp directory
        rm -rf "$backup_dir"
        
        echo "$backup_path"
        return 0
    else
        print_error "MinIO backup failed" >&2
        rm -rf "$backup_dir" "$backup_path"
        return 1
    fi
}

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
    
    ssh -i "$BACKUP_SSH_KEY" "$BACKUP_SERVER_USER@$BACKUP_SERVER_HOST" \
        "mkdir -p $BACKUP_SERVER_PATH_MINIO"
    
    if scp -i "$BACKUP_SSH_KEY" "$backup_file" "${backup_file}.sha256" \
        "$BACKUP_SERVER_USER@$BACKUP_SERVER_HOST:$BACKUP_SERVER_PATH_MINIO/"; then
        print_success "Backup sent to $BACKUP_SERVER_HOST:$BACKUP_SERVER_PATH_MINIO/"
        return 0
    else
        print_error "Failed to send backup to remote server"
        return 1
    fi
}

cleanup_old_backups() {
    local days="${1:-$BACKUP_RETENTION_DAYS}"
    
    print_info "Cleaning up backups older than $days days..."
    
    local local_count=$(find "$LOCAL_BACKUP_DIR" -name "minio_backup_*.tar.gz" -mtime +$days 2>/dev/null | wc -l)
    if [ "$local_count" -gt 0 ]; then
        find "$LOCAL_BACKUP_DIR" -name "minio_backup_*.tar.gz*" -mtime +$days -delete
        print_info "Deleted $local_count old local backup(s)"
    fi
    
    if [ -n "$BACKUP_SERVER_HOST" ] && [ -f "$BACKUP_SSH_KEY" ]; then
        ssh -i "$BACKUP_SSH_KEY" "$BACKUP_SERVER_USER@$BACKUP_SERVER_HOST" \
            "find $BACKUP_SERVER_PATH_MINIO -name 'minio_backup_*.tar.gz*' -mtime +$days -delete 2>/dev/null || true"
        print_info "Remote cleanup completed"
    fi
}

# =============================================================================
# RESTORE FUNCTIONS
# =============================================================================

restore_local() {
    local backup_file="$1"
    
    if [ ! -f "$backup_file" ]; then
        print_error "Backup file not found: $backup_file"
        return 1
    fi
    
    print_warning "This will upload backup data to external MinIO: $MINIO_ENDPOINT"
    read -p "Continue? (y/N): " confirm
    if [[ ! $confirm =~ ^[Yy]$ ]]; then
        print_info "Operation cancelled"
        return 0
    fi
    
    ensure_mc
    configure_mc || return 1
    
    print_info "Restoring MinIO from: $backup_file"
    
    local temp_dir="/tmp/minio_restore_$$"
    mkdir -p "$temp_dir"
    
    # Extract backup
    print_info "Extracting backup..."
    tar -xzf "$backup_file" -C "$temp_dir"
    
    # Find the extracted directory
    local data_dir=$(find "$temp_dir" -maxdepth 1 -type d ! -name "$(basename "$temp_dir")" | head -1)
    if [ -z "$data_dir" ]; then
        data_dir="$temp_dir"
    fi
    
    # Upload each bucket
    for bucket_dir in "$data_dir"/*/; do
        local bucket=$(basename "$bucket_dir")
        print_info "Restoring bucket: $bucket"
        
        # Create bucket if not exists
        mc mb -p "$MC_ALIAS/$bucket" 2>/dev/null || true
        
        # Mirror data back
        mc mirror --overwrite --quiet "$bucket_dir" "$MC_ALIAS/$bucket" 2>/dev/null || {
            print_warning "Failed to restore bucket: $bucket"
        }
    done
    
    # Cleanup
    rm -rf "$temp_dir"
    
    print_success "MinIO restore completed"
}

# =============================================================================
# AUTO BACKUP (for cron)
# =============================================================================

auto_backup() {
    log "INFO" "========== Starting MinIO Auto Backup (External) =========="
    
    local backup_file=$(create_backup)
    if [ $? -ne 0 ]; then
        log "ERROR" "Backup creation failed"
        exit 1
    fi
    
    if [ -n "$BACKUP_SERVER_HOST" ] && [ -f "$BACKUP_SSH_KEY" ]; then
        send_to_remote "$backup_file"
    fi
    
    cleanup_old_backups
    
    if [ "${BACKUP_KEEP_LOCAL:-true}" != "true" ] && [ -n "$BACKUP_SERVER_HOST" ]; then
        rm -f "$backup_file" "${backup_file}.sha256"
        log "INFO" "Local backup removed (BACKUP_KEEP_LOCAL=false)"
    fi
    
    log "INFO" "========== MinIO Auto Backup Completed =========="
}

# =============================================================================
# STATUS & LIST
# =============================================================================

show_status() {
    print_header "📊 MinIO Backup Status"
    echo ""
    
    echo "Configuration:"
    echo "  MinIO Endpoint: ${MINIO_ENDPOINT:-Not configured}"
    echo "  Bucket: $MINIO_BUCKET"
    echo "  Local Backup Dir: $LOCAL_BACKUP_DIR"
    echo "  Remote Server: ${BACKUP_SERVER_HOST:-Not configured}"
    echo ""
    
    # Check MinIO health
    ensure_mc 2>/dev/null
    if configure_mc 2>/dev/null && mc ls "$MC_ALIAS/" >/dev/null 2>&1; then
        echo -e "  MinIO Status: ${GREEN}Reachable${NC}"
    else
        echo -e "  MinIO Status: ${RED}Unreachable${NC}"
    fi
    
    # Local backups
    local local_count=$(ls -1 "$LOCAL_BACKUP_DIR"/minio_backup_*.tar.gz 2>/dev/null | wc -l)
    echo "  Local Backups: $local_count"
    echo "  Excluded Buckets: $EXCLUDED_BUCKETS"
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
        echo "Remote Backups ($BACKUP_SERVER_HOST:$BACKUP_SERVER_PATH_MINIO):"
        ssh -i "$BACKUP_SSH_KEY" -o ConnectTimeout=5 "$BACKUP_SERVER_USER@$BACKUP_SERVER_HOST" \
            "ls -lh $BACKUP_SERVER_PATH_MINIO/minio_backup_*.tar.gz 2>/dev/null | awk '{print \"  \" \$9 \" (\" \$5 \")\"}'" 2>/dev/null || echo "  Unable to connect"
    fi
    
    echo ""
}

# =============================================================================
# MAIN
# =============================================================================

show_help() {
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "MinIO Backup for External Server ($MINIO_ENDPOINT)"
    echo ""
    echo "Commands:"
    echo "  backup              Create MinIO backup (local)"
    echo "  backup --remote     Create backup and send to remote server"
    echo "  restore <file>      Restore from local backup file"
    echo "  list                List available backups"
    echo "  status              Show backup system status"
    echo "  cleanup [days]      Remove backups older than N days"
    echo "  --auto              Run automatic backup (for cron)"
    echo ""
}

main() {
    case "${1:-}" in
        backup)
            backup_file=$(create_backup)
            backup_result=$?
            if [ $backup_result -eq 0 ] && [ "${2:-}" == "--remote" ]; then
                send_to_remote "$backup_file"
            fi
            ;;
        restore)
            if [ -n "${2:-}" ]; then
                restore_local "$2"
            else
                print_error "Please specify backup file"
                echo "Usage: $0 restore <file>"
            fi
            ;;
        list)
            list_backups
            ;;
        status)
            show_status
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
