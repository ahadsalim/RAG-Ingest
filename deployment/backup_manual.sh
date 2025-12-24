#!/bin/bash

# =============================================================================
# Manual Backup & Restore Script
# Supports: Full backup (files + config + db) and Database-only backup
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
BACKUP_DIR="/opt/backups/ingest"
COMPOSE_FILE="$SCRIPT_DIR/docker-compose.ingest.yml"
ENV_FILE="$PROJECT_ROOT/.env"

# Ensure backup directory exists
mkdir -p "$BACKUP_DIR"

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

# =============================================================================
# BACKUP FUNCTIONS
# =============================================================================

# Database-only backup
backup_database() {
    local date=$(date +%Y%m%d_%H%M%S)
    local backup_name="ingest_db_${date}.sql.gz"
    local backup_path="$BACKUP_DIR/$backup_name"
    
    print_info "Creating database backup..."
    
    if docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T db \
        pg_dump -U "${POSTGRES_USER:-ingest}" "${POSTGRES_DB:-ingest}" | gzip > "$backup_path"; then
        
        # Create checksum
        sha256sum "$backup_path" > "${backup_path}.sha256"
        
        local size=$(du -sh "$backup_path" | cut -f1)
        print_success "Database backup created successfully"
        echo ""
        echo -e "${GREEN}📁 Backup file: $backup_path${NC}"
        echo -e "${GREEN}📦 Size: $size${NC}"
        return 0
    else
        print_error "Database backup failed"
        rm -f "$backup_path"
        return 1
    fi
}

# Full system backup
backup_full() {
    local date=$(date +%Y%m%d_%H%M%S)
    local backup_name="ingest_full_${date}"
    local backup_dir_temp="$BACKUP_DIR/${backup_name}"
    local backup_path="$BACKUP_DIR/${backup_name}.tar.gz"
    
    print_info "Creating full system backup..."
    mkdir -p "$backup_dir_temp"
    
    # 1. Database
    print_info "  [1/5] Backing up database..."
    if docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T db \
        pg_dump -U "${POSTGRES_USER:-ingest}" "${POSTGRES_DB:-ingest}" | gzip > "$backup_dir_temp/database.sql.gz"; then
        print_success "  Database backup done"
    else
        print_error "  Database backup failed"
        rm -rf "$backup_dir_temp"
        return 1
    fi
    
    # 2. MinIO data
    print_info "  [2/5] Backing up MinIO files..."
    local minio_volume=$(docker volume ls --format "{{.Name}}" | grep -E "minio_data$" | head -1)
    if [ -n "$minio_volume" ]; then
        if docker run --rm -v "$minio_volume:/data:ro" alpine tar -czf - /data > "$backup_dir_temp/minio_data.tar.gz" 2>/dev/null; then
            local minio_size=$(du -sh "$backup_dir_temp/minio_data.tar.gz" | cut -f1)
            print_success "  MinIO backup done ($minio_size)"
        else
            print_warning "  MinIO backup failed (continuing...)"
        fi
    else
        print_warning "  MinIO volume not found"
    fi
    
    # 3. Environment file
    print_info "  [3/5] Backing up configuration..."
    mkdir -p "$backup_dir_temp/config"
    if [ -f "$ENV_FILE" ]; then
        cp "$ENV_FILE" "$backup_dir_temp/config/.env"
        print_success "  .env file backed up"
    fi
    
    # 4. Nginx Proxy Manager data
    print_info "  [4/5] Backing up Nginx Proxy Manager..."
    local npm_volume=$(docker volume ls --format "{{.Name}}" | grep -E "npm_data$" | head -1)
    if [ -n "$npm_volume" ]; then
        if docker run --rm -v "$npm_volume:/data:ro" alpine tar -czf - /data > "$backup_dir_temp/npm_data.tar.gz" 2>/dev/null; then
            print_success "  NPM data backed up"
        else
            print_warning "  NPM backup failed (continuing...)"
        fi
    fi
    
    local npm_ssl_volume=$(docker volume ls --format "{{.Name}}" | grep -E "npm_letsencrypt$" | head -1)
    if [ -n "$npm_ssl_volume" ]; then
        if docker run --rm -v "$npm_ssl_volume:/data:ro" alpine tar -czf - /data > "$backup_dir_temp/npm_letsencrypt.tar.gz" 2>/dev/null; then
            print_success "  NPM SSL certificates backed up"
        else
            print_warning "  NPM SSL backup failed (continuing...)"
        fi
    fi
    
    # 5. Metadata
    print_info "  [5/5] Creating metadata..."
    cat > "$backup_dir_temp/backup_info.json" << EOF
{
    "backup_date": "$(date -Iseconds)",
    "backup_type": "full",
    "server_hostname": "$(hostname)",
    "git_commit": "$(cd "$PROJECT_ROOT" && git rev-parse HEAD 2>/dev/null || echo 'unknown')",
    "postgres_db": "${POSTGRES_DB:-ingest}",
    "backup_version": "2.0"
}
EOF
    
    # Compress everything
    print_info "Compressing backup..."
    cd "$BACKUP_DIR"
    tar -czf "${backup_name}.tar.gz" "${backup_name}/"
    rm -rf "${backup_name}/"
    
    # Create checksum
    sha256sum "${backup_name}.tar.gz" > "${backup_name}.tar.gz.sha256"
    
    local size=$(du -sh "$backup_path" | cut -f1)
    print_success "Full backup created successfully"
    echo ""
    echo -e "${GREEN}📁 Backup file: $backup_path${NC}"
    echo -e "${GREEN}📦 Size: $size${NC}"
}

