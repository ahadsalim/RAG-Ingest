#!/bin/bash
# Script to check container status after server restart
# Usage: ./check_containers.sh

set -e

echo "🔍 بررسی وضعیت کانتینرها..."
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check Docker service
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "1️⃣  بررسی Docker Service"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if systemctl is-active --quiet docker; then
    echo -e "${GREEN}✅ Docker service: active${NC}"
else
    echo -e "${RED}❌ Docker service: inactive${NC}"
    exit 1
fi

if systemctl is-enabled --quiet docker; then
    echo -e "${GREEN}✅ Docker service: enabled (auto-start)${NC}"
else
    echo -e "${YELLOW}⚠️  Docker service: disabled${NC}"
fi
echo ""

# Check containers
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "2️⃣  بررسی کانتینرها"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

cd /srv/deployment

# Define expected containers
CONTAINERS=(
    "deployment-db-1:PostgreSQL Database"
    "deployment-redis-1:Redis Cache"
    "deployment-minio-1:MinIO Storage"
    "deployment-web-1:Django Web"
    "deployment-worker-1:Celery Worker"
    "deployment-beat-1:Celery Beat"
    "deployment-nginx-proxy-manager-1:Nginx Proxy"
)

ALL_RUNNING=true

for item in "${CONTAINERS[@]}"; do
    CONTAINER_NAME="${item%%:*}"
    CONTAINER_DESC="${item##*:}"
    
    if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        # Check if healthy (if healthcheck exists)
        HEALTH=$(docker inspect --format='{{.State.Health.Status}}' "$CONTAINER_NAME" 2>/dev/null || echo "none")
        
        if [ "$HEALTH" = "healthy" ]; then
            echo -e "${GREEN}✅ $CONTAINER_DESC ($CONTAINER_NAME): running (healthy)${NC}"
        elif [ "$HEALTH" = "none" ]; then
            echo -e "${GREEN}✅ $CONTAINER_DESC ($CONTAINER_NAME): running${NC}"
        else
            echo -e "${YELLOW}⚠️  $CONTAINER_DESC ($CONTAINER_NAME): running ($HEALTH)${NC}"
        fi
    else
        echo -e "${RED}❌ $CONTAINER_DESC ($CONTAINER_NAME): not running${NC}"
        ALL_RUNNING=false
    fi
done

echo ""

# Check website
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "3️⃣  بررسی وب‌سایت"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if curl -s -f http://localhost:8001/api/health/ > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Health endpoint: OK${NC}"
    echo -e "${GREEN}✅ Website: http://localhost:8001/${NC}"
else
    echo -e "${RED}❌ Health endpoint: Failed${NC}"
    ALL_RUNNING=false
fi

echo ""

# Summary
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 خلاصه"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ "$ALL_RUNNING" = true ]; then
    echo -e "${GREEN}✅ همه سرویس‌ها در حال اجرا هستند!${NC}"
    echo ""
    echo "🌐 Admin Panel: http://localhost:8001/admin/"
    echo "🔧 MinIO Console: http://localhost:9001/"
    echo "📊 Health Check: http://localhost:8001/api/health/"
    exit 0
else
    echo -e "${RED}❌ برخی سرویس‌ها مشکل دارند!${NC}"
    echo ""
    echo "برای بررسی logs:"
    echo "  docker logs deployment-web-1 --tail 50"
    echo "  docker logs deployment-worker-1 --tail 50"
    echo ""
    echo "برای راه‌اندازی مجدد:"
    echo "  cd /srv/deployment"
    echo "  docker compose -f docker-compose.ingest.yml up -d"
    exit 1
fi
