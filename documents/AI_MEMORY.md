# 🧠 AI Memory - RAG-Ingest Project

**آخرین به‌روزرسانی**: 1404/11/30 (2026-02-19)

---

## 📌 خلاصه پروژه

**RAG-Ingest** سیستم مدیریت اسناد حقوقی با قابلیت:
- Embedding و Vector Search
- Chunking هوشمند فارسی
- همگام‌سازی با Core (Qdrant)
- پنل مدیریت Django

---

## 🔧 تنظیمات مهم

### تنظیمات سرور (ESXi VM)
```
CPUs: 6 cores
Memory: 12 GB
Storage: 112 GB
Guest OS: Ubuntu Linux (64-bit)
VMware Tools: نصب شده
```

### Embedding
```
Model: intfloat/multilingual-e5-large
Dimension: 1024
Chunk Size: 350 tokens
Chunk Overlap: 80 tokens
Persian Numbers: تبدیل به انگلیسی
```

### بهینه‌سازی Celery Worker
```yaml
# docker-compose.ingest.yml
command: celery -A ingest worker --loglevel=info --concurrency=5 --max-tasks-per-child=50
```

```bash
# .env
EMBEDDING_BATCH_SIZE=24
```

**مزایا:**
- استفاده بهینه از 6 CPU cores
- مصرف RAM: ~8GB (67% از 12GB)
- سرعت پردازش: 2.5x سریع‌تر
- جلوگیری از memory leak با `max-tasks-per-child`

### مدل‌ها
- **LegalUnit**: بند قانونی (MPTT Tree)
- **LUnit**: Proxy Model برای LegalUnit (Admin ساده‌تر)
- **QAEntry**: پرسش و پاسخ
- **TextEntry**: متون آزاد
- **Chunk**: قطعه متنی (ForeignKey به هر سه مدل بالا)
- **Embedding**: بردار معنایی (GenericRelation)

---

## � حادثه امنیتی — 1404/11/28 (2026-02-17)

### حمله به Redis از طریق اینترنت
- **IP مهاجم**: `160.30.159.104`
- **روش**: دستور `SLAVEOF` از طریق پورت باز 6380 (بدون رمز، بدون protected-mode)
- **تأثیر**: Redis → read-only → Celery worker کرش → کلید مخرب `x` تزریق شد
- **بدافزار**: cron job برای دانلود و اجرای `j.sh` (احتمالاً crypto miner)
- **نفوذ به host**: ❌ نفوذ نکرده (محدود به Docker container)
- **مستند کامل**: `/srv/documents/SECURITY_INCIDENT_2026.md`

### اقدامات اصلاحی
1. ✅ همه پورت‌های داخلی bind به `127.0.0.1` شدند (Redis, PostgreSQL, cAdvisor, MinIO)
2. ✅ Redis hardened: `protected-mode yes` + غیرفعال کردن `SLAVEOF/REPLICAOF/DEBUG/CONFIG`
3. ✅ UFW اصلاح شد: فقط 22/80/443 از اینترنت، بقیه فقط از LAN (192.168.100.0/24)
4. ✅ `DOCKER-USER` iptables chain تنظیم شد (Docker به طور پیش‌فرض UFW را دور می‌زند!)
5. ✅ systemd service ایجاد شد: `/etc/systemd/system/docker-user-iptables.service`
6. ✅ `deployment/start.sh` بروزرسانی شد با تمام موارد امنیتی

### ⚠️ نکات حیاتی برای AI بعدی
1. **هرگز پورت Redis/PostgreSQL/MinIO را بدون `127.0.0.1` expose نکنید**
2. **Docker به طور پیش‌فرض UFW را دور می‌زند** — حتماً `DOCKER-USER` chain بررسی شود
3. **قبل از تغییر docker-compose**: پورت‌ها را بررسی کنید — فرمت صحیح: `"127.0.0.1:HOST_PORT:CONTAINER_PORT"`
4. **بررسی دوره‌ای**: `ss -tlnp | grep -v 127.0.0.1` — فقط 22, 80, 443 باید public باشند

### فایل‌های تغییر یافته
- `/srv/deployment/docker-compose.ingest.yml` — bind پورت‌ها به localhost + Redis hardening
- `/srv/deployment/start.sh` — تابع‌های `configure_firewall` و `configure_docker_security` بازنویسی شد
- `/etc/ufw/after.rules` — DOCKER-USER chain اضافه شد
- `/etc/systemd/system/docker-user-iptables.service` — سرویس جدید

