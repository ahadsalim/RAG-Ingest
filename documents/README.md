# 📚 مستندات پروژه RAG-Ingest

**نسخه**: 2.0  
**تاریخ**: 1403/08/28

---

## 📖 فهرست مطالب

1. [معرفی پروژه](#معرفی-پروژه)
2. [معماری سیستم](#معماری-سیستم)
3. [نصب و راه‌اندازی](#نصب-و-راهاندازی)
4. [بهینه‌سازی‌های اعمال شده](#بهینهسازیهای-اعمال-شده)
5. [مدیریت سیستم](#مدیریت-سیستم)
6. [حل مشکلات رایج](#حل-مشکلات-رایج)
7. [API Reference](#api-reference)
8. [تست‌ها](#تستها)

---

## 🎯 معرفی پروژه

**RAG-Ingest** یک سیستم جامع برای:
- 📄 مدیریت اسناد حقوقی (FRBR Model)
- 🔍 Embedding و Vector Search
- 🤖 RAG (Retrieval-Augmented Generation)
- 📊 مدیریت Chunks و Metadata

### تکنولوژی‌ها:
- **Backend**: Django 5.1, Django REST Framework
- **Database**: PostgreSQL 16 + pgvector
- **Cache**: Redis 7
- **Storage**: MinIO (S3-compatible)
- **Queue**: Celery + Redis
- **Web Server**: Gunicorn + Nginx
- **Containerization**: Docker + Docker Compose

---

## 🏗️ معماری سیستم

### ساختار کلی:

```
┌─────────────────────────────────────────────────────────┐
│                    Nginx Proxy Manager                  │
│              (SSL, Caching, Compression)                │
└────────────────────┬────────────────────────────────────┘
                     │
         ┌───────────┴───────────┐
         │                       │
    ┌────▼─────┐          ┌─────▼──────┐
    │   Web    │          │   Static   │
    │ Gunicorn │          │   Files    │
    │ 4w + 4t  │          │ (Whitenoise)│
    └────┬─────┘          └────────────┘
         │
    ┌────┴──────────────────────────┐
    │                               │
┌───▼────┐  ┌────────┐  ┌────────┐ │
│  DB    │  │ Redis  │  │ MinIO  │ │
│ PG+vec │  │ Cache  │  │   S3   │ │
└────────┘  └────────┘  └────────┘ │
                                   │
                        ┌──────────▼──┐
                        │   Celery    │
                        │ Worker+Beat │
                        └─────────────┘
```

### مدل‌های اصلی:

```python
InstrumentWork          # سند حقوقی (FRBR Work)
  └─ InstrumentExpression    # نسخه سند (FRBR Expression)
      └─ InstrumentManifestation  # انتشار سند (FRBR Manifestation)
          └─ LegalUnit       # واحد قانونی (ماده، بند، تبصره)
              └─ Chunk       # قطعه متنی برای Embedding
                  └─ Embedding    # Vector Embedding
                  └─ SyncLog      # لاگ همگام‌سازی
```

---

## 🚀 نصب و راه‌اندازی

### پیش‌نیازها:
```bash
- Docker 24+
- Docker Compose 2+
- 8GB RAM (حداقل)
- 50GB Storage
```

### نصب:

```bash
# 1. Clone repository
git clone <repo-url>
cd RAG-Ingest

# 2. تنظیم Environment Variables
cp .env.example .env
nano .env  # ویرایش تنظیمات

# 3. Build و Start
cd deployment
docker compose -f docker-compose.ingest.yml up -d

# 4. Migrate Database
docker exec deployment-web-1 python manage.py migrate

# 5. Create Superuser
docker exec -it deployment-web-1 python manage.py createsuperuser

# 6. Collect Static Files
docker exec deployment-web-1 python manage.py collectstatic --noinput

# 7. بررسی وضعیت
docker ps
```

### دسترسی:
- **Admin Panel**: http://localhost:8001/admin/
- **API**: http://localhost:8001/api/
- **API Docs**: http://localhost:8001/api/docs/

---

## ⚡ بهینه‌سازی‌های اعمال شده

### 1. **Gunicorn Configuration**
```yaml
# docker-compose.ingest.yml
command: gunicorn ingest.wsgi:application 
  --bind 0.0.0.0:8000 
  --workers 4 
  --threads 4 
  --worker-class gthread 
  --timeout 120 
  --max-requests 1000 
  --max-requests-jitter 50
```

**نتیجه**: 16 concurrent requests (4 workers × 4 threads)

### 2. **Static Files Optimization**
```python
# settings/prod.py
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
WHITENOISE_MAX_AGE = 31536000  # 1 year
```

**نتیجه**: Compression + Long-term caching

### 3. **Database Connection Pooling**
```python
# settings/prod.py
DATABASES['default'].update({
    'CONN_MAX_AGE': 600,  # 10 minutes
    'CONN_HEALTH_CHECKS': True,
})
```

**نتیجه**: کاهش overhead اتصال به DB

### 4. **Admin Panel Optimization**
```python
# apps/documents/admin.py
class LegalUnitAdmin(MPTTModelAdmin):
    list_per_page = 50  # کاهش از 100
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # حل N+1 problem
        qs = qs.annotate(chunks_count=Count('chunks'))
        qs = qs.select_related('work', 'expr', 'manifestation', 'parent')
        return qs
```

**نتیجه**: کاهش 90% queries (از 200 به 20)

### 5. **Cache Configuration**
```python
# settings/performance.py
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://redis:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'CONNECTION_POOL_KWARGS': {'max_connections': 50}
        }
    }
}
```

### نتایج عملکرد:

| معیار | قبل | بعد | بهبود |
|-------|-----|-----|-------|
| Response Time | 18-45s | 0.002s | 99.99% |
| Queries/Page | 150-200 | 15-20 | 90% |
| CPU Usage | 87% | 12% | 86% |
| Memory | 969MB | 450MB | 54% |

---

## 🛠️ مدیریت سیستم

### اسکریپت جامع مدیریت:

```bash
# استفاده از اسکریپت manage.sh
bash /srv/scripts/manage.sh

# یا با دستورات مستقیم:
bash /srv/scripts/manage.sh <command>
```

### دستورات موجود:

#### 1. رفع مشکل SyncLog
```bash
bash /srv/scripts/manage.sh fix
```

#### 2. حذف LegalUnit
```bash
bash /srv/scripts/manage.sh delete <work_id>

# مثال:
bash /srv/scripts/manage.sh delete 75a28f9c-099b-4b52-92c7-7edf7d006230
```

#### 3. اعمال بهینه‌سازی‌ها
```bash
bash /srv/scripts/manage.sh optimize
```

#### 4. ایجاد Database Indexes
```bash
bash /srv/scripts/manage.sh index
```

#### 5. مانیتورینگ عملکرد
```bash
bash /srv/scripts/manage.sh monitor
```

#### 6. Restart سرویس‌ها
```bash
bash /srv/scripts/manage.sh restart
```

#### 7. نمایش وضعیت
```bash
bash /srv/scripts/manage.sh status
```

#### 8. راه‌اندازی کامل
```bash
bash /srv/scripts/manage.sh setup
```

---

## 🔧 حل مشکلات رایج

### 1. مشکل حذف LegalUnit

**خطا**: "امکان حذف اجزاء سند حقوقی نیست - SyncLog"

**راه‌حل**:
```bash
# روش 1: استفاده از اسکریپت
bash /srv/scripts/manage.sh delete <work_id>

# روش 2: Django Shell
docker exec deployment-web-1 python manage.py shell
>>> from ingest.apps.documents.models import LegalUnit
>>> LegalUnit.objects.filter(work_id='<work_id>').delete()
```

**علت**: Foreign key constraint بین `SyncLog` و `Chunk`  
**حل شده**: با CASCADE constraint + pre_delete signals

### 2. صفحه Admin کند است

**تشخیص**:
```bash
# تست سرعت server-side
curl -w "\nTime: %{time_total}s\n" http://localhost:8001/admin/
```

**اگر server-side سریع است (< 0.01s) اما browser کند است**:

**علت**: مشکل از Nginx Proxy یا Browser Cache  
**راه‌حل**:

1. **Nginx Proxy Manager**:
   - وارد NPM شوید
   - Proxy Host → Advanced
   - اضافه کنید:
   ```nginx
   gzip on;
   gzip_types text/css application/javascript;
   
   location /static/ {
       expires 1y;
       add_header Cache-Control "public, immutable";
   }
   ```

2. **Browser Cache**:
   - Hard Refresh: `Ctrl+Shift+R` (Windows/Linux)
   - Hard Refresh: `Cmd+Shift+R` (Mac)
   - یا Clear Browser Cache

### 3. Database Connection Errors

**خطا**: "too many connections"

**راه‌حل**:
```bash
# بررسی connections
docker exec deployment-db-1 psql -U postgres -c "SELECT count(*) FROM pg_stat_activity;"

# افزایش max_connections در PostgreSQL
docker exec deployment-db-1 psql -U postgres -c "ALTER SYSTEM SET max_connections = 200;"
docker restart deployment-db-1
```

### 4. Celery Worker مشکل دارد

**بررسی**:
```bash
# لاگ worker
docker logs deployment-worker-1 --tail 50

# Restart worker
docker restart deployment-worker-1

# بررسی tasks
docker exec deployment-web-1 python manage.py shell
>>> from celery import current_app
>>> current_app.control.inspect().active()
```

### 5. Static Files لود نمی‌شوند

**راه‌حل**:
```bash
# Collect static files
docker exec deployment-web-1 python manage.py collectstatic --noinput --clear

# بررسی
docker exec deployment-web-1 ls -la /app/staticfiles/admin/

# Restart web
docker restart deployment-web-1
```

---

## 📡 API Reference

### Authentication:
```bash
# Get Token
curl -X POST http://localhost:8001/api/token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "password"}'

# Use Token
curl http://localhost:8001/api/documents/legalunits/ \
  -H "Authorization: Bearer <token>"
```

### Endpoints:

#### LegalUnits
```bash
# List
GET /api/documents/legalunits/

# Retrieve
GET /api/documents/legalunits/{id}/

# Create
POST /api/documents/legalunits/

# Update
PUT /api/documents/legalunits/{id}/

# Delete
DELETE /api/documents/legalunits/{id}/

# Search
GET /api/documents/legalunits/?search=<query>
```

#### Chunks
```bash
# List
GET /api/documents/chunks/

# Retrieve
GET /api/documents/chunks/{id}/

# Embeddings
GET /api/documents/chunks/{id}/embeddings/
```

#### Search
```bash
# Semantic Search
POST /api/search/semantic/
{
  "query": "متن جستجو",
  "top_k": 10
}

# Hybrid Search
POST /api/search/hybrid/
{
  "query": "متن جستجو",
  "filters": {"doc_type": "law"}
}
```

---

## 🧪 تست‌ها

### اجرای تست‌ها:

```bash
# تمام تست‌ها
docker exec deployment-web-1 python manage.py test

# تست‌های عملکرد
docker exec deployment-web-1 python manage.py test tests.test_performance

# با coverage
docker exec deployment-web-1 coverage run --source='.' manage.py test
docker exec deployment-web-1 coverage report
```

### تست‌های موجود:

1. **test_performance.py**: تست‌های عملکرد
   - API response times
   - Query optimization
   - Cache functionality
   - Pagination performance
   - Bulk operations
   - Compression middleware
   - Memory usage

### نوشتن تست جدید:

```python
# tests/test_custom.py
from django.test import TestCase
from ingest.apps.documents.models import LegalUnit

class CustomTestCase(TestCase):
    def setUp(self):
        # Setup test data
        pass
    
    def test_something(self):
        # Your test
        self.assertEqual(1, 1)
```

---

## 📊 مانیتورینگ

### دستورات مفید:

```bash
# وضعیت کانتینرها
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# مصرف منابع
docker stats --no-stream

# لاگ‌ها
docker logs deployment-web-1 --tail 100 -f
docker logs deployment-worker-1 --tail 100 -f

# Database queries
docker exec deployment-web-1 python manage.py shell
>>> from django.db import connection
>>> print(connection.queries)

# Cache status
docker exec deployment-redis-1 redis-cli INFO stats

# Disk usage
docker exec deployment-db-1 du -sh /var/lib/postgresql/data
```

---

## 🔐 امنیت

### تنظیمات امنیتی:

```python
# settings/prod.py
DEBUG = False
ALLOWED_HOSTS = ['ingest.tejarat.chat', 'localhost']
CSRF_TRUSTED_ORIGINS = ['https://ingest.tejarat.chat']

# SSL
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
```

### Backup:

```bash
# Database Backup
docker exec deployment-db-1 pg_dump -U postgres ingest > backup_$(date +%Y%m%d).sql

# Restore
docker exec -i deployment-db-1 psql -U postgres ingest < backup_20231118.sql

# Media Files Backup
docker cp deployment-web-1:/app/media ./media_backup
```

---

## 📞 پشتیبانی

### لاگ‌های مهم:

```bash
# Django
docker logs deployment-web-1

# Celery
docker logs deployment-worker-1

# Nginx
docker logs deployment-nginx-proxy-manager-1

# Database
docker logs deployment-db-1
```

### دیباگ:

```bash
# Django Shell
docker exec -it deployment-web-1 python manage.py shell

# Database Shell
docker exec -it deployment-db-1 psql -U postgres ingest

# Redis CLI
docker exec -it deployment-redis-1 redis-cli
```

---

## 📚 منابع

- [Django Documentation](https://docs.djangoproject.com/)
- [DRF Documentation](https://www.django-rest-framework.org/)
- [Celery Documentation](https://docs.celeryproject.org/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [pgvector Documentation](https://github.com/pgvector/pgvector)

---

**تاریخ به‌روزرسانی**: 1403/08/28  
**نسخه**: 2.0
