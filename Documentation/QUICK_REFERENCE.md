# ⚡ مرجع سریع Ingest System

> دستورات و لینک‌های پرکاربرد برای مدیریت روزانه سیستم

**آخرین به‌روزرسانی:** 2024-11-07

---

## 🔗 لینک‌های مهم

| سرویس | URL | کاربری |
|-------|-----|---------|
| **Admin Panel** | https://ingest.arpanet.ir/admin/ | مدیریت کل سیستم |
| **Celery Beat Tasks** | https://ingest.arpanet.ir/admin/django_celery_beat/periodictask/ | مدیریت وظایف دوره‌ای |
| **Embeddings** | https://ingest.arpanet.ir/admin/embeddings/embedding/ | مدیریت بردارها |
| **Core Node Viewer** | https://ingest.arpanet.ir/admin/embeddings/corenodeviewer/ | تست اتصال به Core |
| **MinIO Console** | http://ingest.arpanet.ir:9001/ | مدیریت فایل‌ها |

---

## 🐳 Docker - دستورات روزانه

### وضعیت و لاگ

```bash
# بررسی وضعیت همه سرویس‌ها
docker compose ps

# لاگ همه سرویس‌ها
docker compose logs -f

# لاگ سرویس خاص
docker compose logs -f web
docker compose logs -f worker
docker compose logs -f beat
```

### Start / Stop / Restart

```bash
# راه‌اندازی
cd /srv/deployment
docker compose -f docker-compose.ingest.yml up -d

# توقف
docker compose -f docker-compose.ingest.yml down

# Restart همه
docker compose restart

# Restart سرویس خاص
docker compose restart web
docker compose restart worker
docker compose restart beat
```

### بررسی سلامت

```bash
# وضعیت container ها
docker ps --format "table {{.Names}}\t{{.Status}}"

# بررسی Django
docker compose exec web python manage.py check --deploy

# بررسی Database
docker compose exec db pg_isready -U ingest

# بررسی Redis
docker compose exec redis redis-cli ping
```

---

## 📦 Backup و Restore

### Backup سریع

```bash
cd /srv/deployment
./backup_manager.sh
# انتخاب: 1 → Create Manual Backup
# انتخاب: 1 → Full (Database + Files + Config)
```

### Restore سریع

```bash
cd /srv/deployment
./backup_manager.sh
# انتخاب: 2 → Restore from Backup
# انتخاب نوع و فایل
```

### مدیریت Backup ها

```bash
# مشاهده backup ها
ls -lh /opt/backups/ingest/

# حذف backup های قدیمی
./backup_manager.sh
# انتخاب: 5 → Cleanup Old Backups

# تست سیستم backup
./backup_manager.sh
# انتخاب: 7 → Test Backup System
```

---

## 🔧 Django - دستورات متداول

### Database

```bash
# اجرای migrations
docker compose exec web python manage.py migrate

# نمایش migrations
docker compose exec web python manage.py showmigrations

# ساخت superuser
docker compose exec web python manage.py createsuperuser

# Database shell
docker compose exec web python manage.py dbshell
```

### Shell و Debug

```bash
# Django shell
docker compose exec web python manage.py shell

# مثال تست:
docker compose exec web python manage.py shell -c "
from django_celery_beat.models import PeriodicTask
print(f'Active tasks: {PeriodicTask.objects.filter(enabled=True).count()}')
"
```

### Static Files

```bash
# Collect static files
docker compose exec web python manage.py collectstatic --noinput
```

---

## ⚙️ Celery - مدیریت Worker و Beat

### وضعیت Worker

```bash
# بررسی وضعیت
docker compose exec worker celery -A ingest status

# بررسی task های active
docker compose exec worker celery -A ingest inspect active

# بررسی task های scheduled
docker compose exec worker celery -A ingest inspect scheduled

# لیست registered tasks
docker compose exec worker celery -A ingest inspect registered
```

### مدیریت Queue

```bash
# پاک کردن queue
docker compose exec worker celery -A ingest purge

# Restart worker
docker compose restart worker
```

### Beat Schedule

```bash
# مشاهده لاگ Beat
docker compose logs -f beat | grep -i schedule

# تنظیم مجدد periodic tasks
docker compose exec web python manage.py setup_periodic_tasks
```

---

## 🤖 Embedding System

### بررسی وضعیت

```bash
# تعداد embedding ها
docker compose exec web python manage.py shell -c "
from ingest.apps.embeddings.models import Embedding
print(f'Total: {Embedding.objects.count()}')
print(f'Synced: {Embedding.objects.filter(synced_to_core=True).count()}')
"

# بررسی Core Config
docker compose exec web python manage.py shell -c "
from ingest.apps.embeddings.models import CoreConfig
config = CoreConfig.get_config()
print(f'Core URL: {config.core_api_url}')
print(f'Model: {config.embedding_model_name}')
"
```

### اجرای دستی Task ها

```bash
# Sync همه embedding های جدید
docker compose exec worker celery -A ingest call \
  ingest.apps.embeddings.tasks.auto_sync_new_embeddings

# بررسی embedding های گمشده
docker compose exec worker celery -A ingest call \
  embeddings.check_missing_embeddings

# پاکسازی embedding های orphan
docker compose exec worker celery -A ingest call \
  embeddings.cleanup_orphaned_embeddings
```

---

## 🔍 عیب‌یابی سریع

### Container مشکل دارد

