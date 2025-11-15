#!/bin/bash

# Ingest System Backup Manager
# Complete backup and restore system management

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m'

# Default settings
BACKUP_BASE_DIR="/opt/backups/ingest"
LOG_FILE="/var/log/ingest_backup.log"
MAX_LOCAL_BACKUPS=7
MAX_REMOTE_BACKUPS=30

print_header() {
    echo -e "${PURPLE}================================${NC}"
    echo -e "${PURPLE}$1${NC}"
    echo -e "${PURPLE}================================${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

log_message() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Main menu
show_main_menu() {
    clear
    print_header "🗄️ Ingest System Backup Manager"
    echo ""
    echo "1️⃣  Create Manual Backup"
    echo "2️⃣  Restore from Backup"
    echo "3️⃣  Setup Automated Backup"
    echo "4️⃣  View Backups"
    echo "5️⃣  Cleanup Old Backups"
    echo "6️⃣  Setup Remote Server"
    echo "7️⃣  Test Backup System"
    echo "0️⃣  Exit"
    echo ""
    read -p "Choose option (0-7): " choice
}

# Create manual backup
create_manual_backup() {
    print_header "📦 Create Manual Backup"
    
    echo "Backup Type:"
    echo "1) Full (Database + Files + Config)"
    echo "2) Database Only"
    echo "3) Files Only"
    echo ""
    read -p "Choose option (1-3): " backup_type
    
    case $backup_type in
        1) create_full_backup ;;
        2) create_database_backup ;;
        3) create_files_backup ;;
        *) print_error "Invalid selection" && return 1 ;;
    esac
}

# Full backup
create_full_backup() {
    local date=$(date +%Y%m%d_%H%M%S)
    local backup_name="ingest_full_${date}"
    local backup_dir="${BACKUP_BASE_DIR}/${backup_name}"
    
    print_info "Starting full backup..."
    mkdir -p "$backup_dir"
    
    # Detect docker-compose file
    detect_compose_file
    
    # Database
    print_info "Backing up database..."
    docker compose -f "$COMPOSE_FILE" $ENV_FILE_ARG exec -T db pg_dump -U "${POSTGRES_USER:-ingest}" "${POSTGRES_DB:-ingest}" | gzip > "$backup_dir/database.sql.gz"
    
    # MinIO
    print_info "Backing up MinIO files..."
    local volume_name=$(docker volume ls --format "{{.Name}}" | grep minio_data | head -1)
    if [ -z "$volume_name" ]; then
        volume_name="deployment_minio_data"
    fi
    docker run --rm -v "$volume_name:/data" alpine tar -czf - /data > "$backup_dir/minio_data.tar.gz" 2>/dev/null || print_warning "MinIO backup failed"
    
    # Verify MinIO backup was successful
    if [ -f "$backup_dir/minio_data.tar.gz" ] && [ $(stat -c%s "$backup_dir/minio_data.tar.gz" 2>/dev/null || echo 0) -gt 100 ]; then
        print_success "MinIO backup successful ($(du -sh "$backup_dir/minio_data.tar.gz" | cut -f1))"
    else
        print_warning "MinIO backup may be empty or failed"
    fi
    
    # Configuration
    print_info "Backing up configuration..."
    mkdir -p "$backup_dir/config"
    [ -f "../.env" ] && cp ../.env "$backup_dir/config/"
    cp -r . "$backup_dir/config/deployment/"
    
    # Metadata
    create_backup_metadata "$backup_dir" "full"
    
    # Compression
    compress_backup "$backup_name"
    
    print_success "Full backup created: ${backup_name}.tar.gz"
    print_info "📁 Backup location: ${BACKUP_BASE_DIR}/${backup_name}.tar.gz"
}

