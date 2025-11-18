#!/bin/bash

# ====================================================
# 🚀 اسکریپت جامع مدیریت سیستم RAG-Ingest
# ====================================================
# این اسکریپت تمام عملیات‌های مهم را در یک جا جمع می‌کند
# نسخه: 1.0.0
# تاریخ: 1403/08/28
# ====================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Global variables
CONTAINERS=("deployment-web-1" "deployment-worker-1" "deployment-beat-1")
PROJECT_DIR="/srv"
SCRIPT_NAME=$(basename "$0")

# ====================================================
# Helper Functions
# ====================================================

print_header() {
    echo ""
    echo -e "${CYAN}========================================${NC}"
    echo -e "${CYAN}$1${NC}"
    echo -e "${CYAN}========================================${NC}"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

check_docker() {
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed or not in PATH"
        exit 1
    fi
    
    if ! docker ps &> /dev/null; then
        print_error "Docker daemon is not running or you don't have permissions"
        exit 1
    fi
}

# ====================================================
# Main Functions
# ====================================================

# 1. Fix SyncLog Deletion Issue
fix_synclog_issue() {
    print_header "🔧 رفع مشکل حذف LegalUnit با SyncLog"
    
    for CONTAINER in "${CONTAINERS[@]}"; do
        if docker ps --format "{{.Names}}" | grep -q "^${CONTAINER}$"; then
            print_info "Applying fix to $CONTAINER..."
            
            docker exec "$CONTAINER" python manage.py shell << 'EOF' 2>/dev/null || true
# Fix database constraint
from django.db import connection

try:
    with connection.cursor() as cursor:
        # Drop old constraint
        cursor.execute("""
            ALTER TABLE embeddings_synclog 
            DROP CONSTRAINT IF EXISTS embeddings_synclog_chunk_id_fkey;
        """)
        
        # Add new constraint with SET NULL
        cursor.execute("""
            ALTER TABLE embeddings_synclog 
            ADD CONSTRAINT embeddings_synclog_chunk_id_fkey 
            FOREIGN KEY (chunk_id) 
            REFERENCES documents_chunk(id) 
            ON DELETE SET NULL;
        """)
    print("✓ Database constraint updated")
except Exception as e:
    print(f"Database update skipped: {e}")

# Create signal handlers
signals_code = '''
from django.db.models.signals import pre_delete
from django.dispatch import receiver
from django.db import transaction
import logging

logger = logging.getLogger(__name__)

@receiver(pre_delete, sender='documents.LegalUnit')
def cleanup_before_legalunit_delete(sender, instance, **kwargs):
    from ingest.apps.documents.models import Chunk
    from ingest.apps.embeddings.models_synclog import SyncLog
    
    with transaction.atomic():
        chunk_ids = list(instance.chunks.values_list('id', flat=True))
        if chunk_ids:
            SyncLog.objects.filter(chunk_id__in=chunk_ids).delete()
            logger.info(f"Cleaned up SyncLogs for LegalUnit {instance.id}")
'''

with open('/app/ingest/apps/documents/signals.py', 'w') as f:
    f.write(signals_code)
print("✓ Signals created")
EOF
            print_success "Fix applied to $CONTAINER"
        else
            print_warning "$CONTAINER is not running"
        fi
    done
    
    print_success "SyncLog issue fixed!"
}

# 2. Apply Performance Optimizations
apply_optimizations() {
    print_header "⚡ اعمال بهینه‌سازی‌های عملکرد"
    
    # List of optimization files
    OPTIMIZATION_FILES=(
        "ingest/core/optimizations.py"
        "ingest/core/middleware.py"
        "ingest/settings/performance.py"
        "ingest/apps/documents/signals.py"
        "ingest/api/mixins.py"
        "ingest/apps/documents/management/commands/optimize_database.py"
        "ingest/apps/documents/management/commands/monitor_performance.py"
    )
    
    # Copy files to containers
    for CONTAINER in "${CONTAINERS[@]}"; do
        if docker ps --format "{{.Names}}" | grep -q "^${CONTAINER}$"; then
            print_info "Copying files to $CONTAINER..."
            
            # Create necessary directories
            docker exec "$CONTAINER" mkdir -p \
                /app/ingest/core \
                /app/ingest/settings \
                /app/ingest/api \
                /app/ingest/apps/documents/management/commands 2>/dev/null || true
            
            # Copy optimization files if they exist
            for FILE in "${OPTIMIZATION_FILES[@]}"; do
                if [ -f "$PROJECT_DIR/$FILE" ]; then
                    docker cp "$PROJECT_DIR/$FILE" "$CONTAINER:/app/$FILE" 2>/dev/null && \
                        echo -e "  ${GREEN}✓${NC} $FILE" || \
                        echo -e "  ${YELLOW}⚠${NC} $FILE (skipped)"
                fi
            done
        fi
    done
    
    print_success "Optimization files deployed"
}

# 3. Create Database Indexes
create_indexes() {
    print_header "📊 ایجاد Index های دیتابیس"
    
    docker exec deployment-web-1 python manage.py shell << 'EOF' 2>/dev/null || {
        print_error "Could not create indexes"
        return 1
    }
from django.db import connection

indexes = [
    "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_legalunit_work_type ON documents_legalunit(work_id, unit_type);",
    "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_chunk_unit_created ON documents_chunk(unit_id, created_at DESC);",
    "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_chunk_node_id ON documents_chunk(node_id) WHERE node_id IS NOT NULL;",
    "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_synclog_status_retry ON embeddings_synclog(status, retry_count);",
]

with connection.cursor() as cursor:
    for idx in indexes:
        try:
            cursor.execute(idx)
            print(f"✓ Index created")
        except Exception as e:
            print(f"⚠ Index skipped: {e}")
EOF
    
    print_success "Database indexes optimized"
}

# 4. Monitor Performance
monitor_performance() {
    print_header "📈 مانیتورینگ عملکرد"
    
    docker exec deployment-web-1 python manage.py shell << 'EOF' 2>/dev/null || {
        print_error "Could not monitor performance"
        return 1
    }
import time
from django.core.cache import cache
from django.db import connection

# Test cache
cache.set('test', 'value', 60)
cache_works = cache.get('test') == 'value'
print(f"Cache: {'✓ Working' if cache_works else '✗ Not working'}")

# Check DB pool
conn_age = connection.settings_dict.get('CONN_MAX_AGE', 0)
print(f"DB Connection Pool: {conn_age} seconds")

# Test response time
from django.test import Client
client = Client()
start = time.time()
# Simple health check
response = client.get('/api/health/')
duration = time.time() - start
print(f"Response Time: {duration:.3f}s")
EOF
}

# 5. Restart Services
restart_services() {
    print_header "🔄 ری‌استارت سرویس‌ها"
    
    for CONTAINER in "${CONTAINERS[@]}"; do
        if docker ps --format "{{.Names}}" | grep -q "^${CONTAINER}$"; then
            print_info "Restarting $CONTAINER..."
            docker restart "$CONTAINER" &
        fi
    done
    
    wait
    sleep 10
    
    # Check health
    for CONTAINER in "${CONTAINERS[@]}"; do
        if docker ps --format "{{.Names}}" | grep -q "$CONTAINER"; then
            STATUS=$(docker ps --format "table {{.Names}}\t{{.Status}}" | grep "$CONTAINER" | awk '{print $2}')
            if [[ "$STATUS" == *"healthy"* ]] || [[ "$STATUS" == *"Up"* ]]; then
                print_success "$CONTAINER is running"
            else
                print_warning "$CONTAINER status: $STATUS"
            fi
        fi
    done
}

# 6. Clear Cache
clear_cache() {
    print_header "🧹 پاکسازی Cache"
    
    docker exec deployment-web-1 python manage.py shell -c "
from django.core.cache import cache
cache.clear()
print('Cache cleared')
" 2>/dev/null && print_success "Cache cleared" || print_error "Could not clear cache"
}

# 7. System Status
system_status() {
    print_header "📊 وضعیت سیستم"
    
    echo -e "${BLUE}Containers:${NC}"
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep deployment || true
    
    echo ""
    echo -e "${BLUE}Resource Usage:${NC}"
    docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" | grep deployment || true
}

# 8. Full Setup
full_setup() {
    print_header "🚀 راه‌اندازی کامل سیستم"
    
    fix_synclog_issue
    apply_optimizations
    create_indexes
    clear_cache
    restart_services
    sleep 5
    monitor_performance
    
    print_header "✅ سیستم آماده است!"
}

# ====================================================
# Menu System
# ====================================================

show_menu() {
    print_header "🎯 منوی مدیریت سیستم RAG-Ingest"
    
    echo ""
    echo "1) رفع مشکل حذف LegalUnit (SyncLog)"
    echo "2) اعمال بهینه‌سازی‌های عملکرد"
    echo "3) ایجاد Index های دیتابیس"
    echo "4) مانیتورینگ عملکرد"
    echo "5) ری‌استارت سرویس‌ها"
    echo "6) پاکسازی Cache"
    echo "7) نمایش وضعیت سیستم"
    echo "8) راه‌اندازی کامل (همه موارد)"
    echo "0) خروج"
    echo ""
    echo -n "انتخاب شما: "
}

# ====================================================
# Main Script
# ====================================================

main() {
    check_docker
    
    # If no arguments, show menu
    if [ $# -eq 0 ]; then
        while true; do
            show_menu
            read -r choice
            
            case $choice in
                1) fix_synclog_issue ;;
                2) apply_optimizations ;;
                3) create_indexes ;;
                4) monitor_performance ;;
                5) restart_services ;;
                6) clear_cache ;;
                7) system_status ;;
                8) full_setup ;;
                0) echo "خروج..."; exit 0 ;;
                *) print_error "انتخاب نامعتبر" ;;
            esac
            
            echo ""
            echo -n "Press Enter to continue..."
            read -r
        done
    else
        # Handle command line arguments
        case "$1" in
            fix-synclog) fix_synclog_issue ;;
            optimize) apply_optimizations ;;
            indexes) create_indexes ;;
            monitor) monitor_performance ;;
            restart) restart_services ;;
            clear-cache) clear_cache ;;
            status) system_status ;;
            setup) full_setup ;;
            --help|-h)
                echo "Usage: $SCRIPT_NAME [command]"
                echo ""
                echo "Commands:"
                echo "  fix-synclog    Fix LegalUnit deletion issue"
                echo "  optimize       Apply performance optimizations"
                echo "  indexes        Create database indexes"
                echo "  monitor        Monitor performance"
                echo "  restart        Restart all services"
                echo "  clear-cache    Clear Redis cache"
                echo "  status         Show system status"
                echo "  setup          Full system setup"
                echo ""
                echo "Or run without arguments for interactive menu"
                ;;
            *)
                print_error "Unknown command: $1"
                echo "Run '$SCRIPT_NAME --help' for usage"
                exit 1
                ;;
        esac
    fi
}

# Run main function
main "$@"
