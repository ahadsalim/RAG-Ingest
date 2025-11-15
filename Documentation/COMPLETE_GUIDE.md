# 📚 راهنمای جامع سیستم Ingest

> **سیستم مدیریت اسناد حقوقی** - پلتفرم هوشمند پردازش، ذخیره‌سازی و جستجوی اسناد با قابلیت‌های AI

[![Python](https://img.shields.io/badge/Python-3.11-blue.svg)](https://python.org)
[![Django](https://img.shields.io/badge/Django-5.0-green.svg)](https://djangoproject.com)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)](https://docker.com)

**آخرین به‌روزرسانی:** 2024-11-07

---

## 📖 فهرست مطالب

1. [معرفی سیستم](#1-معرفی-سیستم)
2. [معماری](#2-معماری)
3. [راه‌اندازی](#3-راه‌اندازی)
4. [مدیریت Celery Beat](#4-مدیریت-celery-beat)
5. [Backup و Restore](#5-backup-و-restore)
6. [Admin Panel](#6-admin-panel)
7. [عیب‌یابی](#7-عیب‌یابی)

---

## 1. معرفی سیستم

### ✨ ویژگی‌های اصلی

- 📄 **مدیریت اسناد حقوقی** - آپلود، پردازش و ذخیره‌سازی
- 🤖 **Embedding هوشمند** - تبدیل متن به بردار با FastEmbed
- 🔄 **همگام‌سازی خودکار** - ارسال به سیستم مرکزی (Core)
- 🔍 **جستجوی معنایی** - استفاده از Qdrant Vector DB
- ⏰ **وظایف دوره‌ای** - مدیریت با Celery Beat
- 💾 **Backup خودکار** - پشتیبان‌گیری روزانه

### 🏗️ Stack تکنولوژی

```
Backend:       Django 5.0, Django REST Framework
Database:      PostgreSQL 16 + pgvector
Cache:         Redis 7
Queue:         Celery + Redis
Storage:       MinIO (S3-compatible)
Embedding:     FastEmbed (BAAI/bge-small-en-v1.5)
Deployment:    Docker + Nginx Proxy Manager
```

---

## 2. معماری

### 📐 نمودار کلی

```
┌─────────────────────────────────────────────────┐
│              USER / CLIENT                      │
└─────────────────┬───────────────────────────────┘
                  │
         ┌────────▼────────┐
         │  Nginx Proxy    │  Port 80/443
         │    Manager      │
         └────────┬────────┘
                  │
    ┌─────────────┼─────────────┐
    │             │             │
┌───▼───┐   ┌────▼─────┐   ┌──▼───────┐
│Django │   │  MinIO   │   │  Redis   │
│ Web   │   │ Storage  │   │  Cache   │
└───┬───┘   └──────────┘   └──────────┘
    │
    ├──────────────┬──────────────┐
    │              │              │
┌───▼────┐   ┌────▼─────┐   ┌───▼────┐
│Postgres│   │  Celery  │   │ Celery │
│   DB   │   │  Worker  │   │  Beat  │
└────────┘   └──────────┘   └────────┘
```

### 🔄 جریان داده

1. **آپلود سند** → MinIO → ذخیره فایل
2. **پردازش** → تبدیل به Chunk → ذخیره در DB
3. **Embedding** → FastEmbed → تولید بردار
4. **Sync** → ارسال به Core API → ذخیره در Qdrant
5. **جستجو** → Query → Core API → نتایج

---

## 3. راه‌اندازی

### 🚀 راه‌اندازی سریع

#### گام 1: کلون و تنظیمات
```bash
cd /srv
git clone <repository-url> ingest
cd ingest
```

#### گام 2: تنظیم Environment
```bash
cp .env.example .env
nano .env
```

**متغیرهای مهم:**
```bash
# Django
SECRET_KEY=your-secret-key-here
DEBUG=False
ALLOWED_HOSTS=ingest.arpanet.ir

# Database
POSTGRES_DB=ingest
POSTGRES_USER=ingest
POSTGRES_PASSWORD=secure-password

# MinIO
AWS_ACCESS_KEY_ID=minioadmin
AWS_SECRET_ACCESS_KEY=secure-password
AWS_STORAGE_BUCKET_NAME=advisor-docs

# Core API (اتصال از طریق Admin Panel تنظیم می‌شود)
CORE_BASE_URL=https://core.arpanet.ir
```

**نکته**: تنظیمات اتصال به سیستم Core (شامل API Key) از طریق پنل ادمین در آدرس `/admin/embeddings/coreconfig/` انجام می‌شود.

#### گام 3: راه‌اندازی با Docker
```bash
cd deployment
docker compose -f docker-compose.ingest.yml up -d

# منتظر راه‌اندازی سرویس‌ها بمانید
sleep 30

# بررسی وضعیت
docker compose ps
```

#### گام 4: مهاجرت دیتابیس
```bash
docker compose exec web python manage.py migrate
docker compose exec web python manage.py collectstatic --noinput
```

#### گام 5: ایجاد Superuser
```bash
docker compose exec web python manage.py createsuperuser
```

### 🔧 تنظیمات Celery Beat

#### ایجاد Task های دوره‌ای
```bash
docker compose exec web python manage.py setup_periodic_tasks
```

این command تمام task های زیر را ایجاد می‌کند:
- `auto-sync-new-embeddings` - هر 5 دقیقه
- `sync-metadata-changes` - هر 15 دقیقه
- `cleanup-orphaned-nodes` - روزانه 2:30 صبح
- `check-missing-embeddings-hourly` - هر ساعت
- `cleanup-orphaned-embeddings-daily` - روزانه 3 صبح

---

## 4. مدیریت Celery Beat

### ⏰ دسترسی به Admin Panel

**لینک:** `https://ingest.arpanet.ir/admin/django_celery_beat/periodictask/`

### 📋 منوهای موجود

در sidebar admin، تحت بخش **"⏰ برنامه‌ریز وظایف"**:

1. **وظایف دوره‌ای** (Periodic Tasks)
   - مدیریت اصلی task ها
   - فعال/غیرفعال کردن
   - اجرای دستی (Run Now)

2. **زمان‌بندی‌های Crontab**
   - تعریف زمان دقیق (مثلاً روزانه 3 صبح)
   - فرمت Unix Cron

3. **زمان‌بندی‌های بازه‌ای**
   - اجرا در بازه ثابت (مثلاً هر 5 دقیقه)

4. **زمان‌بندی‌های یکباره**
   - اجرا در زمان مشخص (فقط یکبار)

### 🎯 ایجاد Task جدید

#### مثال: گزارش روزانه

**گام 1:** ایجاد Crontab Schedule
- مراجعه به: Admin → زمان‌بندی‌های Crontab
- Add New:
  - Minute: `0`
  - Hour: `8`
  - Day/Month/Week: `*`

**گام 2:** ایجاد Periodic Task
- مراجعه به: Admin → وظایف دوره‌ای
- Add New:
  - Name: `daily-report`
  - Task: `myapp.tasks.generate_report`
  - Enabled: ✅
  - Crontab Schedule: (انتخاب schedule بالا)

**گام 3:** تست
```bash
# اجرای دستی
# در admin: کلیک روی task → "Run Now"

# بررسی لاگ
docker compose logs -f worker
```

### 📊 نظارت

```bash
# بررسی task های scheduled
docker compose exec worker celery -A ingest inspect scheduled

# بررسی task های فعال
docker compose exec worker celery -A ingest inspect active

# مشاهده لاگ Beat
docker compose logs -f beat
```

---

## 5. Backup و Restore

### 💾 Backup خودکار

سیستم هر شب ساعت 2 صبح backup می‌گیرد.

**محل ذخیره:**
```
/opt/backups/ingest/
├── ingest_full_20241106_020000.tar.gz
├── ingest_full_20241105_020000.tar.gz
└── ...
```

**محتوای Backup:**
```
backup.tar.gz
├── database.sql.gz           # دیتابیس PostgreSQL
├── minio_data.tar.gz         # فایل‌های MinIO
├── config/
│   ├── .env                  # تنظیمات
│   └── deployment/           # فایل‌های Docker
└── backup_info.json          # metadata
```

### 📦 Backup دستی

```bash
cd /srv/deployment
./backup_manager.sh

# انتخاب گزینه 1: Create Manual Backup
# انتخاب نوع:
#   1) Full (Database + Files + Config)
#   2) Database Only
#   3) Files Only
```

### 🔄 Restore

#### روش 1: از طریق Script

```bash
cd /srv/deployment
./backup_manager.sh

# انتخاب گزینه 2: Restore from Backup
# انتخاب نوع restore:
#   1) Full Restore (Database + MinIO)
#   2) Database Only
#   3) MinIO Files Only

# انتخاب فایل backup از لیست
# یا وارد کردن مسیر سفارشی
```

#### روش 2: دستی

```bash
# استخراج backup
tar -xzf backup.tar.gz
cd extracted/

# Restore Database
zcat database.sql.gz | \
  docker compose exec -T db \
  psql -U ingest -d ingest

# Restart services
docker compose restart
```

### ⚙️ تنظیم Backup خودکار

```bash
# اجرای wizard
./backup_manager.sh
# انتخاب گزینه 3: Setup Automated Backup

# تنظیمات:
# - ساعت اجرا (پیش‌فرض: 2 صبح)
# - مدت نگهداری (پیش‌فرض: 7 روز)
```

### 🧹 پاکسازی Backup های قدیمی

```bash
./backup_manager.sh
# انتخاب گزینه 5: Cleanup Old Backups
# وارد کردن تعداد روز (پیش‌فرض: 7)
```

---

## 6. Admin Panel

### 🔐 دسترسی

**URL:** `https://ingest.arpanet.ir/admin/`

### 📂 بخش‌های اصلی

#### 1. 📄 مدیریت اسناد
- اسناد حقوقی (LegalUnit)
- چانک‌ها (Chunks)
- سوال و جواب (QA Entries)

#### 2. 📊 اطلاعات پایه
- Work، Expression، Manifestation
- روابط اسناد

#### 3. 🗂️ جداول پایه
- نوع اسناد
- موضوعات
- دسته‌بندی‌ها

#### 4. 🔐 احراز هویت و مجوزها
- کاربران (Users)
- گروه‌ها (Groups)
- مجوزها (Permissions)

#### 5. 🤖 مدیریت بردارها
- **لیست بردارها** - مشاهده همه embedding ها
- **گزارش بردارسازی** - آمار و وضعیت
- **همگام‌سازی با Core** - مدیریت sync
- **مشاهده نود در Core** - تست دسترسی
- **تنظیمات Core** - پیکربندی اتصال

#### 6. ⏰ برنامه‌ریز وظایف
- وظایف دوره‌ای
- زمان‌بندی‌ها

#### 7. ⚙️ سیستم
- گزارش فعالیت کاربران
- تنظیمات

### 🎨 سفارشی‌سازی Admin

تمام منوها در فایل `/srv/ingest/admin.py` در متد `get_app_list()` سفارشی‌سازی شده‌اند:

```python
def get_app_list(self, request, app_label=None):
    # فارسی‌سازی نام app ها
    if app['app_label'] == 'django_celery_beat':
        app['name'] = '⏰ برنامه‌ریز وظایف'
        
        # فارسی‌سازی نام model ها
        model_names = {
            'periodic task': 'وظیفه دوره‌ای',
            'crontab': 'زمان‌بندی Crontab',
            # ...
        }
```

---

## 7. عیب‌یابی

### 🔍 بررسی وضعیت سیستم

```bash
# وضعیت container ها
docker compose ps

# لاگ همه سرویس‌ها
docker compose logs -f

# لاگ سرویس خاص
docker compose logs -f web
docker compose logs -f worker
docker compose logs -f beat
```

### ❌ مشکلات رایج

#### 1. Container مدام Restart می‌شود

**علل احتمالی:**
- پورت در حال استفاده
- حافظه ناکافی
- خطا در migrations
- اتصال به دیتابیس

**راه‌حل:**
```bash
# بررسی لاگ
docker compose logs --tail=100 container_name

# بررسی منابع
docker stats

# بررسی پورت‌ها
netstat -tulpn | grep LISTEN
```

#### 2. Celery Worker کار نمی‌کند

**بررسی:**
```bash
# وضعیت worker
docker compose exec worker celery -A ingest status

# لاگ worker
docker compose logs -f worker

# Redis در دسترس است؟
docker compose exec worker redis-cli -h redis ping
```

**راه‌حل:**
```bash
# Restart worker
docker compose restart worker

# Purge queue
docker compose exec worker celery -A ingest purge
```

#### 3. Beat Task ها اجرا نمی‌شوند

**چک‌لیست:**
```bash
# ✓ Beat container در حال اجرا است?
docker compose ps beat

# ✓ Task ها enabled هستند?
# Admin → وظایف دوره‌ای → بررسی Enabled

# ✓ زمان‌بندی صحیح است?
# Admin → Crontab Schedules → بررسی فیلدها

# ✓ لاگ Beat
docker compose logs -f beat | grep -i schedule
```

#### 4. Database Connection Error

**راه‌حل:**
```bash
# بررسی DB
docker compose exec db psql -U ingest -c "SELECT version();"

# بررسی متغیرهای محیطی
docker compose exec web printenv | grep POSTGRES

# تست اتصال
docker compose exec web python manage.py dbshell
```

#### 5. MinIO Files دسترسی ندارد

**بررسی:**
```bash
# وضعیت MinIO
docker compose ps minio

# دسترسی به Console
# http://localhost:9001
# Username/Password: از .env

# بررسی bucket
docker compose exec minio mc ls local/
```

#### 6. Core API Sync خطا می‌دهد

**بررسی:**
```bash
# تست اتصال به Core
docker compose exec web python manage.py shell -c "
from ingest.apps.embeddings.models import CoreConfig
config = CoreConfig.get_config()
print(f'URL: {config.core_api_url}')
print(f'Key: {config.core_api_key[:10]}...')
"

# تست endpoint
curl -H "X-API-Key: YOUR_KEY" \
  https://core.arpanet.ir/api/v1/health
```

### 🧪 تست سیستم

```bash
# Django check
docker compose exec web python manage.py check --deploy

# Database migrations
docker compose exec web python manage.py showmigrations

# Celery connectivity
docker compose exec worker celery -A ingest inspect ping

# Storage connectivity
docker compose exec web python manage.py shell -c "
from django.core.files.storage import default_storage
print(default_storage.exists('test.txt'))
"
```

### 📊 Monitoring

```bash
# CPU & Memory usage
docker stats

# Disk usage
df -h
du -sh /opt/backups/ingest/

# Database size
docker compose exec db psql -U ingest -c "
SELECT pg_size_pretty(pg_database_size('ingest'));
"

# Queue size
docker compose exec worker celery -A ingest inspect active | wc -l
```

---

## 📝 دستورات مفید

### Docker

```bash
# Start all services
docker compose -f docker-compose.ingest.yml up -d

# Stop all services
docker compose -f docker-compose.ingest.yml down

# Restart specific service
docker compose restart web

# View logs
docker compose logs -f web

# Execute command
docker compose exec web python manage.py shell

# Rebuild image
docker compose build web
```

### Django

```bash
# Run migrations
docker compose exec web python manage.py migrate

# Create superuser
docker compose exec web python manage.py createsuperuser

# Shell
docker compose exec web python manage.py shell

# Collect static files
docker compose exec web python manage.py collectstatic

# Database shell
docker compose exec web python manage.py dbshell
```

### Celery

```bash
# Worker status
docker compose exec worker celery -A ingest status

# Inspect scheduled tasks
docker compose exec worker celery -A ingest inspect scheduled

# Purge queue
docker compose exec worker celery -A ingest purge

# Control
docker compose exec worker celery -A ingest control shutdown
```

---

## 🔗 لینک‌های مفید

### Production
- **Admin Panel:** https://ingest.arpanet.ir/admin/
- **API:** https://ingest.arpanet.ir/api/
- **MinIO Console:** http://ingest.arpanet.ir:9001/
- **Core API:** https://core.arpanet.ir/

### دستورات سریع
```bash
# Quick status check
docker compose ps && docker compose exec web python manage.py check

# Quick restart
docker compose restart web worker beat

# Quick backup
cd /srv/deployment && ./backup_manager.sh
```

---

## 📞 پشتیبانی

در صورت بروز مشکل:

1. **بررسی لاگ‌ها:** `docker compose logs -f`
2. **بررسی مستندات:** این فایل + `/srv/Documentation/QUICK_REFERENCE.md`
3. **تست سیستم:** `python manage.py check --deploy`
4. **Backup:** همیشه قبل از تغییرات backup بگیرید

---

**نگارش:** 1.0  
**تاریخ:** 2024-11-07  
**نگهدارنده:** Ingest Development Team
