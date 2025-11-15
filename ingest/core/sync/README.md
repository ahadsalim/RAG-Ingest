# Core Sync System با مدل Summary

این سیستم برای همگام‌سازی embeddings از Django Ingest به Core با مدل Summary metadata طراحی شده است.

## ساختار فایل‌ها

```
ingest/core/sync/
├── __init__.py
├── payload_builder.py    # ساخت payload با مدل Summary
├── sync_service.py       # سرویس همگام‌سازی
└── README.md            # این فایل
```

## مدل Summary

هر embedding با این ساختار به Core ارسال می‌شود:

```python
{
    # IDs
    "id": "uuid",
    "chunk_id": "uuid",
    "unit_id": "uuid",
    "work_id": "uuid",
    "expression_id": "uuid",
    "manifestation_id": "uuid",
    
    # Vector
    "vector": [768 floats],
    
    # Content & Structure
    "text": "متن کامل...",
    "path_label": "قانون کار > فصل اول > ماده 1",
    "unit_type": "ARTICLE",
    "unit_number": "1",
    
    # Document Info
    "work_title": "قانون کار جمهوری اسلامی ایران",
    "doc_type": "LAW",
    "urn_lex": "ir:majlis:law:1990-06-01:123",
    "language": "fa",
    "consolidation_level": "BASE",
    "expression_date": "2020-01-01",
    
    # Publication
    "publication_date": "2020-06-15",
    "official_gazette": "روزنامه رسمی",
    "gazette_issue_no": "12345",
    "source_url": "https://...",
    
    # Legal Info
    "jurisdiction": "ایران",
    "authority": "مجلس شورای اسلامی",
    
    # Validity
    "valid_from": "2020-07-01",
    "valid_to": null,
    "is_active": true,
    "in_force_from": "2020-07-01",
    "in_force_to": null,
    "repeal_status": "in_force",
    
    # Technical
    "token_count": 256,
    "overlap_prev": 50,
    "chunk_hash": "sha256...",
    
    # Embedding Metadata
    "embedding_model": "intfloat/multilingual-e5-base",
    "embedding_dimension": 768,
    "embedding_created_at": "2025-11-02T...",
    
    # Tags
    "tags": ["کار", "استخدام"],
    
    # System
    "source": "ingest",
    "content_type": "chunk",
    "created_at": "2025-11-02T...",
    "updated_at": "2025-11-02T..."
}
```

## نصب و راه‌اندازی

### 1. Migration اجرا کنید

```bash
python manage.py migrate embeddings
```

### 2. تنظیمات Core را پیکربندی کنید

در Django Admin به بخش "تنظیمات Core" بروید و موارد زیر را تنظیم کنید:

- **آدرس API Core**: مثلاً `http://localhost:7001`
- **کلید API**: API key برای احراز هویت
- **همگام‌سازی خودکار**: فعال/غیرفعال
- **تعداد رکورد در هر batch**: پیش‌فرض 100

### 3. اتصال را تست کنید

در صفحه تنظیمات Core روی دکمه "Test Connection" کلیک کنید.

## استفاده

### همگام‌سازی دستی

برای sync کردن تمام embeddings موجود:

```bash
python manage.py sync_all_to_core
```

با گزینه‌های اضافی:

```bash
# با batch size مشخص
python manage.py sync_all_to_core --batch-size 50

# Reset و sync مجدد همه
python manage.py sync_all_to_core --reset

# فقط نمایش (بدون تغییر)
python manage.py sync_all_to_core --dry-run
```

### همگام‌سازی خودکار

سیستم به صورت خودکار:
- **هر 5 دقیقه**: embeddings جدید را sync می‌کند
- **هر 15 دقیقه**: تغییرات metadata را بررسی و sync می‌کند

این کار توسط Celery Beat انجام می‌شود.

### استفاده برنامه‌نویسی

```python
from ingest.core.sync.sync_service import CoreSyncService

# ساخت service
service = CoreSyncService()

# Sync embeddings جدید
result = service.sync_new_embeddings(batch_size=100)

# Sync تغییرات metadata
result = service.sync_changed_metadata()

# Sync تمام embeddings
result = service.sync_all_embeddings()
```

## Change Tracking

سیستم به صورت خودکار تغییرات زیر را track می‌کند:

