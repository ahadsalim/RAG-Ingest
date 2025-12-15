# 🚀 RAG-Ingest - سیستم هوشمند مدیریت اسناد حقوقی

<div align="center">

![Version](https://img.shields.io/badge/Version-2.1-brightgreen.svg)
![Python](https://img.shields.io/badge/Python-3.11-blue.svg)
![Django](https://img.shields.io/badge/Django-5.1-green.svg)
![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16+pgvector-blue.svg)
![Redis](https://img.shields.io/badge/Redis-7-red.svg)
![License](https://img.shields.io/badge/License-Private-red.svg)

**پلتفرم جامع پردازش، Embedding و جستجوی معنایی اسناد حقوقی با RAG**

[نصب سریع](#نصب-سریع) • [ویژگی‌ها](#ویژگیهای-کلیدی) • [معماری](#معماری-سیستم) • [مستندات](#مستندات) • [API](#api)

</div>

---

## 📌 درباره پروژه

**Ingest** یک سیستم مدیریت اسناد حقوقی پیشرفته است که با استفاده از تکنیک‌های هوش مصنوعی و پردازش زبان طبیعی، امکان جستجوی معنایی، دسته‌بندی خودکار و مدیریت هوشمند اسناد را فراهم می‌کند.

### 🎯 کاربردها
- **سازمان‌های حقوقی**: مدیریت و جستجوی سریع در قوانین و مقررات
- **دفاتر وکالت**: آرشیو و بازیابی هوشمند پرونده‌ها
- **مراکز پژوهشی**: تحلیل و مقایسه اسناد حقوقی
- **نهادهای دولتی**: دیجیتالی‌سازی و دسترسی آسان به قوانین

---

## ✨ ویژگی‌های کلیدی

### 🤖 هوش مصنوعی و RAG
- **Embedding خودکار**: تولید بردارهای معنایی با `intfloat/multilingual-e5-large` (1024 بعد)
- **جستجوی معنایی**: Vector Search با pgvector و Qdrant
- **Chunking هوشمند**: تقسیم خودکار با 350 توکن و 80 overlap
- **پردازش فارسی**: استفاده از hazm برای جمله‌بندی
- **همگام‌سازی Core**: ارسال خودکار به سیستم مرکزی RAG

### 📄 مدیریت اسناد
- **ساختار FRBR**: Work → Expression → Manifestation → LegalUnit
- **انواع محتوا**: LegalUnit (بندهای قانونی)، QAEntry (پرسش و پاسخ)، TextEntry (متون)
- **نسخه‌بندی**: تاریخچه کامل با django-simple-history
- **درخت سلسله‌مراتبی**: MPTT برای ساختار قوانین (باب، فصل، ماده، تبصره)

### 🔐 امنیت و احراز هویت
- **احراز هویت OTP**: ورود با شماره موبایل و کد تایید از پیام‌رسان بله
- **احراز هویت JWT**: دسترسی امن به API
- **Backup خودکار**: پشتیبان‌گیری روزانه
- **مقیاس‌پذیری**: معماری Microservices

### 🛠️ زیرساخت مدرن
- **Containerized**: Docker و Kubernetes ready
- **CI/CD**: استقرار خودکار با GitHub Actions
- **Monitoring**: Prometheus و Grafana
- **High Availability**: Load balancing و Failover

---

## 🚀 نصب سریع

### پیش‌نیازها
```bash
# سیستم‌عامل: Ubuntu 20.04+ / Debian 11+
# RAM: حداقل 4GB (توصیه 8GB)
# Storage: حداقل 20GB
# Docker: 24.0+
```

### نصب یک دستوری
```bash
curl -fsSL https://raw.githubusercontent.com/your-org/ingest/main/install.sh | bash
```

### نصب دستی
```bash
# 1. Clone repository
git clone https://github.com/your-org/ingest.git /srv
cd /srv

# 2. اجرای اسکریپت نصب
chmod +x deployment/*.sh
cd deployment
sudo ./start.sh

# 3. دستورات اسکریپت را دنبال کنید
```

---

## 📁 ساختار پروژه

```
/srv/
├── 📱 ingest/                    # کد اصلی Django
│   ├── apps/
│   │   ├── documents/            # مدیریت اسناد و بندها
│   │   │   ├── models.py         # LegalUnit, QAEntry, TextEntry, Chunk
│   │   │   ├── admin.py          # تنظیمات Admin
│   │   │   ├── admin_lunit.py    # LUnit Admin (بهینه‌شده)
│   │   │   ├── signals_unified.py # سیگنال‌های Chunking
│   │   │   └── processing/       # سرویس Chunking
│   │   ├── embeddings/           # سیستم Embedding
│   │   │   ├── models.py         # Embedding, CoreConfig
│   │   │   ├── admin.py          # گزارشات
│   │   │   └── tasks.py          # Celery Tasks
│   │   ├── accounts/             # احراز هویت
│   │   └── masterdata/           # VocabularyTerm, Tags
│   ├── core/
│   │   ├── sync/                 # همگام‌سازی با Core
│   │   └── text_processing.py    # پردازش متن فارسی
│   └── settings/
├── 🚀 deployment/
│   └── docker-compose.ingest.yml
├── 📚 documents/                 # مستندات پروژه
│   ├── PROJECT_DOCUMENTATION.md  # مستندات جامع
│   └── AI_MEMORY.md              # حافظه AI
└── .env                          # تنظیمات محیطی
```

---

## 💻 محیط توسعه

### راه‌اندازی Local
```bash
cd /srv/deployment
./deploy_development.sh
```

### دسترسی‌ها
| سرویس | آدرس | اطلاعات ورود |
|--------|------|---------------|
| **وب‌اپ** | http://localhost:8001 | - |
| **پنل ادمین** | http://localhost:8001/admin/ | admin / admin123 |
| **MinIO** | http://localhost:9001 | minioadmin / minioadmin123 |
| **API Docs** | http://localhost:8001/api/docs/ | - |

### کار با کد
```bash
# ایجاد تغییرات
vim /srv/ingest/apps/your_app/models.py

# تست محلی
docker exec deployment-web-1 python manage.py test

# اعمال تغییرات
git add .
git commit -m "feat: your feature"
git push origin main
```

---

## 🌐 استقرار Production

### استقرار خودکار
```bash
cd /srv/deployment
./deploy_production.sh
```

### تنظیمات دامنه
1. تنظیم DNS records به IP سرور
2. اجرای Nginx Proxy Manager
3. دریافت SSL certificate
4. تنظیم reverse proxy

### مانیتورینگ
```bash
# وضعیت سرویس‌ها
docker ps
docker stats

# لاگ‌ها
docker logs -f deployment-web-1

# Health check
curl https://your-domain.com/api/health/
```

---

## 📊 API

### Authentication
```bash
# دریافت token
curl -X POST https://api.your-domain.com/token/ \
  -d "username=admin&password=yourpass"
```

### Document Operations
```python
import requests

# آپلود سند
files = {'file': open('document.pdf', 'rb')}
data = {'title': 'قانون کار', 'type': 'law'}
response = requests.post(
    'https://api.your-domain.com/documents/',
    files=files,
    data=data,
    headers={'Authorization': f'Bearer {token}'}
)

# جستجوی معنایی
response = requests.post(
    'https://api.your-domain.com/search/',
    json={'query': 'حقوق کارگران', 'limit': 10},
    headers={'Authorization': f'Bearer {token}'}
)
```

### مستندات کامل API
👉 [مشاهده Swagger UI](http://localhost:8001/api/docs/)

---

## 🔧 پیکربندی

### متغیرهای محیطی
```env
# Database
POSTGRES_DB=ingest
POSTGRES_USER=ingest
POSTGRES_PASSWORD=secure_password

# Django
SECRET_KEY=your-secret-key
DEBUG=False
ALLOWED_HOSTS=your-domain.com

# MinIO
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=secure_password

# Redis
REDIS_URL=redis://redis:6379/0

# AI/ML
EMBEDDING_MODEL=intfloat/multilingual-e5-large
CHUNK_SIZE=512
```

### تنظیمات Embedding
```python
# در settings/base.py
EMBEDDING_CONFIG = {
    'model': 'intfloat/multilingual-e5-large',
    'dimension': 1024,
    'chunk_size': 350,
    'overlap': 80,
    'batch_size': 16
}
```

---

## 📦 Backup و بازیابی

### Backup خودکار
```bash
cd /srv/deployment
./backup_manager.sh

# انتخاب گزینه 5: Setup Automated Backup
# تنظیم زمان: 02:00 AM
```

### بازیابی از Backup
```bash
./backup_manager.sh
# گزینه 2: Restore from Backup
# انتخاب فایل backup
```

---

## 🐛 عیب‌یابی

### مشکلات رایج

<details>
<summary>Container بالا نمی‌آید</summary>

```bash
# بررسی logs
docker logs deployment-web-1 --tail 50

# restart
docker restart deployment-web-1

# بررسی منابع
docker stats
```
</details>

<details>
<summary>خطای Migration</summary>

```bash
# نمایش migrations
docker exec deployment-web-1 python manage.py showmigrations

# اجرای دستی
docker exec deployment-web-1 python manage.py migrate
```
</details>

<details>
<summary>مشکل Embedding</summary>

```bash
# بررسی Celery
docker logs deployment-worker-1

# پردازش دستی
docker exec deployment-web-1 python manage.py process_embeddings
```
</details>

---

## 📚 مستندات

### 📖 مستندات اصلی
مستندات جامع پروژه در پوشه `documents/` قرار دارد:

- **[PROJECT_DOCUMENTATION.md](documents/PROJECT_DOCUMENTATION.md)** - مستندات جامع سیستم
- **[AI_MEMORY.md](documents/AI_MEMORY.md)** - حافظه AI و نکات مهم

### 🔧 دستورات مفید
```bash
# وضعیت سرویس‌ها
docker ps

# لاگ‌ها
docker logs deployment-web-1 -f
docker logs deployment-worker-1 -f

# Django Shell
docker exec -it deployment-web-1 python manage.py shell

# کپی فایل به container
docker cp /srv/ingest/apps/documents/admin.py deployment-web-1:/app/ingest/apps/documents/admin.py
docker compose -f docker-compose.ingest.yml restart web worker
```

---

## 🤝 مشارکت

ما از مشارکت شما استقبال می‌کنیم! لطفاً:

1. Fork کنید
2. Branch بسازید (`git checkout -b feature/AmazingFeature`)
3. Commit کنید (`git commit -m 'Add AmazingFeature'`)
4. Push کنید (`git push origin feature/AmazingFeature`)
5. Pull Request بفرستید

### کد استایل
- Python: PEP 8
- JavaScript: ESLint
- Commits: Conventional Commits

---

## 📞 پشتیبانی

### کانال‌های ارتباطی
- 📧 **ایمیل**: support@your-domain.com
- 💬 **Discord**: [Join Server](https://discord.gg/yourserver)
- 🐛 **Issues**: [GitHub Issues](https://github.com/your-org/ingest/issues)
- 📚 **Wiki**: [Project Wiki](https://github.com/your-org/ingest/wiki)

### منابع مفید
- [Django Documentation](https://docs.djangoproject.com/)
- [Docker Documentation](https://docs.docker.com/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)

---

## 🏆 تیم توسعه

<table>
  <tr>
    <td align="center">
      <a href="https://github.com/username">
        <img src="https://github.com/username.png" width="100px;" alt=""/>
        <br />
        <sub><b>نام توسعه‌دهنده</b> : احد شخص سلیم</sub>
      </a>
      <br />
      <a href="https://github.com/ahadsalim" title="Code">💻</a>
      <a href="https://github.com/ahadsalim" title="Documentation">📖</a>
    </td>
  </tr>
</table>

---

## 📊 آمار پروژه

| معیار | مقدار |
|-------|-------|
| **تعداد فایل‌های کد** | 219 |
| **تعداد فایل‌های Python** | 160 |
| **کل خطوط کد** | ~35,800 |
| **خطوط Python** | ~26,500 |
| **نسخه** | 2.1 |
| **آخرین به‌روزرسانی** | آذر ۱۴۰۳ |

---

## 📄 لایسنس

Copyright © 2025 Ahad Salim. All rights reserved.

این پروژه تحت لایسنس اختصاصی است. استفاده، کپی، تغییر یا توزیع بدون اجازه کتبی ممنوع است.

---

<div align="center">

**ساخته شده با ❤️ توسط تیم احد شخص سلیم**

⭐ **اگر این پروژه مفید بود، لطفاً ستاره دهید!**

</div>
