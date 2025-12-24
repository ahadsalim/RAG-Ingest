# راهنمای کامل سیستم Backup و Restore

## فهرست مطالب
- [معرفی](#معرفی)
- [پیش‌نیازها](#پیش‌نیازها)
- [ساختار فایل‌ها](#ساختار-فایلها)
- [راه‌اندازی اولیه](#راه‌اندازی-اولیه)
- [Backup خودکار](#backup-خودکار)
- [Backup دستی](#backup-دستی)
- [Backup مجزای MinIO](#backup-مجزای-minio)
- [Restore (بازیابی)](#restore-بازیابی)
- [سناریوهای رایج](#سناریوهای-رایج)

---

## معرفی

سیستم backup شامل سه اسکریپت مجزا است:

| اسکریپت | کاربرد | محتوا |
|---------|--------|-------|
| `backup_auto.sh` | خودکار (هر 6 ساعت) | DB + .env + NPM |
| `backup_manual.sh` | دستی | DB + .env + NPM |
| `backup_minio.sh` | مجزا برای MinIO | فایل‌های آپلود شده |

### چه چیزهایی backup می‌شوند؟

| مورد | توضیح | اسکریپت |
|------|-------|---------|
| **PostgreSQL Database** | داده‌های اصلی سیستم | auto, manual |
| **فایل .env** | تنظیمات و رمزها | auto, manual |
| **Nginx Proxy Manager** | تنظیمات SSL و proxy | auto, manual |
| **MinIO Data** | فایل‌های آپلود شده | minio |

---

## پیش‌نیازها

### 1. تنظیمات در فایل `.env`

```bash
# سرور backup برای ارسال خودکار backup ها
BACKUP_SERVER_HOST="monback.tejarat.chat"
BACKUP_SERVER_USER="root"
BACKUP_SERVER_PATH="/srv/backup/ingest"
BACKUP_SSH_KEY="/root/.ssh/backup_key"
BACKUP_RETENTION_DAYS=30
BACKUP_KEEP_LOCAL=false
```

### 2. ایجاد SSH Key برای سرور backup

```bash
# ایجاد کلید SSH
ssh-keygen -t ed25519 -f /root/.ssh/backup_key -N ''

# کپی کلید به سرور backup
ssh-copy-id -i /root/.ssh/backup_key root@monback.tejarat.chat

# تست اتصال
ssh -i /root/.ssh/backup_key root@monback.tejarat.chat "echo 'Connection OK'"
```

---

## ساختار فایل‌ها

```
/srv/deployment/
├── backup_auto.sh      # Backup خودکار
├── backup_manual.sh    # Backup دستی
├── backup_minio.sh     # Backup MinIO
└── BACKUP.md           # این مستند

/opt/backups/
├── ingest/             # Backup های دستی
│   ├── ingest_full_20241224_120000.tar.gz
│   └── ingest_db_20241224_120000.sql.gz
└── minio/              # Backup های MinIO
    └── minio_backup_20241224_030000.tar.gz

/var/log/
├── ingest_auto_backup.log    # لاگ backup خودکار
└── minio_backup.log          # لاگ backup MinIO
```

---

## راه‌اندازی اولیه

```bash
cd /srv/deployment

# 1. تست اتصال SSH
./backup_auto.sh --test

# 2. فعال‌سازی backup خودکار (هر 6 ساعت)
./backup_auto.sh --setup

# 3. فعال‌سازی backup خودکار MinIO (روزانه ساعت 3)
./backup_minio.sh setup

# 4. بررسی وضعیت
./backup_auto.sh --status
./backup_minio.sh status
```

---

## Backup خودکار

### دستورات

```bash
cd /srv/deployment

# اجرای دستی backup خودکار
./backup_auto.sh

# نصب cron job (هر 6 ساعت)
./backup_auto.sh --setup

# نمایش وضعیت
./backup_auto.sh --status

# تست اتصال SSH
./backup_auto.sh --test

# راهنما
./backup_auto.sh --help
```

### محتوای backup خودکار

فایل: `ingest_auto_YYYYMMDD_HHMMSS.tar.gz`

```
ingest_auto_20241224_120000/
├── database.sql.gz         # دیتابیس PostgreSQL
├── config/
│   └── .env                # فایل تنظیمات
├── npm_data.tar.gz         # تنظیمات Nginx Proxy Manager
├── npm_letsencrypt.tar.gz  # گواهی‌های SSL
└── backup_info.json        # اطلاعات backup
```

### زمان‌بندی

- **هر 6 ساعت**: 0:00, 6:00, 12:00, 18:00
- **نگهداری**: 30 روز (قابل تنظیم در .env)

### مشاهده لاگ

```bash
tail -f /var/log/ingest_auto_backup.log
```

---

## Backup دستی

### منوی تعاملی

```bash
cd /srv/deployment
./backup_manual.sh
```

### دستورات خط فرمان

```bash
cd /srv/deployment

# Backup کامل (DB + Config + NPM)
./backup_manual.sh backup full

# Backup فقط دیتابیس
./backup_manual.sh backup db

# لیست backup های موجود
./backup_manual.sh list

# راهنما
./backup_manual.sh --help
```

### محل ذخیره

```
/opt/backups/ingest/
├── ingest_full_20241224_120000.tar.gz      # Backup کامل
├── ingest_full_20241224_120000.tar.gz.sha256
├── ingest_db_20241224_140000.sql.gz        # فقط دیتابیس
└── ingest_db_20241224_140000.sql.gz.sha256
```

---

## Backup مجزای MinIO

### دستورات

```bash
cd /srv/deployment

# Backup محلی
./backup_minio.sh backup

# Backup و ارسال به سرور remote
./backup_minio.sh backup --remote

# نصب cron job (روزانه ساعت 3)
./backup_minio.sh setup

# نمایش وضعیت
./backup_minio.sh status

# لیست backup ها
./backup_minio.sh list

# پاکسازی backup های قدیمی
./backup_minio.sh cleanup 30
```

### محل ذخیره

```
/opt/backups/minio/
└── minio_backup_20241224_030000.tar.gz
```

---

## Restore (بازیابی)

### Restore دیتابیس

```bash
cd /srv/deployment

# از منوی تعاملی
./backup_manual.sh
# گزینه 4 را انتخاب کنید

# یا با خط فرمان
./backup_manual.sh restore db /opt/backups/ingest/ingest_db_20241224_120000.sql.gz
```

### Restore کامل (بدون MinIO)

```bash
cd /srv/deployment

# از منوی تعاملی
./backup_manual.sh
# گزینه 3 را انتخاب کنید

# یا با خط فرمان
./backup_manual.sh restore full /opt/backups/ingest/ingest_full_20241224_120000.tar.gz
```

### Restore MinIO

```bash
cd /srv/deployment

# از فایل محلی
./backup_minio.sh restore /opt/backups/minio/minio_backup_20241224_030000.tar.gz

# از سرور remote (تعاملی)
./backup_minio.sh restore --remote
```

### Restore کامل از سرور backup

```bash
# 1. دانلود backup از سرور remote
scp -i /root/.ssh/backup_key \
    root@monback.tejarat.chat:/srv/backup/ingest/ingest_auto_20241224_120000.tar.gz \
    /tmp/

# 2. Restore
cd /srv/deployment
./backup_manual.sh restore full /tmp/ingest_auto_20241224_120000.tar.gz

# 3. Restore MinIO جداگانه
./backup_minio.sh restore --remote
```

---

## سناریوهای رایج

### سناریو 1: راه‌اندازی سرور جدید

```bash
# 1. Clone کد از GitHub
git clone https://github.com/your-repo/ingest.git /srv

# 2. دانلود آخرین backup
scp -i /root/.ssh/backup_key \
    root@monback.tejarat.chat:/srv/backup/ingest/ingest_auto_*.tar.gz \
    /tmp/

# 3. کپی فایل .env از backup
tar -xzf /tmp/ingest_auto_*.tar.gz -C /tmp
cp /tmp/ingest_auto_*/config/.env /srv/.env

# 4. ویرایش .env برای سرور جدید (در صورت نیاز)
nano /srv/.env

# 5. راه‌اندازی Docker
cd /srv/deployment
docker compose -f docker-compose.ingest.yml --env-file ../.env up -d

# 6. Restore دیتابیس
./backup_manual.sh restore full /tmp/ingest_auto_*.tar.gz

# 7. Restore MinIO
./backup_minio.sh restore --remote
```

### سناریو 2: بازیابی بعد از خرابی دیتابیس

```bash
cd /srv/deployment

# لیست backup های موجود
./backup_manual.sh list

# Restore آخرین backup دیتابیس
./backup_manual.sh restore db /opt/backups/ingest/ingest_db_YYYYMMDD_HHMMSS.sql.gz
```

### سناریو 3: انتقال به سرور جدید

```bash
# در سرور قدیم:
cd /srv/deployment
./backup_manual.sh backup full
./backup_minio.sh backup

# کپی به سرور جدید:
scp /opt/backups/ingest/ingest_full_*.tar.gz user@new-server:/tmp/
scp /opt/backups/minio/minio_backup_*.tar.gz user@new-server:/tmp/

# در سرور جدید:
cd /srv/deployment
./backup_manual.sh restore full /tmp/ingest_full_*.tar.gz
./backup_minio.sh restore /tmp/minio_backup_*.tar.gz
```

### سناریو 4: بررسی سلامت backup

```bash
cd /srv/deployment

# وضعیت backup خودکار
./backup_auto.sh --status

# وضعیت backup MinIO
./backup_minio.sh status

# بررسی cron jobs
crontab -l

# بررسی لاگ‌ها
tail -50 /var/log/ingest_auto_backup.log
tail -50 /var/log/minio_backup.log
```

---

## نکات مهم

1. **MinIO جداست**: backup خودکار و دستی شامل MinIO نیست. از `backup_minio.sh` استفاده کنید.

2. **رمزها حفظ می‌شوند**: هنگام restore، رمزهای فعلی سرور حفظ می‌شوند.

3. **تست SSH**: قبل از فعال‌سازی backup خودکار، اتصال SSH را تست کنید:
   ```bash
   ./backup_auto.sh --test
   ```

4. **فضای دیسک**: backup های قدیمی‌تر از 30 روز به صورت خودکار پاک می‌شوند.

5. **لاگ‌ها**: همیشه لاگ‌ها را بررسی کنید:
   ```bash
   tail -f /var/log/ingest_auto_backup.log
   ```

---

## عیب‌یابی

### خطای SSH Connection Failed

```bash
# بررسی کلید SSH
ls -la /root/.ssh/backup_key

# تست اتصال دستی
ssh -i /root/.ssh/backup_key -v root@monback.tejarat.chat

# اگر کلید وجود ندارد، ایجاد کنید
ssh-keygen -t ed25519 -f /root/.ssh/backup_key -N ''
ssh-copy-id -i /root/.ssh/backup_key root@monback.tejarat.chat
```

### خطای Database Backup Failed

```bash
# بررسی وضعیت container
docker compose -f docker-compose.ingest.yml ps

# بررسی لاگ دیتابیس
docker compose -f docker-compose.ingest.yml logs db

# تست اتصال به دیتابیس
docker compose -f docker-compose.ingest.yml exec db pg_isready
```

### خطای MinIO Backup Failed

```bash
# بررسی volume
docker volume ls | grep minio

# بررسی وضعیت MinIO
docker compose -f docker-compose.ingest.yml exec minio curl -sf http://127.0.0.1:9000/minio/health/live
```

---

## تماس و پشتیبانی

در صورت بروز مشکل، لاگ‌های زیر را بررسی کنید:

```bash
# لاگ backup خودکار
cat /var/log/ingest_auto_backup.log

# لاگ backup MinIO
cat /var/log/minio_backup.log

# لاگ Docker
docker compose -f docker-compose.ingest.yml logs
```
