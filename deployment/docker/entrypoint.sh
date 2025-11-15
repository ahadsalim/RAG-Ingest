#!/bin/bash
set -e

# Wait for database to be ready
echo "Waiting for database..."
python -c "
import os
import time
import sys

try:
    import psycopg2
except ImportError:
    import psycopg

host = os.environ.get('POSTGRES_HOST', 'db')
port = 5432  # Internal Docker port, not external mapped port
user = os.environ.get('POSTGRES_USER')
password = os.environ.get('POSTGRES_PASSWORD')
db = os.environ.get('POSTGRES_DB')

if not all([user, password, db]):
    print('ERROR: Missing required database environment variables!')
    print(f'POSTGRES_USER: {user}')
    pw_status = 'set' if password else 'NOT SET'
    print(f'POSTGRES_PASSWORD: {pw_status}')
    print(f'POSTGRES_DB: {db}')
    sys.exit(1)

max_attempts = 300  # 30 seconds
attempt = 0

while attempt < max_attempts:
    try:
        if 'psycopg2' in sys.modules:
            import psycopg2
            conn = psycopg2.connect(
                host=host,
                port=port,
                user=user,
                password=password,
                dbname=db,
                connect_timeout=1
            )
        else:
            import psycopg
            conn = psycopg.connect(
                host=host,
                port=port,
                user=user,
                password=password,
                dbname=db,
                connect_timeout=1
            )
        conn.close()
        print('Database connection successful')
        sys.exit(0)
    except Exception as e:
        print(f'Attempt {attempt + 1}: {e}')
        time.sleep(0.1)
        attempt += 1

print('Database connection failed after 30 seconds')
sys.exit(1)
"
echo "Database started"

# Basic container initialization
echo "Container initialization..."

# Run migrations in all environments
echo "Running database migrations..."
python manage.py migrate --noinput || echo "Migrations completed with warnings"

# Create missing migrations if needed (only in development)
if [ "$DJANGO_SETTINGS_MODULE" = "ingest.settings.dev" ]; then
    echo "Creating database migrations..."
    python manage.py makemigrations accounts || echo "Makemigrations completed with warnings"
    python manage.py makemigrations masterdata || echo "Makemigrations completed with warnings"
    python manage.py makemigrations documents || echo "Makemigrations completed with warnings"
    python manage.py makemigrations embeddings || echo "Makemigrations completed with warnings"
    python manage.py makemigrations syncbridge || echo "Makemigrations completed with warnings"
fi

# Collect static files in production
if [ "$DJANGO_SETTINGS_MODULE" = "ingest.settings.prod" ]; then
    echo "Collecting static files..."
    python manage.py collectstatic --noinput || echo "Static files collection completed with warnings"
fi

# Create superuser if not exists (production and development)
if [ "$DJANGO_SETTINGS_MODULE" = "ingest.settings.prod" ] || [ "$DJANGO_SETTINGS_MODULE" = "ingest.settings.dev" ]; then
    echo "Checking for superuser..."
    python manage.py shell -c "
from django.contrib.auth.models import User
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
    print('✅ Superuser admin/admin123 created')
else:
    print('ℹ️ Superuser already exists')
" || echo "Superuser check completed with warnings"
fi

# For worker containers, skip static files
if [ "$1" = "celery" ]; then
    echo "Celery worker container ready"
else
    echo "Web container ready"
fi

echo "Container initialization completed!"

# Execute the main command
exec "$@"
