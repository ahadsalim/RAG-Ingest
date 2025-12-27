# 📚 مستندات جامع پروژه RAG-Ingest

**نسخه**: 2.0  
**تاریخ**: 1404/09/25 (2025-12-15)  
**وضعیت**: ✅ Production Ready

---

## 📖 فهرست مطالب

1. [معرفی پروژه](#معرفی-پروژه)
2. [معماری سیستم](#معماری-سیستم)
3. [مدل‌های داده](#مدلهای-داده)
4. [سیستم Chunking و Embedding](#سیستم-chunking-و-embedding)
5. [همگام‌سازی با Core](#همگامسازی-با-core)
6. [پنل مدیریت (Admin)](#پنل-مدیریت-admin)
7. [نصب و راه‌اندازی](#نصب-و-راهاندازی)
8. [مدیریت سیستم](#مدیریت-سیستم)
9. [API Reference](#api-reference)
10. [عیب‌یابی](#عیبیابی)

---

## 🎯 معرفی پروژه

**RAG-Ingest** یک سیستم جامع برای مدیریت و پردازش اسناد حقوقی است که شامل:

- 📄 **مدیریت اسناد حقوقی** با استاندارد FRBR
- 🔍 **Embedding و Vector Search** برای جستجوی معنایی
- 🤖 **RAG (Retrieval-Augmented Generation)** برای پاسخ‌دهی هوشمند
- 📊 **Chunking هوشمند** با پشتیبانی فارسی
- 🔄 **همگام‌سازی** با سیستم مرکزی (Core)

### تکنولوژی‌ها

| تکنولوژی | نسخه | کاربرد |
|----------|------|--------|
| Django | 5.1 | Backend Framework |
| PostgreSQL | 16 + pgvector | Database + Vector Storage |
| Redis | 7 | Cache + Message Broker |
| Celery | 5.x | Async Task Queue |
| MinIO | Latest | Object Storage (S3) |
| Docker | 24+ | Containerization |
| Gunicorn | 21+ | WSGI Server |

---

## 🏗️ معماری سیستم

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
                                   │
                        ┌──────────▼──┐
                        │    Core     │
                        │  (Qdrant)   │
                        └─────────────┘
```

### سرویس‌های Docker

| سرویس | پورت | توضیحات |
|-------|------|---------|
| web | 8000 | Django Application |
| db | 5432 | PostgreSQL Database |
| redis | 6379 | Cache & Message Broker |
| worker | - | Celery Worker |
| beat | - | Celery Beat Scheduler |
| minio | 9000/9001 | Object Storage |

---

## 📊 مدل‌های داده

### ساختار FRBR

```
InstrumentWork (سند حقوقی)
  └─ InstrumentExpression (نسخه سند)
      └─ InstrumentManifestation (انتشار سند)
          └─ LegalUnit (بند قانونی) ← LUnit (Proxy Model)
              └─ Chunk (قطعه متنی)
                  └─ Embedding (بردار معنایی)
```

### مدل‌های اصلی

#### 1. LegalUnit (بند قانونی)
```python
class LegalUnit(MPTTModel, BaseModel):
    # FRBR References
    work = ForeignKey('InstrumentWork')
    expr = ForeignKey('InstrumentExpression')
    manifestation = ForeignKey('InstrumentManifestation')
    
    # Tree Structure (MPTT)
    parent = TreeForeignKey('self')
    
    # Content
    unit_type = CharField(choices=UnitType.choices)  # باب، فصل، ماده، تبصره، ...
    number = CharField()
    content = TextField()
    order_index = CharField()
    
    # Temporal Validity
    valid_from = DateField()
    valid_to = DateField()
    
    # Relations
    vocabulary_terms = ManyToManyField(through='LegalUnitVocabularyTerm')
```

#### 2. QAEntry (پرسش و پاسخ)
```python
class QAEntry(BaseModel):
    question = TextField()
    answer = TextField()
    related_units = ManyToManyField('LegalUnit', through='QAEntryRelatedUnit')
    tags = ManyToManyField('VocabularyTerm', through='QAEntryVocabularyTerm')
```

#### 3. TextEntry (متون)
```python
class TextEntry(BaseModel):
    title = CharField()
    content = TextField()
    content_file = FileField()  # md, txt, xml, html, docx
    related_units = ManyToManyField('LegalUnit', through='TextEntryRelatedUnit')
    tags = ManyToManyField('VocabularyTerm', through='TextEntryVocabularyTerm')
```

#### 4. Chunk (قطعه متنی)
```python
class Chunk(BaseModel):
    # Source (یکی از این‌ها پر می‌شود)
    unit = ForeignKey('LegalUnit', null=True)
    qaentry = ForeignKey('QAEntry', null=True)
    textentry = ForeignKey('TextEntry', null=True)
    
    # Content
    content = TextField()
    chunk_index = PositiveIntegerField()
    token_count = PositiveIntegerField()
    
    # Embedding Relation
    embeddings = GenericRelation('Embedding')
```

#### 5. Embedding (بردار معنایی)
```python
class Embedding(BaseModel):
    content_type = ForeignKey(ContentType)
    object_id = UUIDField()
    content_object = GenericForeignKey()
    
    vector = VectorField(dimensions=1024)
    model_id = CharField()  # intfloat/multilingual-e5-large
    
    synced_to_core = BooleanField(default=False)
    core_node_id = CharField(null=True)
```

---

## 🔢 سیستم Chunking و Embedding

### تنظیمات

```python
# در .env
EMBEDDING_E5_MODEL_NAME=intfloat/multilingual-e5-large
EMBEDDING_DIMENSION=1024
DEFAULT_CHUNK_SIZE=350      # توکن
DEFAULT_CHUNK_OVERLAP=80    # توکن
```

### جریان کار

```
1. ایجاد/ویرایش LegalUnit/QAEntry/TextEntry
        ↓
2. Signal post_save
        ↓
3. Celery Task (process_*_chunks)
        ↓
4. ChunkProcessingService
   - تقسیم متن به جملات (hazm)
   - گروه‌بندی جملات به chunks
   - ایجاد Chunk objects
        ↓
5. Signal post_save برای Chunk
        ↓
6. Embedding generation
   - تولید بردار با E5 model
   - ذخیره در PostgreSQL (pgvector)
        ↓
7. Sync به Core
   - ارسال به Qdrant
   - به‌روزرسانی synced_to_core
```

### Celery Tasks

#### Periodic Tasks (زمان‌بندی خودکار)

| نام | Task | زمان‌بندی (UTC) | توضیحات |
|-----|------|-----------------|---------|
| `check-missing-embeddings-hourly` | `embeddings.check_missing_embeddings` | هر ساعت (دقیقه 0) | بررسی و تولید embedding های گمشده |
| `cleanup-orphaned-embeddings-daily` | `embeddings.cleanup_orphaned_embeddings` | 3:00 AM | پاکسازی embedding های یتیم |
| `auto-sync-new-embeddings` | `ingest.apps.embeddings.tasks.auto_sync_new_embeddings` | هر 5 دقیقه | همگام‌سازی خودکار با Core |
| `sync-metadata-changes` | `ingest.apps.embeddings.tasks.sync_changed_metadata` | هر 15 دقیقه | همگام‌سازی تغییرات metadata |
| `cleanup-orphaned-nodes` | `ingest.apps.embeddings.tasks.cleanup_orphaned_nodes` | 2:30 AM | پاکسازی نودهای یتیم در Core |
| `cleanup-old-logs-daily` | `system.cleanup_old_logs` | 4:00 AM | پاکسازی لاگ‌های قدیمی (30 روز) |
| `celery.backend_cleanup` | `celery.backend_cleanup` | 4:00 AM | پاکسازی backend سلری (سیستمی) |

#### On-Demand Tasks (فراخوانی دستی)

| Task | توضیحات |
|------|---------|
| `process_legal_unit_chunks` | Chunking برای LegalUnit |
| `process_qa_entry_chunks` | Chunking برای QAEntry |
| `process_text_entry_chunks` | Chunking برای TextEntry |
| `process_document_chunks` | Chunking برای کل سند |
| `batch_process_units` | پردازش دسته‌ای چند LegalUnit |
| `batch_generate_embeddings_for_queryset` | تولید Embedding دسته‌ای |
| `generate_embeddings_for_new_content` | تولید Embedding برای محتوای جدید |
| `full_sync_all_embeddings` | همگام‌سازی کامل با Core |
| `cleanup_duplicate_chunks` | پاکسازی chunk های تکراری |

#### System Cron Jobs (خارج از Celery)

| زمان‌بندی (UTC) | اسکریپت | توضیحات |
|-----------------|---------|---------|
| 4:00 AM, 4:00 PM | `backup_minio.sh --auto` | بکاپ MinIO به سرور ریموت |
| هر 6 ساعت | `backup_auto.sh` | بکاپ DB + .env + NPM |

---

## 🔄 همگام‌سازی با Core

### تنظیمات

```python
# در CoreConfig model
core_api_url = "https://core.tejarat.chat"
core_api_key = "your-api-key"
```

### Payload Structure

```json
{
  "node_id": "uuid",
  "content": "متن chunk",
  "vector": [0.1, 0.2, ...],
  "metadata": {
    "source_type": "legalunit|qaentry|textentry",
    "source_id": "uuid",
    "chunk_index": 0,
    "unit_type": "ماده",
    "number": "1",
    "work_title": "قانون مالیات",
    "tags": ["مالیات", "درآمد"]
  }
}
```

---

## 🖥️ پنل مدیریت (Admin)

### URL‌های اصلی

| صفحه | URL |
|------|-----|
| داشبورد | `/admin/` |
| بندهای قانونی | `/admin/documents/lunit/` |
| پرسش و پاسخ | `/admin/documents/qaentry/` |
| متون | `/admin/documents/textentry/` |
| گزارش Embedding | `/admin/embeddings/embeddingreports/` |
| مشاهده نود Core | `/admin/embeddings/corenodeviewer/` |

### LUnit Admin

- **Navigation دو مرحله‌ای**: ابتدا لیست اسناد، سپس بندهای هر سند
- **Parent Autocomplete**: جستجوی AJAX برای انتخاب والد
- **Tags Inline**: اضافه کردن برچسب با autocomplete
- **تاریخ شمسی**: نمایش تاریخ‌ها به شمسی

### گزارشات Embedding

آمار کامل شامل:
- تعداد LegalUnit، QAEntry، TextEntry
- تعداد Chunk ها به تفکیک منبع
- درصد Embedding شده
- آمار همگام‌سازی با Core

---

## 🚀 نصب و راه‌اندازی

### پیش‌نیازها

```bash
- Docker 24+
- Docker Compose 2+
- 8GB RAM (حداقل)
- 50GB Storage
```

### نصب

```bash
# 1. Clone repository
git clone <repo-url> /srv
cd /srv

# 2. تنظیم Environment
cp .env.example .env
nano .env

# 3. Build و Start
cd deployment
docker compose -f docker-compose.ingest.yml up -d

# 4. Migrate
docker exec deployment-web-1 python manage.py migrate

# 5. Create Superuser
docker exec -it deployment-web-1 python manage.py createsuperuser

# 6. Collect Static
docker exec deployment-web-1 python manage.py collectstatic --noinput
```

### دسترسی

- **Admin Panel**: https://ingest.tejarat.chat/admin/
- **API**: https://ingest.tejarat.chat/api/

---

## 🛠️ مدیریت سیستم

### دستورات مفید

```bash
# وضعیت سرویس‌ها
docker ps

# لاگ‌ها
docker logs deployment-web-1 -f
docker logs deployment-worker-1 -f

# Restart
docker compose -f docker-compose.ingest.yml restart web worker

# Shell
docker exec -it deployment-web-1 python manage.py shell

# Database
docker exec -it deployment-db-1 psql -U postgres ingest
```

### کپی فایل به Container

```bash
# بعد از تغییر کد
docker cp /srv/ingest/apps/documents/admin.py deployment-web-1:/app/ingest/apps/documents/admin.py
docker compose -f docker-compose.ingest.yml restart web worker
```

### Management Commands

```bash
# پردازش chunks
docker exec deployment-web-1 python manage.py process_chunks

# بررسی embeddings
docker exec deployment-web-1 python manage.py check_embeddings

# بهینه‌سازی دیتابیس
docker exec deployment-web-1 python manage.py optimize_database
```

---

## 📡 API Reference

### Authentication

```bash
# Get Token
curl -X POST https://ingest.tejarat.chat/api/token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "password"}'
```

### Endpoints

| Method | Endpoint | توضیحات |
|--------|----------|---------|
| GET | `/api/documents/legalunits/` | لیست بندها |
| GET | `/api/documents/legalunits/{id}/` | جزئیات بند |
| POST | `/api/search/semantic/` | جستجوی معنایی |

---

## 🔧 عیب‌یابی

### مشکلات رایج

#### 1. Embedding ایجاد نمی‌شود
```bash
# بررسی worker
docker logs deployment-worker-1 --tail 100

# بررسی task queue
docker exec deployment-web-1 python manage.py shell
>>> from celery import current_app
>>> current_app.control.inspect().active()
```

#### 2. Sync با Core کار نمی‌کند
```bash
# بررسی تنظیمات
docker exec deployment-web-1 python manage.py shell
>>> from ingest.apps.embeddings.models import CoreConfig
>>> config = CoreConfig.get_config()
>>> print(config.core_api_url, bool(config.core_api_key))
```

#### 3. صفحه Admin کند است
- بررسی تعداد queries با Django Debug Toolbar
- استفاده از `select_related` و `prefetch_related`
- فعال کردن Redis cache

---

## 📁 فایل‌های مهم

```
/srv/
├── ingest/
│   ├── apps/
│   │   ├── documents/
│   │   │   ├── models.py          # مدل‌های اصلی
│   │   │   ├── admin.py           # تنظیمات Admin
│   │   │   ├── admin_lunit.py     # LUnit Admin
│   │   │   ├── forms.py           # فرم‌ها
│   │   │   ├── signals_unified.py # سیگنال‌ها
│   │   │   └── processing/
│   │   │       ├── chunking.py    # سرویس Chunking
│   │   │       └── tasks.py       # Celery Tasks
│   │   └── embeddings/
│   │       ├── models.py          # Embedding, CoreConfig
│   │       ├── admin.py           # گزارشات
│   │       ├── signals.py         # سیگنال‌ها
│   │       └── tasks.py           # Celery Tasks
│   ├── core/
│   │   ├── sync/
│   │   │   ├── payload_builder.py # ساخت Payload
│   │   │   └── core_client.py     # ارتباط با Core
│   │   └── text_processing.py     # پردازش متن
│   └── settings/
│       ├── base.py
│       ├── prod.py
│       └── performance.py
├── deployment/
│   └── docker-compose.ingest.yml
├── .env
└── documents/
    ├── PROJECT_DOCUMENTATION.md   # این فایل
    └── AI_MEMORY.md               # حافظه AI
```

---

**تهیه‌کننده**: Cascade AI  
**تاریخ**: 2025-12-15  
**نسخه**: 2.0
