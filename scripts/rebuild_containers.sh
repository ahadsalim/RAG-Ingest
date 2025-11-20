#!/bin/bash

# Rebuild and restart containers with latest code changes
# استفاده: bash rebuild_containers.sh

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Rebuild Containers with New Code    ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
echo ""

cd /srv/deployment

echo -e "${YELLOW}⚠️  این عملیات containers را rebuild می‌کند${NC}"
echo -e "${YELLOW}⚠️  زمان تقریبی: 3-5 دقیقه${NC}"
echo ""
read -p "ادامه می‌دهید؟ (y/N): " confirm

if [[ ! $confirm =~ ^[Yy]$ ]]; then
    echo -e "${RED}✗ لغو شد${NC}"
    exit 0
fi

echo ""
echo -e "${BLUE}📦 Building containers...${NC}"
docker compose -f docker-compose.ingest.yml --env-file ../.env build web worker beat

echo ""
echo -e "${BLUE}🔄 Restarting services...${NC}"
docker compose -f docker-compose.ingest.yml --env-file ../.env up -d

echo ""
echo -e "${BLUE}⏳ Waiting for services to start...${NC}"
sleep 15

echo ""
echo -e "${BLUE}✅ Checking service status...${NC}"
docker ps --filter "name=deployment-" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo ""
echo -e "${GREEN}✅ Rebuild completed!${NC}"
echo ""
echo -e "${BLUE}📋 Next steps:${NC}"
echo "  1. Test LegalUnit deletion: docker exec deployment-web-1 python manage.py shell"
echo "  2. Check logs: docker logs deployment-web-1 --tail 50"
echo "  3. Monitor: bash /srv/scripts/manage.sh status"
