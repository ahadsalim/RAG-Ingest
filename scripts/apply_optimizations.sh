#!/bin/bash

# Script to apply optimizations to running containers
# اسکریپت برای اعمال بهینه‌سازی‌ها در کانتینرهای در حال اجرا

set -e

echo "🚀 Applying Performance Optimizations to Containers"
echo "=================================================="

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Step 1: Rebuild containers with new code
echo -e "${YELLOW}Step 1: Rebuilding containers...${NC}"
cd /srv/deployment

# Stop and rebuild
docker-compose -f docker-compose.ingest.yml down
docker-compose -f docker-compose.ingest.yml build --no-cache web worker beat
docker-compose -f docker-compose.ingest.yml up -d

echo -e "${GREEN}✓ Containers rebuilt${NC}"

# Step 2: Wait for services to be healthy
echo -e "${YELLOW}Step 2: Waiting for services to be healthy...${NC}"
sleep 10

# Check health status
for service in web worker beat db redis minio; do
    if docker-compose -f docker-compose.ingest.yml ps | grep "$service" | grep -q "healthy"; then
        echo -e "${GREEN}✓ $service is healthy${NC}"
    else
        echo -e "${YELLOW}⚠ $service may not be fully ready${NC}"
    fi
done

# Step 3: Run migrations inside container
echo -e "${YELLOW}Step 3: Running migrations...${NC}"
docker exec deployment-web-1 python manage.py migrate --noinput
echo -e "${GREEN}✓ Migrations completed${NC}"

# Step 4: Create indexes
echo -e "${YELLOW}Step 4: Creating database indexes...${NC}"
docker exec deployment-web-1 python manage.py optimize_database --create-indexes
echo -e "${GREEN}✓ Indexes created${NC}"

# Step 5: Collect static files
echo -e "${YELLOW}Step 5: Collecting static files...${NC}"
docker exec deployment-web-1 python manage.py collectstatic --noinput
echo -e "${GREEN}✓ Static files collected${NC}"

# Step 6: Clear cache
echo -e "${YELLOW}Step 6: Clearing cache...${NC}"
docker exec deployment-web-1 python manage.py shell -c "from django.core.cache import cache; cache.clear()"
echo -e "${GREEN}✓ Cache cleared${NC}"

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✅ Optimizations Applied Successfully!${NC}"
echo -e "${GREEN}========================================${NC}"

echo ""
echo "📊 To monitor performance, run:"
echo "   docker exec deployment-web-1 python manage.py monitor_performance --live"

echo ""
echo "🧪 To test performance, run:"
echo "   docker exec deployment-web-1 python manage.py test tests.test_performance"