---

## 🗄️ مهاجرت MinIO به سرور خارجی — 1404/11/30 (2026-02-19)

### انتقال از Local Container به External Server
- **سرور قبلی**: Docker container محلی (`deployment-minio-1`)
- **سرور جدید**: سرور خارجی `10.10.10.50:9000`
- **دلیل**: جداسازی storage از application server

### تغییرات انجام شده
1. ✅ حذف `minio` و `minio-init` از `docker-compose.ingest.yml`
2. ✅ حذف volume `minio_data`
3. ✅ بروزرسانی `deployment/start.sh`:
   - اضافه شدن `configure_minio()` برای پرسیدن آدرس سرور خارجی
   - حذف تولید کلیدهای MinIO محلی
   - حذف port check و firewall rules برای 9000/9001
   - حذف Nginx Proxy Manager config برای MinIO
   - حذف cron jobs بکاپ MinIO محلی
4. ✅ بروزرسانی Django settings:
   - `base.py`: حذف default `http://minio:9000` → فقط از `.env` خوانده می‌شود
   - `prod.py`: حذف default های داخلی (`minioadmin`)
   - `dev.py`: بروزرسانی کامنت‌ها
5. ✅ بازنویسی `deployment/backup_minio.sh`:
   - استفاده از `mc` (MinIO Client) به جای `docker volume`
   - پشتیبانی از بکاپ از سرور خارجی via S3 API
6. ✅ بروزرسانی کامنت‌ها در کد:
   - `upload_service.py`, `api/views.py`, `s3.py` → از "MinIO" به "S3 Storage"
7. ✅ حذف فایل `deployment/docker/minio-init.sh`
8. ✅ توقف و حذف container محلی `deployment-minio-1`

### مشکل FileAsset Upload و راه‌حل — 1404/11/30 (2026-02-19)

#### خطای 500 در Admin Panel
**مشکل**: خطای 500 هنگام آپلود فایل از `/admin/documents/fileasset/add/`

**علت‌های مشکل**:
1. ❌ کلیدهای دسترسی MinIO در `.env` نادرست بود → `403 Forbidden`
2. ❌ استفاده از `ServerSideEncryption='AES256'` که MinIO خارجی بدون KMS از آن پشتیبانی نمی‌کرد → `NotImplemented` error
3. ❌ `upload_service.py` برای مدل قدیمی نوشته شده بود که فیلدهای `bucket`, `object_key`, `sha256` داشت، اما مدل فعلی `FileAsset` فقط یک `FileField` ساده دارد

**راه‌حل‌های اعمال شده**:
1. ✅ بروزرسانی کلیدهای MinIO در `.env` (توسط کاربر)
2. ✅ حذف `ServerSideEncryption='AES256'` از `_upload_to_s3()`
3. ✅ بازنویسی کامل `upload_service.py`:
   ```python
   # قبل (دستی S3 upload):
   file_asset = FileAsset.objects.create(
       bucket=..., object_key=..., sha256=..., ...
   )
   
   # بعد (استفاده از Django FileField):
   file_asset = FileAsset.objects.create(
       file=uploaded_file,
       legal_unit=...,
       uploaded_by=...
   )
   ```
4. ✅ ساده‌سازی `delete_file()` - Django's storage backend خودش فایل را از S3 حذف می‌کند

### ⚠️ تصمیم امنیتی: حذف ServerSideEncryption

**سوال**: آیا حذف `ServerSideEncryption='AES256'` مشکل امنیتی ایجاد می‌کند؟

**پاسخ**: خیر، برای این پروژه مشکلی ایجاد نمی‌کند چون:
- ✅ داده‌ها **عمومی و غیرحساس** هستند (اسناد قانونی عمومی)
- ✅ سرور MinIO در **شبکه داخلی (DMZ)** قرار دارد
- ✅ دسترسی با **Access Key محدود** شده است
- ✅ برای فعال‌سازی `ServerSideEncryption` نیاز به **KMS (Key Management Service)** در MinIO است

**گزینه‌های امنیتی برای آینده** (در صورت نیاز):
1. **فعال‌سازی KMS در MinIO** → امکان استفاده از encryption at rest
2. **استفاده از HTTPS** به جای HTTP → رمزنگاری در حین انتقال
3. **Disk Encryption** در سطح OS (LUKS/BitLocker)