- تغییر در `LegalUnit`
- تغییر در `InstrumentWork`
- تغییر در `InstrumentExpression`
- تغییر در `InstrumentManifestation`
- تغییر در tags (vocabulary terms)
- تغییر در `QAEntry`

هنگامی که تغییری رخ می‌دهد، `metadata_hash` embedding پاک می‌شود و در sync بعدی دوباره ارسال می‌شود.

## Admin Interface

### Embedding Admin

- **List View**: نمایش وضعیت sync با رنگ‌های مختلف
  - 🟢 Synced: ارسال شده
  - 🔴 Error: خطا
  - 🟠 Pending: در انتظار
  
- **Actions**:
  - **Sync to Core**: sync دستی embeddings انتخاب شده
  - **Reset Sync Status**: reset وضعیت برای sync مجدد

### CoreConfig Admin

- **Test Connection**: تست اتصال به Core
- **Trigger Sync**: اجرای sync دستی
- **Full Sync**: sync کامل تمام embeddings
- **آمار**: نمایش تعداد sync شده، خطاها، و آخرین sync

## Celery Tasks

سه task اصلی:

1. **auto_sync_new_embeddings**: Sync embeddings جدید (هر 5 دقیقه)
2. **sync_changed_metadata**: Sync تغییرات metadata (هر 15 دقیقه)
3. **full_sync_all_embeddings**: Sync کامل (manual)

### اجرای دستی Tasks

```python
from ingest.apps.embeddings.tasks import auto_sync_new_embeddings

# اجرا در پس‌زمینه
task = auto_sync_new_embeddings.delay()

# چک کردن وضعیت
print(task.status)
print(task.result)
```

## خطایابی

### چک کردن وضعیت Sync

```python
from ingest.apps.embeddings.models import Embedding

# تعداد کل
total = Embedding.objects.count()

# تعداد sync شده
synced = Embedding.objects.filter(synced_to_core=True).count()

# تعداد با خطا
errors = Embedding.objects.exclude(sync_error='').count()

print(f"Total: {total}, Synced: {synced}, Errors: {errors}")
```

### مشاهده خطاها

```python
# گرفتن embeddings با خطا
failed = Embedding.objects.exclude(sync_error='').values('id', 'sync_error', 'sync_retry_count')

for item in failed:
    print(f"{item['id']}: {item['sync_error']} (retries: {item['sync_retry_count']})")
```

### Reset کردن خطاها

```python
# Reset embeddings با خطا
Embedding.objects.exclude(sync_error='').update(
    synced_to_core=False,
    sync_error='',
    sync_retry_count=0
)
```

## Performance

- از `select_related` و `prefetch_related` برای کاهش queries استفاده می‌شود
- Batch processing برای ارسال چندین embedding به صورت همزمان
- Transaction برای atomic updates
- Indexing روی فیلدهای `synced_to_core` و `metadata_hash`

## Security

- API Key برای احراز هویت
- HTTPS برای ارتباط امن (در production)
- Timeout برای جلوگیری از hanging requests
- Retry logic با max retries

## Monitoring

### در Admin

- آمار sync در CoreConfig Admin
- لیست embeddings با فیلتر بر اساس وضعیت sync
- نمایش آخرین خطا و زمان آخرین sync موفق

### در Logs

```python
import logging
logger = logging.getLogger('ingest.core.sync')

# لاگ‌ها در console/file
```

## API Endpoint مورد انتظار در Core

```
POST /api/v1/sync/embeddings
```

**Request Body**:
```json
{
  "embeddings": [...],
  "sync_type": "incremental"
}
```

**Response**:
```json
{
  "status": "success",
  "synced_count": 100,
  "errors": []
}
```

## Troubleshooting

### مشکل: اتصال به Core ناموفق است

- بررسی کنید Core در حال اجرا است
- IP/Port را چک کنید
- API Key را بررسی کنید
- Firewall را بررسی کنید

### مشکل: Embeddings sync نمی‌شوند

- بررسی کنید `auto_sync_enabled = True`
- بررسی کنید Celery Beat در حال اجرا است
- لاگ‌های Celery را بررسی کنید

### مشکل: خطاهای مکرر

- تعداد max_retries را افزایش دهید
- Timeout را افزایش دهید
- Batch size را کاهش دهید
