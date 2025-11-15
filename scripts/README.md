# 🔧 Scripts - اسکریپت‌های کمکی

این پوشه شامل اسکریپت‌های utility و ابزارهای کمکی پروژه است.

---

## 📋 فهرست اسکریپت‌ها

### 1️⃣ **create_models.py**
**هدف:** ایجاد EmbeddingModel های پیش‌فرض در دیتابیس

**استفاده:**
```bash
docker cp scripts/create_models.py deployment-web-1:/app/
docker exec deployment-web-1 python3 /app/create_models.py
```

**نتیجه:**
```
Base model: created (or already exists)
Large model: created (or already exists)
Default embedding models setup completed!
```

**مدل‌های ایجاد شده:**
- `intfloat/multilingual-e5-base` (768 dimensions)
- `intfloat/multilingual-e5-large` (1024 dimensions)

---

## 🚀 اضافه کردن اسکریپت جدید

Template برای اسکریپت جدید:

```python
#!/usr/bin/env python3
import os
import sys
import django

sys.path.insert(0, '/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ingest.settings.production')

django.setup()

# Your script code here

print('Script completed!')
```

---

## 💡 نکات

- همه اسکریپت‌ها باید `django.setup()` را فراخوانی کنند
- از `/app` به عنوان root path استفاده کنید
- خروجی‌های واضح برای debugging ارائه دهید
- اسکریپت‌ها را idempotent طراحی کنید (اجرای چندباره مشکل ایجاد نکند)

---

**آخرین به‌روزرسانی:** 2025-11-01