**نتیجه**: وضعیت فعلی (HTTP + بدون encryption at rest) برای داده‌های عمومی **قابل قبول** است.

### فایل‌های تغییر یافته
- `/srv/deployment/docker-compose.ingest.yml` — حذف minio services
- `/srv/deployment/start.sh` — configure_minio + حذف local minio setup
- `/srv/deployment/backup_minio.sh` — بازنویسی با mc client
- `/srv/ingest/settings/base.py` — حذف default endpoint
- `/srv/ingest/settings/prod.py` — حذف internal defaults
- `/srv/ingest/settings/dev.py` — بروزرسانی کامنت
- `/srv/ingest/apps/documents/upload_service.py` — ساده‌سازی کامل
- `/srv/ingest/api/views.py` — بروزرسانی health check
- `/srv/ingest/api/documents/views.py` — بروزرسانی کامنت‌ها
- `/srv/ingest/common/s3.py` — بروزرسانی docstring
- `/srv/deployment/backup_manual.sh` — بروزرسانی کامنت‌ها
- `/srv/.env` — بروزرسانی کامنت و کلیدهای MinIO

### نکات مهم برای آینده
1. **MinIO اکنون خارجی است** - هرگز local container راه‌اندازی نکنید
2. **کلیدهای MinIO در `.env`** - باید با سرور `10.10.10.50` مطابقت داشته باشند
3. **FileAsset از FileField استفاده می‌کند** - نه bucket/object_key جداگانه
4. **Django's storage backend** خودش S3 upload/delete را مدیریت می‌کند
5. **ServerSideEncryption نیاز به KMS دارد** - برای داده‌های عمومی ضروری نیست
6. **بکاپ MinIO** با `mc` client از سرور خارجی: `./backup_minio.sh backup`

---

## 📝 تغییرات اخیر (Session های قبلی)

### 1. سیستم Chunking یکپارچه
- ✅ QAEntry و TextEntry حالا chunk می‌شوند
- ✅ Chunk model دارای `unit`, `qaentry`, `textentry` ForeignKey
- ✅ سیگنال‌های post_save برای هر سه مدل

### 2. بهینه‌سازی Admin
- ✅ LegalUnit Admin: Navigation دو مرحله‌ای
- ✅ Parent Field: Autocomplete با AJAX
- ✅ حل مشکل validation فیلد parent
- ✅ حذف Core Statistics page

### 3. گزارشات Embedding
- ✅ آمار LegalUnit, QAEntry, TextEntry
- ✅ تعداد Chunks و درصد Embedding
- ✅ آمار همگام‌سازی با Core

### 4. اصلاحات فرم
- ✅ Label تاریخ: "تاریخ نسخه/تصویب"
- ✅ Parent queryset: فیلتر به manifestation
- ✅ حذف cache مشکل‌ساز

---

## 📝 تغییرات Session 1404/09/27 (2025-12-17) - Parent Autocomplete Widget

### 🐛 مشکلات و راه‌حل‌ها

#### 1. فاصله زیاد بین فیلدها (margin-bottom: 180px)
**مشکل**: فضای خالی زیاد بین فیلد content و unit_type در فرم LegalUnit
**علت**: CSS قدیمی در `change_form.html` که برای dropdown قبلی بود:
```css
.form-row:has(.field-parent) {
    margin-bottom: 180px !important;  /* این خط مشکل‌ساز بود */
}
```
**راه‌حل**: حذف `margin-bottom: 180px` چون `resultsDiv` حالا در `body` است و نیازی به فاصله نیست

#### 2. بسته شدن زودهنگام لیست autocomplete
**مشکل**: لیست والد قبل از انتخاب آیتم بسته می‌شد
**علت اصلی**: `mouseenter` و `mouseleave` روی آیتم‌ها باعث می‌شد آیتم‌ها یکی یکی حذف شوند!
```javascript
// این کد مشکل‌ساز بود:
item.addEventListener('mouseenter', function() {
    this.style.backgroundColor = '#f0f0f0';
});
item.addEventListener('mouseleave', function() {
    this.style.backgroundColor = 'white';
});
```
**راه‌حل**: حذف کامل `mouseenter`/`mouseleave` و فقط استفاده از `mousedown` برای انتخاب

