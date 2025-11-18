#!/bin/bash

# Quick script to copy optimization files to running containers
# اسکریپت سریع برای کپی فایل‌های بهینه‌سازی بدون rebuild

set -e

echo "⚡ Quick Apply: Copying optimization files to containers"
echo "======================================================="

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# List of files to copy
FILES=(
    "ingest/core/optimizations.py"
    "ingest/core/middleware.py"
    "ingest/settings/performance.py"
    "ingest/apps/documents/signals.py"
    "ingest/apps/documents/admin_optimized.py"
    "ingest/api/mixins.py"
    "ingest/apps/documents/apps.py"
    "ingest/apps/documents/management/commands/optimize_database.py"
    "ingest/apps/documents/management/commands/monitor_performance.py"
    "tests/test_performance.py"
)

# Copy files to all relevant containers
CONTAINERS=("deployment-web-1" "deployment-worker-1" "deployment-beat-1")

for container in "${CONTAINERS[@]}"; do
    echo -e "${YELLOW}Copying files to $container...${NC}"
    
    for file in "${FILES[@]}"; do
        if [ -f "/srv/$file" ]; then
            docker cp "/srv/$file" "$container:/app/$file" 2>/dev/null && \
                echo -e "  ${GREEN}✓${NC} $file" || \
                echo -e "  ${YELLOW}⚠${NC} $file (may not be needed)"
        fi
    done
done

# Update settings in containers
echo -e "${YELLOW}Updating settings...${NC}"

# Edit prod.py to import performance settings
docker exec deployment-web-1 sh -c "echo 'from .performance import *' >> /app/ingest/settings/prod.py" 2>/dev/null || true

# Restart services gracefully
echo -e "${YELLOW}Restarting services...${NC}"

# Restart gunicorn in web container
docker exec deployment-web-1 pkill -HUP gunicorn 2>/dev/null || \
    docker restart deployment-web-1

# Restart celery workers
docker restart deployment-worker-1
docker restart deployment-beat-1

echo -e "${GREEN}✓ Services restarted${NC}"

# Run quick optimizations
echo -e "${YELLOW}Running optimizations...${NC}"

# Create indexes (safe to run multiple times)
docker exec deployment-web-1 python manage.py optimize_database --create-indexes 2>/dev/null || \
    echo -e "${YELLOW}⚠ Could not create indexes (may already exist)${NC}"

# Clear cache
docker exec deployment-web-1 python manage.py shell -c "from django.core.cache import cache; cache.clear()" 2>/dev/null || \
    echo -e "${YELLOW}⚠ Could not clear cache${NC}"

echo ""
echo -e "${GREEN}================================${NC}"
echo -e "${GREEN}✅ Quick Apply Complete!${NC}"
echo -e "${GREEN}================================${NC}"

# Test if optimizations are working
echo ""
echo -e "${YELLOW}Testing optimizations...${NC}"

# Check if new files exist in container
echo "Checking files in container:"
docker exec deployment-web-1 ls -la /app/ingest/core/optimizations.py 2>/dev/null && \
    echo -e "${GREEN}✓ Optimization files are present${NC}" || \
    echo -e "${YELLOW}⚠ Some files may be missing${NC}"

# Quick performance check
echo ""
echo "Quick performance check:"
docker exec deployment-web-1 python -c "
from django.core.cache import cache
cache.set('test', 'value', 60)
result = cache.get('test')
if result == 'value':
    print('✓ Cache is working')
else:
    print('✗ Cache not working')
" 2>/dev/null || echo "⚠ Could not test cache"

echo ""
echo "📊 Monitor performance with:"
echo "   docker exec deployment-web-1 python manage.py monitor_performance"
