#!/bin/bash

# Script for deploying performance optimizations
# اسکریپت برای deploy بهینه‌سازی‌های عملکرد

set -e  # Exit on error

echo "🚀 Starting Performance Optimization Deployment"
echo "=============================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored messages
print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

# Check if we're in the right directory
if [ ! -f "manage.py" ]; then
    print_error "manage.py not found. Please run this script from the project root."
    exit 1
fi

# Step 1: Backup database
echo ""
echo "Step 1: Database Backup"
echo "-----------------------"
print_warning "Creating database backup..."

DB_NAME=${POSTGRES_DB:-ingest}
DB_USER=${POSTGRES_USER:-ingest}
DB_HOST=${POSTGRES_HOST:-localhost}
BACKUP_FILE="backup_$(date +%Y%m%d_%H%M%S).sql"

pg_dump -h $DB_HOST -U $DB_USER -d $DB_NAME > $BACKUP_FILE 2>/dev/null || {
    print_warning "Could not create backup. Continuing anyway..."
}

if [ -f "$BACKUP_FILE" ]; then
    print_status "Database backed up to $BACKUP_FILE"
fi

# Step 2: Run migrations
echo ""
echo "Step 2: Running Migrations"
echo "--------------------------"
python manage.py migrate --noinput
print_status "Migrations completed"

# Step 3: Create database indexes
echo ""
echo "Step 3: Creating Database Indexes"
echo "---------------------------------"
python manage.py optimize_database --create-indexes
print_status "Database indexes created"

# Step 4: Analyze database tables
echo ""
echo "Step 4: Analyzing Database Tables"
echo "---------------------------------"
python manage.py optimize_database --analyze
print_status "Database tables analyzed"

# Step 5: Collect static files
echo ""
echo "Step 5: Collecting Static Files"
echo "-------------------------------"
python manage.py collectstatic --noinput
print_status "Static files collected"

# Step 6: Clear cache
echo ""
echo "Step 6: Clearing Cache"
echo "----------------------"
python manage.py shell -c "from django.core.cache import cache; cache.clear()"
print_status "Cache cleared"

# Step 7: Warm up cache (optional)
echo ""
echo "Step 7: Warming Up Cache"
echo "------------------------"
python manage.py shell << EOF
from django.core.cache import cache
from ingest.apps.documents.models import LegalUnit, InstrumentWork

# Cache frequently accessed data
works = InstrumentWork.objects.all()[:10]
for work in works:
    cache.set(f'work_{work.id}', work, 3600)

print(f"Cached {len(works)} works")
EOF
print_status "Cache warmed up"

# Step 8: Check system status
echo ""
echo "Step 8: System Status Check"
echo "---------------------------"

# Check Redis
redis-cli ping > /dev/null 2>&1 && print_status "Redis is running" || print_warning "Redis is not running"

# Check PostgreSQL
pg_isready -h $DB_HOST > /dev/null 2>&1 && print_status "PostgreSQL is running" || print_warning "PostgreSQL is not running"

# Check Django
python manage.py check --deploy 2>/dev/null && print_status "Django checks passed" || print_warning "Some Django checks failed"

# Step 9: Restart services
echo ""
echo "Step 9: Restarting Services"
echo "---------------------------"

# Restart Gunicorn (if using systemd)
if systemctl is-active --quiet gunicorn; then
    sudo systemctl reload gunicorn
    print_status "Gunicorn reloaded"
fi

# Restart Celery (if using systemd)
if systemctl is-active --quiet celery; then
    sudo systemctl restart celery
    print_status "Celery restarted"
fi

# Restart Celery Beat (if using systemd)
if systemctl is-active --quiet celerybeat; then
    sudo systemctl restart celerybeat
    print_status "Celery Beat restarted"
fi

# If using Docker Compose
if [ -f "docker-compose.yml" ]; then
    print_warning "Docker Compose detected. You may need to run:"
    echo "  docker-compose restart web"
    echo "  docker-compose restart celery"
    echo "  docker-compose restart celerybeat"
fi

# Final report
echo ""
echo "=============================================="
echo "🎉 Performance Optimization Deployment Complete!"
echo "=============================================="
echo ""
echo "Next steps:"
echo "1. Monitor application logs for any errors"
echo "2. Check performance metrics:"
echo "   - Response times should be < 1 second"
echo "   - Database queries should be < 20 per request"
echo "3. Run slow query check:"
echo "   python manage.py optimize_database --check-slow-queries"
echo ""
print_warning "If you encounter any issues, restore the database from: $BACKUP_FILE"
echo ""

# Performance test (optional)
read -p "Do you want to run a quick performance test? (y/n) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Running performance test..."
    python manage.py shell << EOF
import time
from django.test import Client
from django.core.cache import cache

client = Client()

# Test API endpoint
start = time.time()
response = client.get('/api/documents/legalunits/')
end = time.time()

print(f"API Response Time: {end-start:.2f} seconds")
print(f"Status Code: {response.status_code}")

# Check cache
cache_hits = cache.get('cache_hits', 0)
cache_misses = cache.get('cache_misses', 0)
total = cache_hits + cache_misses

if total > 0:
    hit_rate = (cache_hits / total) * 100
    print(f"Cache Hit Rate: {hit_rate:.1f}%")
EOF
fi

echo ""
echo "✨ Deployment script completed successfully!"