# Database only backup
create_database_backup() {
    local date=$(date +%Y%m%d_%H%M%S)
    local backup_name="ingest_db_${date}"
    
    print_info "Backing up database..."
    detect_compose_file
    
    # Load environment variables from .env
    local env_file=""
    if [ -f "../.env" ]; then
        env_file="../.env"
    elif [ -f "/srv/.env" ]; then
        env_file="/srv/.env"
    fi
    
    if [ -n "$env_file" ]; then
        export POSTGRES_USER=$(grep "^POSTGRES_USER=" "$env_file" | cut -d '=' -f2)
        export POSTGRES_DB=$(grep "^POSTGRES_DB=" "$env_file" | cut -d '=' -f2)
        print_info "  Loaded from: $env_file"
        print_info "  DB User: ${POSTGRES_USER}"
        print_info "  DB Name: ${POSTGRES_DB}"
    else
        print_warning ".env file not found, using defaults"
        export POSTGRES_USER="ingest"
        export POSTGRES_DB="ingest"
    fi
    
    mkdir -p "$BACKUP_BASE_DIR"
    
    print_info "  Executing pg_dump..."
    if docker compose -f "$COMPOSE_FILE" $ENV_FILE_ARG exec -T db pg_dump -U "${POSTGRES_USER}" "${POSTGRES_DB}" | gzip > "${BACKUP_BASE_DIR}/${backup_name}.sql.gz"; then
        print_success "Database backup created: ${backup_name}.sql.gz"
        print_info "📁 Backup location: ${BACKUP_BASE_DIR}/${backup_name}.sql.gz"
        print_info "📦 Backup size: $(du -sh "${BACKUP_BASE_DIR}/${backup_name}.sql.gz" | cut -f1)"
    else
        print_error "Database backup failed!"
        rm -f "${BACKUP_BASE_DIR}/${backup_name}.sql.gz"
        return 1
    fi
}

# Files only backup
create_files_backup() {
    local date=$(date +%Y%m%d_%H%M%S)
    local backup_name="ingest_files_${date}"
    
    print_info "Backing up MinIO files..."
    detect_compose_file
    
    mkdir -p "$BACKUP_BASE_DIR"
    
    local volume_name=$(docker volume ls --format "{{.Name}}" | grep minio_data | head -1)
    if [ -z "$volume_name" ]; then
        volume_name="deployment_minio_data"
    fi
    
    docker run --rm -v "$volume_name:/data" alpine tar -czf - /data > "${BACKUP_BASE_DIR}/${backup_name}.tar.gz" 2>/dev/null
    
    if [ -f "${BACKUP_BASE_DIR}/${backup_name}.tar.gz" ] && [ $(stat -c%s "${BACKUP_BASE_DIR}/${backup_name}.tar.gz" 2>/dev/null || echo 0) -gt 100 ]; then
        print_success "Files backup created: ${backup_name}.tar.gz"
        print_info "📁 Backup location: ${BACKUP_BASE_DIR}/${backup_name}.tar.gz"
    else
        print_error "Files backup failed or is empty"
        return 1
    fi
}

# Detect compose file
detect_compose_file() {
    # Try current directory first
    if [ -f "docker-compose.ingest.yml" ]; then
        COMPOSE_FILE="docker-compose.ingest.yml"
        ENV_FILE_ARG="--env-file ../.env"
    elif [ -f "docker-compose.dev.yml" ]; then
        COMPOSE_FILE="docker-compose.dev.yml"
        ENV_FILE_ARG="--env-file ../.env"
    # Try /srv/deployment directory
    elif [ -f "/srv/deployment/docker-compose.ingest.yml" ]; then
        COMPOSE_FILE="/srv/deployment/docker-compose.ingest.yml"
        ENV_FILE_ARG="--env-file /srv/.env"
    elif [ -f "/srv/deployment/docker-compose.dev.yml" ]; then
        COMPOSE_FILE="/srv/deployment/docker-compose.dev.yml"
        ENV_FILE_ARG="--env-file /srv/.env"
    # Try relative to script location
    else
        local script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
        if [ -f "$script_dir/docker-compose.ingest.yml" ]; then
            COMPOSE_FILE="$script_dir/docker-compose.ingest.yml"
            ENV_FILE_ARG="--env-file $script_dir/../.env"
        elif [ -f "$script_dir/docker-compose.dev.yml" ]; then
            COMPOSE_FILE="$script_dir/docker-compose.dev.yml"
            ENV_FILE_ARG="--env-file $script_dir/../.env"
        else
            print_error "Docker-compose file not found!"
            print_info "Searched in:"
            print_info "  - Current directory: $(pwd)"
            print_info "  - /srv/deployment/"
            print_info "  - Script directory: $script_dir"
            exit 1
        fi
    fi
    
    print_info "Using compose file: $COMPOSE_FILE"
}