#### 3. دکمه حذف والد (✕) نبود
**راه‌حل**: اضافه کردن دکمه قرمز که فقط وقتی والد انتخاب شده نمایش داده می‌شود

### 📁 فایل‌های تغییر یافته
- `/srv/ingest/apps/documents/widgets.py` - اصلاح JavaScript و اضافه کردن دکمه حذف
- `/srv/ingest/templates/admin/documents/lunit/change_form.html` - حذف margin-bottom

### ⚠️ نکات مهم برای آینده

1. **هرگز از `mouseenter`/`mouseleave` برای hover effect روی آیتم‌های dropdown استفاده نکنید** - این باعث رفتار عجیب می‌شود
2. **برای بستن dropdown با کلیک خارج**: از `blur` با تأخیر (300ms) استفاده کنید، نه `click` روی document
3. **resultsDiv در body**: چون `resultsDiv` به `body` منتقل شده، نیازی به `margin-bottom` روی parent نیست
4. **class name تداخل**: از class name یکتا مثل `parent-search-dropdown` استفاده کنید تا با CSS خارجی تداخل نداشته باشد

### 🔧 کد نهایی widget (خلاصه)
```javascript
// فقط mousedown برای انتخاب - بدون mouseenter/mouseleave
item.addEventListener('mousedown', function(e) {
    e.preventDefault();
    e.stopPropagation();
    selectParent(this.dataset.id, this.dataset.display);
});

// بستن با blur و تأخیر
searchInput.addEventListener('blur', function() {
    setTimeout(hideResults, 300);
});
```

---

## 📝 تغییرات Session 1404/09/26 (2025-12-16)

### 1. دکمه حذف برچسب در LUnit Admin
**هدف**: اضافه کردن دکمه ضربدر (✕) برای حذف سریع برچسب‌ها

**فایل‌های تغییر یافته**:
- `/srv/ingest/apps/documents/admin_lunit.py` - اضافه کردن view `delete_tags_view`
- `/srv/ingest/templates/admin/documents/lunit/change_form.html` - JavaScript برای دکمه حذف

**تغییرات در admin_lunit.py**:
```python
# در get_urls اضافه شد:
path('<path:object_id>/delete-tags/', self.admin_site.admin_view(self.delete_tags_view), name='lunit_delete_tags'),

# متد جدید delete_tags_view:
def delete_tags_view(self, request, object_id):
    # POST request با JSON body: {tag_ids: [...]}
    # حذف LegalUnitVocabularyTerm با id های داده شده
    # برگرداندن JSON response
```

**تغییرات در change_form.html**:
- تابع `deleteSingleTag(tagId, row)` برای حذف AJAX
- در DOMContentLoaded: پیدا کردن inline برچسب‌ها و اضافه کردن دکمه ✕
- دکمه در ستون "حذف؟" قرار می‌گیرد (جایگزین checkbox)
- متن توضیحی در `td.original > p` مخفی می‌شود (hidden inputs حفظ می‌شوند)

### 2. نکات مهم

**⚠️ مشکل شناخته شده**:
- وقتی برچسب با AJAX حذف می‌شود، صفحه reload می‌شود
- اگر بدون reload دکمه ذخیره زده شود، خطای validation می‌دهد
- **راه‌حل فعلی**: reload صفحه بعد از هر حذف

**⚠️ td.original**:
- این td حاوی hidden input های `id` و `legal_unit` است
- **هرگز innerHTML را خالی نکنید** - فقط `<p>` را مخفی کنید
- اگر hidden inputs حذف شوند، فرم Django خطا می‌دهد

### 3. دستورات کپی به container
```bash
# کپی template
docker cp /srv/ingest/templates/admin/documents/lunit/change_form.html deployment-web-1:/app/ingest/templates/admin/documents/lunit/change_form.html

# کپی admin_lunit.py
docker cp /srv/ingest/apps/documents/admin_lunit.py deployment-web-1:/app/ingest/apps/documents/admin_lunit.py

# restart برای اعمال تغییرات template
docker restart deployment-web-1
```

### 4. ساختار HTML inline برچسب‌ها
```html
<div id="unit_vocabulary_terms-group">
  <table>
    <tbody>
      <tr class="form-row has_original" id="unit_vocabulary_terms-0">
        <td class="original">
          <p>فصل 9 > ماده 114 - نماینده (وزن: 6)</p>
          <input type="hidden" name="unit_vocabulary_terms-0-id" value="...">
          <input type="hidden" name="unit_vocabulary_terms-0-legal_unit" value="...">
        </td>
        <td class="field-vocabulary_term">...</td>
        <td class="field-weight">...</td>
        <td class="delete"><input type="checkbox" name="...-DELETE"></td>
      </tr>
    </tbody>
  </table>
</div>
```