# =============================================================================
# RESTORE FUNCTIONS
# =============================================================================

# Restore database only
restore_database() {
    local backup_file="$1"
    
    if [ ! -f "$backup_file" ]; then
        print_error "Backup file not found: $backup_file"
        return 1
    fi
    
    print_warning "This will REPLACE all database data!"
    read -p "Continue? (y/N): " confirm
    if [[ ! $confirm =~ ^[Yy]$ ]]; then
        print_info "Operation cancelled"
        return 0
    fi
    
    print_info "Restoring database from: $backup_file"
    
    # Stop services that use database
    print_info "Stopping web services..."
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" stop web worker beat 2>/dev/null || true
    sleep 3
    
    # Ensure database is running
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d db
    sleep 5
    
    # Terminate connections
    print_info "Terminating database connections..."
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T db \
        psql -U "${POSTGRES_USER:-ingest}" -d postgres -c \
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '${POSTGRES_DB:-ingest}' AND pid <> pg_backend_pid();" >/dev/null 2>&1 || true
    
    # Drop and recreate database
    print_info "Recreating database..."
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T db \
        psql -U "${POSTGRES_USER:-ingest}" -d postgres -c "DROP DATABASE IF EXISTS ${POSTGRES_DB:-ingest};" 2>/dev/null || true
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T db \
        psql -U "${POSTGRES_USER:-ingest}" -d postgres -c "CREATE DATABASE ${POSTGRES_DB:-ingest};"
    
    # Restore data
    print_info "Importing data..."
    if [[ "$backup_file" == *.gz ]]; then
        zcat "$backup_file" | docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T db \
            psql -U "${POSTGRES_USER:-ingest}" -d "${POSTGRES_DB:-ingest}" >/dev/null 2>&1
    else
        cat "$backup_file" | docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T db \
            psql -U "${POSTGRES_USER:-ingest}" -d "${POSTGRES_DB:-ingest}" >/dev/null 2>&1
    fi
    
    # Restart services
    print_info "Restarting services..."
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d
    sleep 10
    
    # Run migrations
    print_info "Syncing migrations..."
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T web \
        python manage.py migrate --fake-initial --noinput 2>/dev/null || true
    
    print_success "Database restored successfully"
}