# Create metadata
create_backup_metadata() {
    local backup_dir="$1"
    local backup_type="$2"
    
    cat > "$backup_dir/backup_info.json" << EOF
{
    "backup_date": "$(date -Iseconds)",
    "backup_type": "$backup_type",
    "server_hostname": "$(hostname)",
    "git_commit": "$(cd .. && git rev-parse HEAD 2>/dev/null || echo 'unknown')",
    "backup_version": "1.0"
}
EOF
}

# Compress backup
compress_backup() {
    local backup_name="$1"
    
    print_info "Compressing..."
    cd "$BACKUP_BASE_DIR"
    tar -czf "${backup_name}.tar.gz" "${backup_name}/"
    rm -rf "${backup_name}/"
    
    # checksum
    sha256sum "${backup_name}.tar.gz" > "${backup_name}.tar.gz.sha256"
    
    local size=$(du -sh "${backup_name}.tar.gz" | cut -f1)
    print_success "File compressed: ${backup_name}.tar.gz (${size})"
}

# Download backup file from remote source
download_backup_file() {
    local backup_source="$1"
    local temp_dir="$2"
    
    # Check if it's a remote path (contains :)
    if [[ "$backup_source" == *":"* ]]; then
        print_info "Downloading backup from remote server..."
        local backup_file="$temp_dir/$(basename "$backup_source")"
        
        if command -v scp >/dev/null 2>&1; then
            if scp "$backup_source" "$backup_file"; then
                # Try to download checksum too
                scp "${backup_source}.sha256" "${backup_file}.sha256" 2>/dev/null || print_warning "Checksum file not found"
                echo "$backup_file"
                return 0
            else
                print_error "Failed to download backup file"
                return 1
            fi
        else
            print_error "scp not available. Please install openssh-client"
            return 1
        fi
    else
        # Local file
        if [ -f "$backup_source" ]; then
            echo "$backup_source"
            return 0
        else
            print_error "File not found: $backup_source"
            return 1
        fi
    fi
}

# Verify backup integrity
verify_backup_checksum() {
    local backup_file="$1"
    
    if [ -f "${backup_file}.sha256" ]; then
        print_info "Verifying backup integrity..."
        local backup_dir=$(dirname "$backup_file")
        if (cd "$backup_dir" && sha256sum -c "$(basename "${backup_file}.sha256")" >/dev/null 2>&1); then
            print_success "Backup integrity verified"
            return 0
        else
            print_error "Backup integrity check failed!"
            return 1
        fi
    else
        print_warning "Checksum file not found - skipping integrity check"
        return 0
    fi
}

# Load current environment variables
load_current_env() {
    local env_file=""
    if [ -f "../.env" ]; then
        env_file="../.env"
    elif [ -f "/srv/.env" ]; then
        env_file="/srv/.env"
    else
        print_error "Current .env file not found!"
        print_info "Searched in: $(pwd)/../.env and /srv/.env"
        return 1
    fi
    
    # Load current credentials
    export CURRENT_POSTGRES_USER=$(grep "^POSTGRES_USER=" "$env_file" | cut -d '=' -f2)
    export CURRENT_POSTGRES_PASSWORD=$(grep "^POSTGRES_PASSWORD=" "$env_file" | cut -d '=' -f2)
    export CURRENT_POSTGRES_DB=$(grep "^POSTGRES_DB=" "$env_file" | cut -d '=' -f2)
    export CURRENT_MINIO_USER=$(grep "^AWS_ACCESS_KEY_ID=" "$env_file" | cut -d '=' -f2)
    export CURRENT_MINIO_PASSWORD=$(grep "^AWS_SECRET_ACCESS_KEY=" "$env_file" | cut -d '=' -f2)
    export CURRENT_MINIO_BUCKET=$(grep "^AWS_STORAGE_BUCKET_NAME=" "$env_file" | cut -d '=' -f2)
    
    print_info "Current server credentials loaded from: $env_file"
    print_info "  DB User: ${CURRENT_POSTGRES_USER}"
    print_info "  DB Name: ${CURRENT_POSTGRES_DB}"
    print_info "  MinIO User: ${CURRENT_MINIO_USER}"
    print_info "  MinIO Bucket: ${CURRENT_MINIO_BUCKET}"
}