```bash
# 1. بررسی لاگ
docker compose logs --tail=100 CONTAINER_NAME

# 2. بررسی منابع
docker stats

# 3. Restart
docker compose restart CONTAINER_NAME

# 4. Rebuild (اگر لازم بود)
docker compose build CONTAINER_NAME
docker compose up -d CONTAINER_NAME
```

### Worker کار نمی‌کند

```bash
# 1. بررسی اتصال Redis
docker compose exec worker redis-cli -h redis ping

# 2. بررسی registered tasks
docker compose exec worker celery -A ingest inspect registered

# 3. پاک کردن queue
docker compose exec worker celery -A ingest purge

# 4. Restart worker
docker compose restart worker
```

### Beat Task اجرا نمی‌شود

```bash
# 1. بررسی Beat در حال اجرا است؟
docker compose ps beat

# 2. بررسی task در admin enabled است؟
# https://ingest.arpanet.ir/admin/django_celery_beat/periodictask/

# 3. بررسی زمان‌بندی صحیح است؟
docker compose logs beat | grep -i schedule

# 4. اجرای دستی
# در Admin → Task → Run Now
```

### Database پر شده

```bash
# 1. بررسی حجم
docker compose exec db psql -U ingest -c "
SELECT pg_size_pretty(pg_database_size('ingest'));
"

# 2. بررسی جداول بزرگ
docker compose exec db psql -U ingest -c "
SELECT schemaname, tablename,
  pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename))
FROM pg_tables
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
LIMIT 10;
"

# 3. پاکسازی (با احتیاط!)
# - حذف لاگ‌های قدیمی
# - حذف embedding های orphan
# - VACUUM FULL
```

### MinIO مشکل دارد

```bash
# 1. بررسی وضعیت
docker compose ps minio

# 2. دسترسی به Console
# http://localhost:9001
# Username/Password: از .env

# 3. بررسی disk usage
docker compose exec minio du -sh /data
```

---

## 📊 Monitoring

### استفاده از منابع

```bash
# CPU & Memory
docker stats --no-stream

# Disk
df -h
du -sh /opt/backups/ingest/

# Database size
docker compose exec db psql -U ingest -c "
SELECT pg_database_size('ingest')/1024/1024 as size_mb;
"
```

### بررسی سلامت کلی

```bash
#!/bin/bash
echo "=== Ingest System Health Check ==="
echo ""

echo "1. Containers:"
docker compose ps | grep -E "(web|worker|beat|db|redis|minio)"

echo ""
echo "2. Django:"
docker compose exec web python manage.py check --deploy 2>&1 | head -1

echo ""
echo "3. Database:"
docker compose exec db pg_isready -U ingest

echo ""
echo "4. Redis:"
docker compose exec redis redis-cli ping

echo ""
echo "5. Celery Worker:"
docker compose exec worker celery -A ingest status 2>&1 | head -1

echo ""
echo "6. Disk:"
df -h / | tail -1

echo ""
echo "=== End of Health Check ==="
```

---

## 🆘 اقدامات اضطراری

### سیستم کاملاً خراب شده

```bash
# 1. Backup فوری (اگر امکان دارد)
cd /srv/deployment
./backup_manager.sh
# انتخاب: 1 → Create Manual Backup

# 2. Stop همه چیز
docker compose down

# 3. بررسی لاگ‌ها
docker compose logs --tail=500 > /tmp/error-logs.txt

# 4. Start مجدد
docker compose up -d

# 5. بررسی وضعیت
docker compose ps
docker compose exec web python manage.py check
```

### Restore از Backup

```bash
# 1. Stop سرویس‌ها
docker compose down

# 2. اجرای restore
cd /srv/deployment
./backup_manager.sh
# انتخاب: 2 → Restore from Backup

# 3. انتخاب آخرین backup سالم
# 4. منتظر بمانید (5-10 دقیقه)
# 5. تست سیستم
```

---

## 📝 Checklist روزانه

### صبح (شروع کار)
- [ ] بررسی وضعیت container ها: `docker compose ps`
- [ ] بررسی لاگ‌های خطا: `docker compose logs --since 24h | grep ERROR`
- [ ] بررسی disk space: `df -h`
- [ ] بررسی backup شب گذشته: `ls -lh /opt/backups/ingest/ | tail -1`

### عصر (پایان کار)
- [ ] بررسی task های failed: Admin → Celery Beat
- [ ] بررسی embedding های pending: Admin → Embeddings
- [ ] بررسی sync با Core: Admin → Core Sync Manager

### هفتگی
- [ ] پاکسازی backup های قدیمی: `./backup_manager.sh` → Cleanup
- [ ] بررسی disk usage: `du -sh /opt/backups/ingest/`
- [ ] Update dependencies (اگر لازم است)
- [ ] بررسی security updates

---

## 🔐 Credentials

**مکان ذخیره:** `/srv/.env`

**مهم‌ترین متغیرها:**
```bash
# Django
SECRET_KEY=...
DEBUG=False

# Database
POSTGRES_PASSWORD=...

# MinIO
AWS_SECRET_ACCESS_KEY=...

# Core API
CORE_API_KEY=...
```

**⚠️ هرگز credentials را commit نکنید!**

---

## 📞 کمک بیشتر

- **مستندات کامل:** `/srv/Documentation/COMPLETE_GUIDE.md`
- **Backup Manager:** `/srv/deployment/backup_manager.sh`
- **Logs:** `/var/log/ingest_backup.log`

---

**نسخه:** 1.0  
**تاریخ:** 2024-11-07
