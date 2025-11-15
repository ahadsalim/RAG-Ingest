# 🚀 Ingest - سیستم هوشمند مدیریت اسناد حقوقی

<div align="center">

![Python](https://img.shields.io/badge/Python-3.11-blue.svg)
![Django](https://img.shields.io/badge/Django-5.0-green.svg)
![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-blue.svg)
![Redis](https://img.shields.io/badge/Redis-7.2-red.svg)
![License](https://img.shields.io/badge/License-Private-red.svg)

**پلتفرم جامع پردازش، ذخیره‌سازی و جستجوی معنایی اسناد حقوقی با قابلیت‌های AI**

[نصب سریع](#نصب-سریع) • [ویژگی‌ها](#ویژگی‌های-کلیدی) • [مستندات](#مستندات) • [API](#api) • [پشتیبانی](#پشتیبانی)

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

### 🤖 هوش مصنوعی
- **Embedding خودکار**: تولید بردارهای معنایی با Multilingual E5
- **جستجوی معنایی**: یافتن اسناد مرتبط بر اساس مفهوم
- **Chunking هوشمند**: تقسیم خودکار اسناد به بخش‌های معنادار
- **پردازش چندزبانه**: پشتیبانی کامل فارسی و انگلیسی

### 📄 مدیریت اسناد
- **پشتیبانی فرمت‌ها**: PDF, DOCX, TXT, HTML
- **متادیتا FRBR**: استاندارد بین‌المللی توصیف اسناد
- **نسخه‌بندی**: تاریخچه کامل تغییرات
- **دسته‌بندی خودکار**: بر اساس نوع و موضوع

### 🔐 امنیت و کارایی
- **رمزنگاری End-to-End**: حفاظت از داده‌ها
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
git clone https://github.com/your-org/ingest.git /srv/ingest
cd /srv

# 2. اجرای اسکریپت نصب
chmod +x deployment/*.sh
cd deployment
./start.sh

# 3. انتخاب محیط (Development یا Production)
```

---

## 📁 ساختار پروژه

```
/srv/
├── 📱 ingest/              # کد اصلی Django
│   ├── apps/               # اپلیکیشن‌های دامنه
│   │   ├── documents/      # مدیریت اسناد
│   │   ├── embeddings/     # سیستم AI/ML
│   │   ├── accounts/       # احراز هویت
│   │   └── masterdata/     # داده‌های مرجع
│   ├── api/                # REST API endpoints
│   ├── core/               # هسته سیستم
│   ├── settings/           # تنظیمات محیط‌ها
│   └── templates/          # قالب‌های UI
├── 🚀 deployment/          # اسکریپت‌های استقرار
│   ├── docker-compose.*.yml
│   ├── backup_manager.sh
│   └── start.sh
├── 📚 Documentation/       # مستندات کامل
├── 🧪 Tests/              # تست‌های سیستم
├── 🔧 scripts/            # ابزارهای کمکی
└── 📊 .github/workflows/  # CI/CD pipelines
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
    'models': {
        'base': 'intfloat/multilingual-e5-base',
        'large': 'intfloat/multilingual-e5-large'
    },
    'chunk_size': 512,
    'overlap': 50,
    'batch_size': 32
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

### 📖 مستندات کامل
مستندات جامع پروژه در پوشه `Documentation/` قرار دارد:

- **[MASTER_GUIDE.md](Documentation/MASTER_GUIDE.md)** - راهنمای جامع سیستم
- **[EMBEDDING_SYSTEM_COMPLETE.md](Documentation/EMBEDDING_SYSTEM_COMPLETE.md)** - جزئیات سیستم AI
- **[Backup_Restore_Guide.md](Documentation/Backup_Restore_Guide.md)** - راهنمای Backup

### 🧪 تست‌ها
```bash
# اجرای همه تست‌ها
cd /srv/Tests
for test in *.py; do
    docker cp "$test" deployment-web-1:/app/
    docker exec deployment-web-1 python3 "/app/$test"
done
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
        <sub><b>نام توسعه‌دهنده</b></sub>
      </a>
      <br />
      <a href="#" title="Code">💻</a>
      <a href="#" title="Documentation">📖</a>
    </td>
  </tr>
</table>

---

## 📄 لایسنس

Copyright © 2025 Your Organization. All rights reserved.

این پروژه تحت لایسنس اختصاصی است. استفاده، کپی، تغییر یا توزیع بدون اجازه کتبی ممنوع است.

---

<div align="center">

**ساخته شده با ❤️ توسط تیم Ingest**

⭐ **اگر این پروژه مفید بود، لطفاً ستاره دهید!**

</div>