# Restore full backup
restore_full() {
    local backup_file="$1"
    
    if [ ! -f "$backup_file" ]; then
        print_error "Backup file not found: $backup_file"
        return 1
    fi
    
    print_warning "This will REPLACE all data (database + MinIO files)!"
    read -p "Continue? (y/N): " confirm
    if [[ ! $confirm =~ ^[Yy]$ ]]; then
        print_info "Operation cancelled"
        return 0
    fi
    
    print_info "Restoring from: $backup_file"
    
    # Extract backup
    local temp_dir=$(mktemp -d)
    print_info "Extracting backup..."
    tar -xzf "$backup_file" -C "$temp_dir"
    
    # Find backup directory
    local backup_dir=$(find "$temp_dir" -maxdepth 2 -type d -name "ingest_*" | head -1)
    if [ -z "$backup_dir" ]; then
        backup_dir="$temp_dir"
    fi
    
    # Show backup info
    if [ -f "$backup_dir/backup_info.json" ]; then
        print_info "Backup information:"
        cat "$backup_dir/backup_info.json"
        echo ""
    fi
    
    # Stop all services
    print_info "Stopping services..."
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" stop 2>/dev/null || true
    sleep 5
    
    # Start only database
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d db
    sleep 5
    
    # Restore database
    if [ -f "$backup_dir/database.sql.gz" ]; then
        print_info "Restoring database..."
        
        docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T db \
            psql -U "${POSTGRES_USER:-ingest}" -d postgres -c \
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '${POSTGRES_DB:-ingest}' AND pid <> pg_backend_pid();" >/dev/null 2>&1 || true
        
        docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T db \
            psql -U "${POSTGRES_USER:-ingest}" -d postgres -c "DROP DATABASE IF EXISTS ${POSTGRES_DB:-ingest};" 2>/dev/null || true
        docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T db \
            psql -U "${POSTGRES_USER:-ingest}" -d postgres -c "CREATE DATABASE ${POSTGRES_DB:-ingest};"
        
        zcat "$backup_dir/database.sql.gz" | docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T db \
            psql -U "${POSTGRES_USER:-ingest}" -d "${POSTGRES_DB:-ingest}" >/dev/null 2>&1
        
        print_success "Database restored"
    fi
    
    # Restore MinIO
    if [ -f "$backup_dir/minio_data.tar.gz" ]; then
        print_info "Restoring MinIO files..."
        local minio_volume=$(docker volume ls --format "{{.Name}}" | grep -E "minio_data$" | head -1)
        if [ -n "$minio_volume" ]; then
            docker run --rm -v "$minio_volume:/data" alpine sh -c "rm -rf /data/* /data/.* 2>/dev/null || true"
            docker run --rm -v "$minio_volume:/data" -v "$backup_dir:/backup:ro" alpine \
                sh -c "cd /data && tar -xzf /backup/minio_data.tar.gz --strip-components=1 2>/dev/null || tar -xzf /backup/minio_data.tar.gz"
            docker run --rm -v "$minio_volume:/data" alpine sh -c "chown -R 1000:1000 /data 2>/dev/null || true"
            print_success "MinIO files restored"
        fi
    fi
    
    # Restore NPM data
    if [ -f "$backup_dir/npm_data.tar.gz" ]; then
        print_info "Restoring Nginx Proxy Manager..."
        local npm_volume=$(docker volume ls --format "{{.Name}}" | grep -E "npm_data$" | head -1)
        if [ -n "$npm_volume" ]; then
            docker run --rm -v "$npm_volume:/data" -v "$backup_dir:/backup:ro" alpine \
                sh -c "cd /data && tar -xzf /backup/npm_data.tar.gz --strip-components=1 2>/dev/null || true"
            print_success "NPM data restored"
        fi
    fi
    
    if [ -f "$backup_dir/npm_letsencrypt.tar.gz" ]; then
        local npm_ssl_volume=$(docker volume ls --format "{{.Name}}" | grep -E "npm_letsencrypt$" | head -1)
        if [ -n "$npm_ssl_volume" ]; then
            docker run --rm -v "$npm_ssl_volume:/data" -v "$backup_dir:/backup:ro" alpine \
                sh -c "cd /data && tar -xzf /backup/npm_letsencrypt.tar.gz --strip-components=1 2>/dev/null || true"
            print_success "NPM SSL certificates restored"
        fi
    fi
    
    # Cleanup
    rm -rf "$temp_dir"
    
    # Restart all services
    print_info "Restarting all services..."
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d
    sleep 15
    
    # Run migrations
    print_info "Syncing migrations..."
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T web \
        python manage.py migrate --fake-initial --noinput 2>/dev/null || true
    
    print_success "Full restore completed successfully"
}