---

## ⚠️ نکات مهم

### 1. LUnit vs LegalUnit
- **LUnit** یک Proxy Model است
- هر دو به یک جدول اشاره می‌کنند
- LUnit برای Admin ساده‌تر طراحی شده
- **هرگز rename نکنید** - ریسک بالا

### 2. بعد از تغییر کد
```bash
# کپی به container
docker cp /srv/ingest/apps/documents/admin.py deployment-web-1:/app/ingest/apps/documents/admin.py

# restart
docker compose -f docker-compose.ingest.yml restart web worker
```

### 3. فایل‌های حساس
- `/srv/ingest/apps/documents/models.py` - مدل‌های اصلی
- `/srv/ingest/apps/documents/admin.py` - تنظیمات Admin
- `/srv/ingest/apps/documents/forms.py` - فرم‌ها
- `/srv/ingest/apps/documents/signals_unified.py` - سیگنال‌ها

---

## 🐛 مشکلات حل‌شده

### 1. Parent Field Validation Error
**مشکل**: "یک گزینه معتبر انتخاب کنید"
**علت**: queryset خالی یا cache شده
**راه‌حل**: 
- `formfield_for_foreignkey` در admin
- فیلتر به manifestation_id
- حذف `.all()` cache

### 2. صفحه Add کند
**علت**: load همه LegalUnit ها در parent dropdown
**راه‌حل**:
- فیلتر به manifestation
- استفاده از `.only()` برای فیلدهای لازم
- Lazy loading inlines

### 3. Embedding ایجاد نمی‌شود
**بررسی**:
```bash
docker logs deployment-worker-1 --tail 100
```
**راه‌حل**: restart worker

---

## 📊 آمار فعلی (تقریبی)

| مدل | تعداد |
|-----|-------|
| LegalUnit | ~4300 |
| QAEntry | ~500 |
| TextEntry | ~100 |
| Chunk | ~15000 |
| Embedding | ~14000 |

---

## 🔗 URL های مهم

| صفحه | URL |
|------|-----|
| Admin | `/admin/` |
| LUnit List | `/admin/documents/lunit/` |
| Embedding Reports | `/admin/embeddings/embeddingreports/` |
| Core Node Viewer | `/admin/embeddings/corenodeviewer/` |

---

## 📁 ساختار پوشه documents

```
/srv/documents/
├── PROJECT_DOCUMENTATION.md       # مستندات جامع
├── AI_MEMORY.md                   # این فایل
├── SECURITY_INCIDENT_2026.md      # 🔴 گزارش حادثه هک Redis (2026-02-17)
├── MINIO_SERVICE_ACCOUNTS.md      # راهنمای Service Account های MinIO
├── NPM_MINIO_CONFIG.md            # تنظیمات Nginx Proxy Manager برای MinIO
├── OPTIMIZATION_REPORT.md         # گزارش بهینه‌سازی
├── ToDoList.md                    # آرشیو - تحلیل performance
├── LUNIT_COMPLETE_GUIDE.md        # آرشیو - راهنمای LUnit
├── CHANGES_2025-11-22.md          # آرشیو - تغییرات
├── FIXES_2025-11-22_PARENT_FIELD.md  # آرشیو - اصلاح parent
└── LEGALUNIT_FORM_ANALYSIS.md     # آرشیو - تحلیل فرم
```

---

## 🎯 کارهای باقی‌مانده

1. ⏳ بهینه‌سازی MPTT partial rebuild
2. ⏳ Cache parent options با Redis
3. ⏳ تست‌های خودکار برای Chunking
4. ⏳ Monitoring با Prometheus

---

## 💡 نکات برای AI بعدی

1. **قبل از تغییر models.py**: همیشه migration بسازید
2. **قبل از تغییر admin.py**: فایل را کامل بخوانید
3. **برای debug**: از Django shell استفاده کنید
4. **برای تست**: فایل را به container کپی کنید
5. **LegalUnit rename**: انجام ندهید - ریسک بالا

---

**تهیه‌کننده**: Cascade AI  
**نسخه**: 1.0
