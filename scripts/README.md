# 📁 Scripts Directory

اسکریپت‌های مدیریت سیستم RAG-Ingest

---

## 🚀 اسکریپت اصلی: `manage.sh`

اسکریپت جامع مدیریت سیستم با قابلیت‌های:

- ✅ رفع مشکل حذف LegalUnit
- 🗑️ حذف LegalUnit با Work ID
- ⚡ اعمال بهینه‌سازی‌ها
- 📊 ایجاد Database Indexes
- 📈 مانیتورینگ عملکرد
- 🔄 Restart سرویس‌ها
- 📋 نمایش وضعیت سیستم
- �� راه‌اندازی کامل

### استفاده:

#### حالت منو (Interactive):
```bash
bash /srv/scripts/manage.sh
```

#### حالت Command Line:
```bash
# رفع مشکل SyncLog
bash /srv/scripts/manage.sh fix

# حذف LegalUnit
bash /srv/scripts/manage.sh delete <work_id>

# اعمال بهینه‌سازی‌ها
bash /srv/scripts/manage.sh optimize

# ایجاد Indexes
bash /srv/scripts/manage.sh index

# مانیتورینگ
bash /srv/scripts/manage.sh monitor

# Restart
bash /srv/scripts/manage.sh restart

# وضعیت
bash /srv/scripts/manage.sh status

# راه‌اندازی کامل
bash /srv/scripts/manage.sh setup

# راهنما
bash /srv/scripts/manage.sh help
```

#### مثال‌ها:
```bash
# حذف LegalUnit با Work ID
bash /srv/scripts/manage.sh delete 75a28f9c-099b-4b52-92c7-7edf7d006230

# راه‌اندازی کامل سیستم
bash /srv/scripts/manage.sh setup
```

---

## 📝 فایل‌های کمکی

### `create_models.py`
ایجاد EmbeddingModel های پیش‌فرض در دیتابیس

```bash
docker cp /srv/scripts/create_models.py deployment-web-1:/app/
docker exec deployment-web-1 python /app/create_models.py
```

---

## 📚 مستندات کامل

برای اطلاعات بیشتر:
```bash
cat /srv/Documentation/README.md
```