# =============================================================================
# LIST BACKUPS
# =============================================================================

list_backups() {
    print_header "📋 Available Backups"
    echo ""
    
    if [ ! -d "$BACKUP_DIR" ] || [ -z "$(ls -A "$BACKUP_DIR" 2>/dev/null)" ]; then
        print_warning "No backups found in $BACKUP_DIR"
        return
    fi
    
    echo "Full Backups:"
    ls -lh "$BACKUP_DIR"/ingest_full_*.tar.gz 2>/dev/null | awk '{print "  " $9 " (" $5 ")"}' || echo "  None"
    echo ""
    
    echo "Database Backups:"
    ls -lh "$BACKUP_DIR"/ingest_db_*.sql.gz 2>/dev/null | awk '{print "  " $9 " (" $5 ")"}' || echo "  None"
    echo ""
    
    echo -e "📁 Backup directory: ${BLUE}$BACKUP_DIR${NC}"
}

# =============================================================================
# INTERACTIVE MENU
# =============================================================================

show_menu() {
    clear
    print_header "🗄️ Manual Backup & Restore"
    echo ""
    echo "BACKUP:"
    echo "  1) Full Backup (Database + MinIO + Config)"
    echo "  2) Database Only Backup"
    echo ""
    echo "RESTORE:"
    echo "  3) Restore Full Backup"
    echo "  4) Restore Database Only"
    echo ""
    echo "OTHER:"
    echo "  5) List Available Backups"
    echo "  0) Exit"
    echo ""
    read -p "Choose option (0-5): " choice
    
    case $choice in
        1)
            backup_full
            ;;
        2)
            backup_database
            ;;
        3)
            list_backups
            echo ""
            read -p "Enter full backup file path: " backup_path
            if [ -n "$backup_path" ]; then
                restore_full "$backup_path"
            fi
            ;;
        4)
            list_backups
            echo ""
            read -p "Enter database backup file path: " backup_path
            if [ -n "$backup_path" ]; then
                restore_database "$backup_path"
            fi
            ;;
        5)
            list_backups
            ;;
        0)
            print_info "Exiting..."
            exit 0
            ;;
        *)
            print_error "Invalid selection"
            ;;
    esac
    
    echo ""
    read -p "Press Enter to continue..."
    show_menu
}

# =============================================================================
# COMMAND LINE INTERFACE
# =============================================================================

show_help() {
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo ""
    echo "Commands:"
    echo "  backup full          Create full system backup"
    echo "  backup db            Create database-only backup"
    echo "  restore full <file>  Restore from full backup"
    echo "  restore db <file>    Restore database from backup"
    echo "  list                 List available backups"
    echo "  (no command)         Interactive menu"
    echo ""
    echo "Examples:"
    echo "  $0 backup full"
    echo "  $0 backup db"
    echo "  $0 restore db /opt/backups/ingest/ingest_db_20241224.sql.gz"
    echo "  $0 restore full /opt/backups/ingest/ingest_full_20241224.tar.gz"
    echo ""
    echo "Backup directory: $BACKUP_DIR"
}

# Main
main() {
    case "${1:-}" in
        backup)
            case "${2:-}" in
                full) backup_full ;;
                db|database) backup_database ;;
                *) show_help ;;
            esac
            ;;
        restore)
            case "${2:-}" in
                full)
                    if [ -n "${3:-}" ]; then
                        restore_full "$3"
                    else
                        print_error "Please specify backup file path"
                        echo "Usage: $0 restore full <backup_file>"
                    fi
                    ;;
                db|database)
                    if [ -n "${3:-}" ]; then
                        restore_database "$3"
                    else
                        print_error "Please specify backup file path"
                        echo "Usage: $0 restore db <backup_file>"
                    fi
                    ;;
                *) show_help ;;
            esac
            ;;
        list)
            list_backups
            ;;
        --help|-h|help)
            show_help
            ;;
        "")
            show_menu
            ;;
        *)
            show_help
            ;;
    esac
}

main "$@"
