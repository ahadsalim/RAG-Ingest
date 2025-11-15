#!/bin/bash
# Manual Deployment Script (Alternative to CI/CD)

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_header() {
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}================================${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}ℹ️  $1${NC}"
}

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   print_error "Do not run as root. Run as regular user with docker access."
   exit 1
fi

print_header "Manual Deployment Script"

# 1. Backup
print_info "Step 1: Creating backup..."
BACKUP_DIR="/srv/backups/manual-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"

docker exec deployment-db-1 pg_dump -U ingest ingest > "$BACKUP_DIR/database.sql"
tar -czf "$BACKUP_DIR/code.tar.gz" /srv/ingest/
print_success "Backup created: $BACKUP_DIR"

# 2. Pull latest changes
print_info "Step 2: Pulling latest changes from Git..."
cd /srv/ingest
git pull origin main
print_success "Code updated"

# 3. Copy files to containers
print_info "Step 3: Copying files to containers..."
for container in deployment-web-1 deployment-worker-1 deployment-beat-1; do
    echo "  → $container"
    docker cp /srv/ingest/apps $container:/app/ingest/ 2>/dev/null || true
    docker cp /srv/ingest/core $container:/app/ingest/ 2>/dev/null || true
    docker cp /srv/ingest/templates $container:/app/ingest/ 2>/dev/null || true
    docker cp /srv/ingest/api $container:/app/ingest/ 2>/dev/null || true
done
print_success "Files copied"

# 4. Run migrations
print_info "Step 4: Running migrations..."
docker exec deployment-web-1 python manage.py migrate --noinput
print_success "Migrations completed"

# 5. Restart containers
print_info "Step 5: Restarting containers..."
docker restart deployment-web-1 deployment-worker-1 deployment-beat-1
print_success "Containers restarted"

# 6. Wait for health check
print_info "Step 6: Waiting for services to be ready..."
sleep 15

# 7. Verify deployment
print_info "Step 7: Verifying deployment..."
if docker exec deployment-web-1 python manage.py check; then
    print_success "Deployment verification passed"
else
    print_error "Deployment verification failed!"
    echo ""
    echo "To rollback:"
    echo "  1. Restore database: docker exec -i deployment-db-1 psql -U ingest ingest < $BACKUP_DIR/database.sql"
    echo "  2. Restore code: tar -xzf $BACKUP_DIR/code.tar.gz -C /"
    echo "  3. Restart: docker restart deployment-web-1 deployment-worker-1 deployment-beat-1"
    exit 1
fi

# 8. Check container status
print_info "Step 8: Checking container status..."
docker ps --filter "name=deployment-" --format "table {{.Names}}\t{{.Status}}"

echo ""
print_header "Deployment Completed Successfully!"
echo ""
echo "📊 Backup location: $BACKUP_DIR"
echo "🌐 Admin panel: https://ingest.arpanet.ir/admin/"
echo ""
echo "To rollback if needed:"
echo "  cd /srv/ingest && git revert HEAD && ./deployment/manual_deploy.sh"