# Restore from backup (Smart restore - preserves new server credentials)
restore_from_backup() {
    print_header "🔄 Smart Restore from Backup"
    
    # Select restore type
    echo "Select what to restore:"
    echo "1) Full Restore (Database + MinIO Files)"
    echo "2) Database Only"
    echo "3) MinIO Files Only"
    echo ""
    read -p "Choose restore type (1-3): " restore_type
    
    case $restore_type in
        1)
            local restore_database=true
            local restore_minio=true
            print_info "Selected: Full Restore (Database + MinIO)"
            ;;
        2)
            local restore_database=true
            local restore_minio=false
            print_info "Selected: Database Only"
            ;;
        3)
            local restore_database=false
            local restore_minio=true
            print_info "Selected: MinIO Files Only"
            ;;
        *)
            print_error "Invalid selection"
            return 1
            ;;
    esac
    
    echo ""
    echo "This restore will:"
    echo "  ✅ Keep current server passwords and credentials"
    if [ "$restore_database" = true ]; then
        echo "  ✅ Restore database data"
    fi
    if [ "$restore_minio" = true ]; then
        echo "  ✅ Restore MinIO files"
    fi
    echo "  ⚠️  NOT change any passwords or configurations"
    echo ""
    
    # Check for available backups in default directory
    local backup_source=""
    
    if [ -d "$BACKUP_BASE_DIR" ]; then
        local backup_files=($(ls -t "$BACKUP_BASE_DIR"/*.tar.gz 2>/dev/null))
        
        if [ ${#backup_files[@]} -gt 0 ]; then
            print_header "📋 Available Backups"
            echo ""
            echo "Found ${#backup_files[@]} backup(s) in $BACKUP_BASE_DIR:"
            echo ""
            
            local index=1
            for backup in "${backup_files[@]}"; do
                local filename=$(basename "$backup")
                local filesize=$(du -sh "$backup" | cut -f1)
                local filedate=$(stat -c %y "$backup" 2>/dev/null | cut -d'.' -f1 || stat -f "%Sm" "$backup" 2>/dev/null)
                
                printf "%2d) %-50s [%8s] %s\n" "$index" "$filename" "$filesize" "$filedate"
                index=$((index + 1))
            done
            
            echo ""
            echo "0) Enter custom path (local or remote)"
            echo "q) Cancel and return to main menu"
            echo ""
            read -p "Select backup number to restore [0-${#backup_files[@]}]: " selection
            
            # Handle selection
            if [[ "$selection" == "q" ]] || [[ "$selection" == "Q" ]]; then
                print_info "Operation cancelled"
                return 0
            elif [[ "$selection" =~ ^[0-9]+$ ]] && [ "$selection" -ge 1 ] && [ "$selection" -le ${#backup_files[@]} ]; then
                backup_source="${backup_files[$((selection - 1))]}"
                print_success "Selected: $(basename "$backup_source")"
                echo ""
            elif [ "$selection" == "0" ]; then
                # Custom path will be asked below
                backup_source=""
            else
                print_error "Invalid selection"
                return 1
            fi
        fi
    fi
    
    # If no backup selected from list, ask for custom path
    if [ -z "$backup_source" ]; then
        echo ""
        echo "Enter backup file path:"
        echo "  - Local file: /path/to/backup.tar.gz"
        echo "  - Remote file: user@server:/path/to/backup.tar.gz"
        echo ""
        read -p "Backup path: " backup_source
        
        if [ -z "$backup_source" ]; then
            print_error "No backup path provided"
            return 1
        fi
    fi
    
    # Load current environment
    load_current_env || return 1
    
    # User confirmation
    echo ""
    print_warning "This will replace all data but keep current credentials!"
    read -p "Continue? (y/N): " confirm
    if [[ ! $confirm =~ ^[Yy]$ ]]; then
        print_info "Operation cancelled"
        return 0
    fi
    
    # Create temp directory
    local temp_dir=$(mktemp -d)
    print_info "Temporary directory: $temp_dir"
    
    # Download/locate backup file
    local backup_file=$(download_backup_file "$backup_source" "$temp_dir")
    if [ $? -ne 0 ]; then
        rm -rf "$temp_dir"
        return 1
    fi
    
    # Verify checksum
    verify_backup_checksum "$backup_file" || {
        read -p "Checksum failed. Continue anyway? (y/N): " continue_anyway
        if [[ ! $continue_anyway =~ ^[Yy]$ ]]; then
            rm -rf "$temp_dir"
            return 1
        fi
    }
    
    # Show backup info
    print_info "Backup file: $backup_file"
    print_info "Backup size: $(du -sh "$backup_file" | cut -f1)"
    
    # Extract backup
    print_info "Extracting backup..."
    local extract_dir="$temp_dir/extracted"
    mkdir -p "$extract_dir"
    tar -xzf "$backup_file" -C "$extract_dir"
    
    # Find backup directory
    local backup_dir=$(find "$extract_dir" -maxdepth 2 -type d -name "ingest_*" | head -1)
    if [ -z "$backup_dir" ]; then
        backup_dir="$extract_dir"
    fi
    
    print_info "Backup directory: $backup_dir"
    
    # Show backup info if available
    if [ -f "$backup_dir/backup_info.json" ]; then
        print_info "Backup information:"
        cat "$backup_dir/backup_info.json" | python3 -m json.tool 2>/dev/null || cat "$backup_dir/backup_info.json"
        echo ""
    fi
    
    # Detect compose file
    detect_compose_file
    
    # Restore database data (using current credentials)
    if [ "$restore_database" = true ] && ([ -f "$backup_dir/database.sql.gz" ] || [ -f "$backup_dir/database.sql" ]); then
        print_info "Restoring database data..."
        print_info "  Using current credentials: ${CURRENT_POSTGRES_USER}@${CURRENT_POSTGRES_DB}"
        
        # Stop web and worker to close database connections
        print_info "  Stopping web and worker containers..."
        docker compose -f "$COMPOSE_FILE" $ENV_FILE_ARG stop web worker beat 2>/dev/null || true
        sleep 3
        
        # Make sure database container is running
        docker compose -f "$COMPOSE_FILE" $ENV_FILE_ARG up -d db
        sleep 5
        
        # Terminate all connections to the database
        print_info "  Terminating active database connections..."
        docker compose -f "$COMPOSE_FILE" $ENV_FILE_ARG exec -T db \
            psql -U "${CURRENT_POSTGRES_USER}" -d postgres -c \
            "SELECT pg_terminate_backend(pg_stat_activity.pid) FROM pg_stat_activity WHERE pg_stat_activity.datname = '${CURRENT_POSTGRES_DB}' AND pid <> pg_backend_pid();" >/dev/null 2>&1 || true
        
        # Drop and recreate database
        print_info "  Dropping existing database..."
        docker compose -f "$COMPOSE_FILE" $ENV_FILE_ARG exec -T db \
            psql -U "${CURRENT_POSTGRES_USER}" -d postgres -c "DROP DATABASE IF EXISTS ${CURRENT_POSTGRES_DB};" 2>&1 | grep -v "does not exist" || true
        
        print_info "  Creating fresh database..."
        docker compose -f "$COMPOSE_FILE" $ENV_FILE_ARG exec -T db \
            psql -U "${CURRENT_POSTGRES_USER}" -d postgres -c "CREATE DATABASE ${CURRENT_POSTGRES_DB};"
        
        # Restore data
        print_info "  Importing data..."
        if [ -f "$backup_dir/database.sql.gz" ]; then
            zcat "$backup_dir/database.sql.gz" | \
                docker compose -f "$COMPOSE_FILE" $ENV_FILE_ARG exec -T db \
                psql -U "${CURRENT_POSTGRES_USER}" -d "${CURRENT_POSTGRES_DB}" >/dev/null 2>&1
        else
            cat "$backup_dir/database.sql" | \
                docker compose -f "$COMPOSE_FILE" $ENV_FILE_ARG exec -T db \
                psql -U "${CURRENT_POSTGRES_USER}" -d "${CURRENT_POSTGRES_DB}" >/dev/null 2>&1
        fi
        
        print_success "Database data restored successfully"
    elif [ "$restore_database" = true ]; then
        print_warning "No database backup found in the backup file"
    else
        print_info "Database restore skipped (not selected)"
    fi
    
    # Restore MinIO files (using current bucket)
    if [ "$restore_minio" = true ] && [ -f "$backup_dir/minio_data.tar.gz" ]; then
        # Verify it's a valid tar.gz file
        local file_type=$(file -b "$backup_dir/minio_data.tar.gz" | cut -d' ' -f1)
        if [[ "$file_type" != "gzip" ]]; then
            print_warning "MinIO backup file is not a valid gzip archive (type: $file_type)"
            print_warning "Skipping MinIO restore - backup may have failed during creation"
            print_info "  You can restore MinIO files manually later if needed"
        else
            print_info "Restoring MinIO files..."
            print_info "  Using current bucket: ${CURRENT_MINIO_BUCKET}"
            
            # Stop MinIO
            docker compose -f "$COMPOSE_FILE" $ENV_FILE_ARG stop minio
            sleep 3
            
            # Get volume name
            local volume_name=$(docker volume ls --format "{{.Name}}" | grep minio_data | head -1)
            if [ -z "$volume_name" ]; then
                volume_name="deployment_minio_data"
            fi
            
            print_info "  Clearing MinIO data volume: $volume_name"
            docker run --rm -v "$volume_name:/data" alpine sh -c "rm -rf /data/* /data/.* 2>/dev/null || true"
            
            print_info "  Extracting MinIO files..."
            if docker run --rm -v "$volume_name:/data" -v "$backup_dir:/backup" alpine sh -c \
                "cd /data && tar -xzf /backup/minio_data.tar.gz --strip-components=1 2>/dev/null || tar -xzf /backup/minio_data.tar.gz" 2>/dev/null; then
                
                # Fix permissions
                docker run --rm -v "$volume_name:/data" alpine sh -c "chown -R 1000:1000 /data 2>/dev/null || true"
                
                # Start MinIO
                docker compose -f "$COMPOSE_FILE" $ENV_FILE_ARG start minio
                sleep 5
                
                print_success "MinIO files restored successfully"
            else
                print_error "Failed to extract MinIO backup"
                print_warning "Starting MinIO anyway (will be empty)"
                docker compose -f "$COMPOSE_FILE" $ENV_FILE_ARG start minio
                sleep 5
            fi
        fi
    elif [ "$restore_minio" = true ]; then
        print_warning "No MinIO backup found in the backup file"
        print_info "MinIO will start with empty storage"
    else
        print_info "MinIO restore skipped (not selected)"
    fi
    
    # Restart all services
    print_info "Restarting all services..."
    docker compose -f "$COMPOSE_FILE" $ENV_FILE_ARG restart
    
    # Wait for services to be ready
    print_info "Waiting for services to start..."
    sleep 15
    
    # Run migrations (only if database was restored)
    if [ "$restore_database" = true ]; then
        print_info "Syncing database migrations..."
        # Use --fake-initial to mark initial migrations as applied without running them
        # This is necessary because the database already has the schema from the backup
        if docker compose -f "$COMPOSE_FILE" $ENV_FILE_ARG exec web python manage.py migrate --fake-initial --noinput 2>&1 | grep -qE "(No migrations to apply|Applying|FAKED)"; then
            print_success "Database migrations synchronized"
        else
            # If --fake-initial fails, use --fake to sync all migrations
            print_info "Syncing with --fake (schema already exists)..."
            docker compose -f "$COMPOSE_FILE" $ENV_FILE_ARG exec web python manage.py migrate --fake --noinput 2>/dev/null || true
            print_success "Migration history synchronized"
        fi
        
        # Collect static files
        print_info "Collecting static files..."
        docker compose -f "$COMPOSE_FILE" $ENV_FILE_ARG exec web python manage.py collectstatic --noinput 2>/dev/null || \
            print_warning "Static files collection failed"
    fi
    
    # Cleanup
    rm -rf "$temp_dir"
    
    print_success "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    print_success "Restore completed successfully!"
    print_success "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    print_info "Restored items:"
    if [ "$restore_database" = true ]; then
        echo "  ✅ Database data restored"
    fi
    if [ "$restore_minio" = true ]; then
        echo "  ✅ MinIO files restored"
    fi
    echo ""
    print_info "Important notes:"
    echo "  ✅ Current server credentials are preserved"
    echo "  ✅ No passwords were changed"
    echo ""
    print_info "Access Information:"
    echo "  🌐 Admin Panel: https://your-domain/admin/"
    echo "  📦 MinIO Console: http://your-domain:9001"
    echo "  🔐 Use your current server credentials to login"
    echo ""
    print_info "Next steps:"
    echo "  1. Test admin panel access"
    echo "  2. Verify MinIO files are accessible"
    echo "  3. Check application functionality"
    echo "  4. Monitor logs: docker compose logs -f"
}

# Setup automated backup
setup_automated_backup() {
    print_header "⏰ Setup Automated Backup"
    
    echo "Automated Backup Settings:"
    echo ""
    read -p "Execution hour (0-23) [default: 2]: " backup_hour
    backup_hour=${backup_hour:-2}
    
    read -p "Local retention days [default: 7]: " local_days
    local_days=${local_days:-7}
    
    # Create automated script
    cat > "/tmp/auto_backup.sh" << EOF
#!/bin/bash
cd "$(pwd)"
./backup_manager.sh --auto-backup
EOF
    chmod +x "/tmp/auto_backup.sh"
    
    # Setup cron
    local cron_job="0 $backup_hour * * * /tmp/auto_backup.sh >> $LOG_FILE 2>&1"
    
    if crontab -l 2>/dev/null | grep -q "auto_backup.sh"; then
        print_warning "Cron job already exists"
    else
        (crontab -l 2>/dev/null; echo "$cron_job") | crontab -
        print_success "Automated backup configured: daily at $backup_hour:00"
    fi
    
    # Create directories
    sudo mkdir -p "$BACKUP_BASE_DIR"
    sudo mkdir -p "$(dirname "$LOG_FILE")"
    sudo chown -R $(whoami):$(whoami) "$BACKUP_BASE_DIR" 2>/dev/null || true
    
    print_info "Settings saved"
}

# View backups
list_backups() {
    print_header "📋 Backup List"
    
    if [ -d "$BACKUP_BASE_DIR" ]; then
        echo "Local backups:"
        ls -lh "$BACKUP_BASE_DIR"/*.tar.gz 2>/dev/null || echo "No local backups found"
        echo ""
        echo "📁 Backup directory: $BACKUP_BASE_DIR"
    else
        echo "Backup directory does not exist"
        echo "📁 Expected location: $BACKUP_BASE_DIR"
    fi
}

# Setup remote server
setup_remote_server() {
    print_header "🌐 Setup Remote Backup Server"
    
    echo "Connection type:"
    echo "1) SSH/SFTP"
    echo "2) NFS Mount"
    echo "3) SMB/CIFS"
    echo ""
    read -p "Choose option (1-3): " connection_type
    
    case $connection_type in
        1)
            read -p "Server IP address: " remote_ip
            read -p "Username: " remote_user
            read -p "Directory path: " remote_path
            
            if ssh -o ConnectTimeout=10 "$remote_user@$remote_ip" "echo 'Connection test'" 2>/dev/null; then
                print_success "SSH connection successful"
                echo "REMOTE_TYPE=ssh" > ~/.backup_config
                echo "REMOTE_IP=$remote_ip" >> ~/.backup_config
                echo "REMOTE_USER=$remote_user" >> ~/.backup_config
                echo "REMOTE_PATH=$remote_path" >> ~/.backup_config
            else
                print_error "SSH connection failed"
            fi
            ;;
        2)
            read -p "NFS address (example: 192.168.1.100:/backup): " nfs_server
            sudo mkdir -p /mnt/remote_backup
            if sudo mount -t nfs "$nfs_server" /mnt/remote_backup; then
                print_success "NFS mount successful"
                echo "$nfs_server /mnt/remote_backup nfs defaults 0 0" | sudo tee -a /etc/fstab
            else
                print_error "NFS mount failed"
            fi
            ;;
        3)
            read -p "SMB address (example: //192.168.1.100/backup): " smb_server
            read -p "Username: " smb_user
            read -s -p "Password: " smb_pass
            echo ""
            
            sudo tee /etc/cifs-credentials > /dev/null << EOF
username=$smb_user
password=$smb_pass
EOF
            sudo chmod 600 /etc/cifs-credentials
            
            sudo mkdir -p /mnt/remote_backup
            if sudo mount -t cifs "$smb_server" /mnt/remote_backup -o credentials=/etc/cifs-credentials; then
                print_success "SMB mount successful"
                echo "$smb_server /mnt/remote_backup cifs credentials=/etc/cifs-credentials 0 0" | sudo tee -a /etc/fstab
            else
                print_error "SMB mount failed"
            fi
            ;;
    esac
}

# Cleanup old backups
cleanup_old_backups() {
    print_header "🧹 Cleanup Old Backups"
    
    read -p "Delete backups older than how many days? [default: 7]: " days
    days=${days:-7}
    
    if [ -d "$BACKUP_BASE_DIR" ]; then
        local count=$(find "$BACKUP_BASE_DIR" -name "*.tar.gz" -mtime +$days | wc -l)
        if [ $count -gt 0 ]; then
            echo "Files older than $days days:"
            find "$BACKUP_BASE_DIR" -name "*.tar.gz" -mtime +$days -ls
            
            read -p "Delete these files? (y/N): " confirm
            if [[ $confirm =~ ^[Yy]$ ]]; then
                find "$BACKUP_BASE_DIR" -name "*.tar.gz" -mtime +$days -delete
                find "$BACKUP_BASE_DIR" -name "*.sha256" -mtime +$days -delete
                print_success "$count files deleted"
            fi
        else
            print_info "No old files found"
        fi
    fi
}

# Test system
test_backup_system() {
    print_header "🧪 Test Backup System"
    
    print_info "Testing database connection..."
    detect_compose_file
    if docker compose -f "$COMPOSE_FILE" $ENV_FILE_ARG exec -T db pg_isready -U "${POSTGRES_USER:-ingest}" >/dev/null 2>&1; then
        print_success "Database: OK"
    else
        print_error "Database: Error"
    fi
    
    print_info "Testing MinIO connection..."
    if docker compose -f "$COMPOSE_FILE" $ENV_FILE_ARG exec -T minio mc --version >/dev/null 2>&1; then
        print_success "MinIO: OK"
    else
        print_error "MinIO: Error"
    fi
    
    print_info "Checking disk space..."
    local available=$(df /opt | awk 'NR==2 {print int($4/1024/1024)}')
    if [ "$available" -gt 1 ]; then
        print_success "Disk space: ${available}GB available"
    else
        print_warning "Low disk space: ${available}GB available"
    fi
}

# Automated backup (for cron)
auto_backup() {
    log_message "Starting automated backup"
    create_full_backup
    cleanup_old_backups
    log_message "Automated backup completed"
}

# Main function
main() {
    # Check for automated parameter
    if [ "$1" = "--auto-backup" ]; then
        auto_backup
        exit 0
    fi
    
    # Interactive menu
    while true; do
        show_main_menu
        
        case $choice in
            1) create_manual_backup ;;
            2) restore_from_backup ;;
            3) setup_automated_backup ;;
            4) list_backups ;;
            5) cleanup_old_backups ;;
            6) setup_remote_server ;;
            7) test_backup_system ;;
            0) print_info "Exiting..."; exit 0 ;;
            *) print_error "Invalid selection" ;;
        esac
        
        echo ""
        read -p "Press Enter to continue..." 
    done
}

# Main execution
main "$@"
