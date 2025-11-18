#!/bin/bash

# ==============================================================================
# 🚀 اسکریپت مدیریت سیستم RAG-Ingest
# ==============================================================================

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# Functions
print_header() {
    echo ""
    echo "========================================="
    echo "$1"
    echo "========================================="
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"  
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

# 1. Fix SyncLog Issue & Delete LegalUnit
fix_synclog() {
    print_header "🔧 رفع مشکل حذف LegalUnit"
    
    if [ "$1" == "delete" ] && [ -n "$2" ]; then
        # حذف مستقیم LegalUnit
        echo "🗑️ حذف LegalUnit با Work ID: $2"
        docker exec deployment-web-1 python manage.py shell << EOF
from ingest.apps.documents.models import LegalUnit
from ingest.apps.embeddings.models_synclog import SyncLog

work_id = "$2"
units = LegalUnit.objects.filter(work_id=work_id)
count = units.count()

if count > 0:
    # حذف SyncLog ها
    for unit in units:
        chunk_ids = list(unit.chunks.values_list("id", flat=True))
        if chunk_ids:
            SyncLog.objects.filter(chunk_id__in=chunk_ids).delete()
    
    # حذف LegalUnit ها
    deleted = units.delete()
    print(f"✅ Deleted {deleted[0]} LegalUnits")
else:
    print("❌ No LegalUnit found with this Work ID")
EOF
        return
    fi
    
    # Python script to fix the issue
    cat > /tmp/fix_synclog.py << 'SCRIPT'
from django.db import connection

# Fix database constraint
try:
    with connection.cursor() as cursor:
        cursor.execute("""
            ALTER TABLE embeddings_synclog 
            DROP CONSTRAINT IF EXISTS embeddings_synclog_chunk_id_fkey;
        """)
        cursor.execute("""
            ALTER TABLE embeddings_synclog 
            ADD CONSTRAINT embeddings_synclog_chunk_id_fkey 
            FOREIGN KEY (chunk_id) 
            REFERENCES documents_chunk(id) 
            ON DELETE SET NULL;
        """)
    print("✓ Database constraint updated")
except Exception as e:
    print(f"⚠ Constraint update: {e}")

# Create signal handlers
signals_code = '''
from django.db.models.signals import pre_delete
from django.dispatch import receiver
from django.db import transaction

@receiver(pre_delete, sender='documents.LegalUnit')  
def cleanup_before_legalunit_delete(sender, instance, **kwargs):
    from ingest.apps.embeddings.models_synclog import SyncLog
    chunk_ids = list(instance.chunks.values_list('id', flat=True))
    if chunk_ids:
        SyncLog.objects.filter(chunk_id__in=chunk_ids).delete()
'''

with open('/app/ingest/apps/documents/signals.py', 'w') as f:
    f.write(signals_code)
print("✓ Signals created")
SCRIPT

    # Apply fix to all containers
    for CONTAINER in deployment-web-1 deployment-worker-1 deployment-beat-1; do
        if docker ps | grep -q "$CONTAINER"; then
            docker cp /tmp/fix_synclog.py "$CONTAINER:/tmp/fix_synclog.py"
            docker exec "$CONTAINER" python manage.py shell < /tmp/fix_synclog.py 2>/dev/null && \
                print_success "Fixed $CONTAINER" || \
                print_warning "Could not fix $CONTAINER"
        fi
    done
    
    rm -f /tmp/fix_synclog.py
    print_success "SyncLog issue fixed!"
}

# 2. Apply Optimizations
apply_optimizations() {
    print_header "⚡ اعمال بهینه‌سازی‌ها"
    
    # Copy optimization files
    FILES=(
        "ingest/core/optimizations.py"
        "ingest/core/middleware.py"
        "ingest/settings/performance.py"
        "ingest/apps/documents/signals.py"
        "ingest/api/mixins.py"
    )
    
    for FILE in "${FILES[@]}"; do
        if [ -f "/srv/$FILE" ]; then
            for CONTAINER in deployment-web-1 deployment-worker-1 deployment-beat-1; do
                if docker ps | grep -q "$CONTAINER"; then
                    docker cp "/srv/$FILE" "$CONTAINER:/app/$FILE" 2>/dev/null
                fi
            done
            echo "  ✓ Copied $FILE"
        fi
    done
    
    print_success "Optimizations applied!"
}

# 3. Create Indexes
create_indexes() {
    print_header "📊 ایجاد Index های دیتابیس"
    
    docker exec deployment-web-1 python manage.py shell -c "
from django.db import connection
with connection.cursor() as c:
    try:
        c.execute('CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_chunk_unit ON documents_chunk(unit_id);')
        c.execute('CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_synclog_chunk ON embeddings_synclog(chunk_id);')
        print('✓ Indexes created')
    except Exception as e:
        print(f'⚠ {e}')
" 2>/dev/null || print_warning "Could not create indexes"
    
    print_success "Database indexes ready!"
}

# 4. Monitor Performance
monitor_performance() {
    print_header "📈 مانیتورینگ عملکرد"
    
    docker exec deployment-web-1 python manage.py shell -c "
from django.core.cache import cache
from django.db import connection

# Test cache
cache.set('test', 'OK', 60)
print(f'Cache: {cache.get(\"test\")}')

# Check DB pool
print(f'DB Pool: {connection.settings_dict.get(\"CONN_MAX_AGE\", 0)} seconds')

# Count records
from ingest.apps.documents.models import LegalUnit, Chunk
print(f'LegalUnits: {LegalUnit.objects.count()}')
print(f'Chunks: {Chunk.objects.count()}')
" 2>/dev/null || print_warning "Could not check performance"
}

# 5. Restart Services
restart_services() {
    print_header "🔄 ری‌استارت سرویس‌ها"
    
    for CONTAINER in deployment-web-1 deployment-worker-1 deployment-beat-1; do
        docker restart "$CONTAINER" 2>/dev/null && \
            print_success "Restarted $CONTAINER" || \
            print_warning "Could not restart $CONTAINER"
    done
    
    sleep 10
    print_success "Services restarted!"
}

# 6. System Status
system_status() {
    print_header "📊 وضعیت سیستم"
    
    echo -e "${BLUE}Containers:${NC}"
    docker ps --format "table {{.Names}}\t{{.Status}}" | grep deployment || true
    
    echo ""
    echo -e "${BLUE}Resource Usage:${NC}"
    docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" | grep deployment || true
}

# 7. Full Setup
full_setup() {
    print_header "🚀 راه‌اندازی کامل"
    
    fix_synclog
    apply_optimizations
    create_indexes
    restart_services
    monitor_performance
    
    print_header "✅ سیستم آماده است!"
}

# Menu
show_menu() {
    clear
    print_header "🎯 مدیریت سیستم RAG-Ingest"
    
    echo "1) رفع مشکل حذف LegalUnit"
    echo "2) اعمال بهینه‌سازی‌ها"
    echo "3) ایجاد Index ها"
    echo "4) مانیتورینگ عملکرد"
    echo "5) ری‌استارت سرویس‌ها"
    echo "6) وضعیت سیستم"
    echo "7) راه‌اندازی کامل"
    echo "0) خروج"
    echo ""
    echo -n "انتخاب: "
}

# Main
main() {
    if [ $# -eq 0 ]; then
        # Interactive mode
        while true; do
            show_menu
            read choice
            
            case $choice in
                1) fix_synclog ;;
                2) apply_optimizations ;;
                3) create_indexes ;;
                4) monitor_performance ;;
                5) restart_services ;;
                6) system_status ;;
                7) full_setup ;;
                0) echo "خروج..."; exit 0 ;;
                *) print_error "انتخاب نامعتبر" ;;
            esac
            
            echo ""
            read -p "Press Enter to continue..."
        done
    else
        # Command mode
        case "$1" in
            fix) fix_synclog ;;
            optimize) apply_optimizations ;;
            index) create_indexes ;;
            monitor) monitor_performance ;;
            restart) restart_services ;;
            status) system_status ;;
            setup) full_setup ;;
            delete)
                if [ -z "$2" ]; then
                    echo "Usage: $0 delete <work_id>"
                    echo "Example: $0 delete 75a28f9c-099b-4b52-92c7-7edf7d006230"
                    exit 1
                fi
                fix_synclog delete "$2"
                ;;
            help|--help|-h)
                echo "Usage: $0 [command]"
                echo ""
                echo "Commands:"
                echo "  fix       Fix SyncLog deletion issue"
                echo "  delete    Delete LegalUnit by Work ID"
                echo "  optimize  Apply optimizations"
                echo "  index     Create database indexes"
                echo "  monitor   Monitor performance"
                echo "  restart   Restart services"
                echo "  status    Show system status"
                echo "  setup     Full setup"
                echo ""
                echo "Example:"
                echo "  $0 delete 75a28f9c-099b-4b52-92c7-7edf7d006230"
                ;;
            *)
                print_error "Unknown command: $1"
                echo "Use: $0 help"
                exit 1
                ;;
        esac
    fi
}

# Run
main "$@"
