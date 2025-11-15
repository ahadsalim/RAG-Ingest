# 🧪 Ingest System Tests

> مجموعه تست‌های کامل و بهینه شده سیستم Ingest

**آخرین به‌روزرسانی:** 2024-11-07  
**نسخه:** 2.0

---

## 📋 فهرست تست‌ها

### 1. **test_auto_embedding.py** (تست سیستم Embedding خودکار)

**کاربرد:** تست کامل فرآیند خودکار chunking و embedding

**تست‌ها:**
- ✅ `test_legal_unit_auto_chunking` - تست تبدیل خودکار متن به chunk
- ✅ `test_chunk_auto_embedding` - تست تولید خودکار embedding برای chunk ها
- ✅ `test_qa_entry_auto_embedding` - تست embedding خودکار QA Entry
- ✅ `test_full_workflow` - تست کامل از ابتدا تا انتها

**اجرا:**
```bash
# با Django test framework
docker compose exec web python manage.py test ingest.tests.test_auto_embedding

# مستقیم (script mode)
docker compose exec web python /app/ingest/tests/test_auto_embedding.py
```

---

### 2. **test_core_node_fetch.py** (تست اتصال به Core API)

**کاربرد:** تست دریافت و نمایش node از Core API

**تست‌ها:**
- ✅ `test_fetch_node` - دریافت یک node از Core
- ✅ بررسی ساختار داده‌ها
- ✅ نمایش metadata و vector

**اجرا:**
```bash
# از Django shell
docker compose exec web python manage.py shell
>>> from ingest.tests.test_core_node_fetch import test_fetch_sample_node
>>> test_fetch_sample_node()

# یا با اسکریپت کمکی
docker compose exec web bash /app/ingest/tests/run_node_test.sh
```

---

### 3. **test_jalali_utils.py** (تست تبدیلات تاریخ جلالی)

**کاربرد:** تست توابع تبدیل تاریخ میلادی به جلالی

**تست‌ها:**
- ✅ `test_to_jalali_date` - تبدیل date به جلالی
- ✅ `test_to_jalali_datetime` - تبدیل datetime به جلالی
- ✅ `test_parse_jalali_date` - پارس رشته تاریخ جلالی
- ✅ `test_parse_jalali_datetime` - پارس datetime جلالی
- ✅ `test_persian_digits` - تبدیل اعداد انگلیسی به فارسی
- ✅ `test_english_digits` - تبدیل اعداد فارسی به انگلیسی
- ✅ `test_month_names` - نام ماه‌های جلالی
- ✅ `test_weekday_names` - نام روزهای هفته

**اجرا:**
```bash
docker compose exec web python manage.py test ingest.tests.test_jalali_utils
```

---

### 4. **test_jalali_forms.py** (تست فرم‌های تاریخ جلالی)

**کاربرد:** تست فیلدهای فرم با تاریخ جلالی

**تست‌ها:**
- ✅ `test_jalali_date_field` - فیلد تاریخ جلالی
- ✅ `test_jalali_datetime_field` - فیلد datetime جلالی
- ✅ `test_validation` - اعتبارسنجی ورودی
- ✅ `test_widget_rendering` - رندر widget

**اجرا:**
```bash
docker compose exec web python manage.py test ingest.tests.test_jalali_forms
```

---

### 5. **test_template_filters.py** (تست فیلترهای Template)

**کاربرد:** تست فیلترهای Django template

**تست‌ها:**
- ✅ `test_jalali_filter` - فیلتر تبدیل به جلالی
- ✅ `test_persian_number_filter` - فیلتر اعداد فارسی
- ✅ `test_truncate_filter` - فیلتر کوتاه‌سازی متن
- ✅ `test_highlight_filter` - فیلتر highlight

**اجرا:**
```bash
docker compose exec web python manage.py test ingest.tests.test_template_filters
```

---

## 🚀 اجرای همه تست‌ها

### اجرای تمام تست‌ها:
```bash
docker compose exec web python manage.py test ingest.tests
```

### اجرای با جزئیات:
```bash
docker compose exec web python manage.py test ingest.tests --verbosity=2
```

### اجرای با coverage:
```bash
docker compose exec web coverage run --source='.' manage.py test ingest.tests
docker compose exec web coverage report
docker compose exec web coverage html
```

---

## 📊 ساختار پوشه

```
ingest/tests/
├── __init__.py                   # تبدیل به Python package
├── README.md                     # این فایل
├── test_auto_embedding.py        # تست سیستم embedding خودکار ⭐
├── test_core_node_fetch.py       # تست اتصال به Core API
├── test_jalali_utils.py          # تست تبدیلات تاریخ جلالی
├── test_jalali_forms.py          # تست فرم‌های جلالی
├── test_template_filters.py      # تست فیلترهای template
└── run_node_test.sh              # اسکریپت کمکی
```

---

## 💡 نکات مهم

### قبل از اجرای تست‌ها:

1. **Database:** مطمئن شوید دیتابیس test جدا است
   ```python
   # settings/test.py
   DATABASES = {
       'default': {
           'ENGINE': 'django.db.backends.postgresql',
           'NAME': 'test_ingest',  # جداگانه
           ...
       }
   }
   ```

2. **Celery:** تست‌های embedding نیاز به Celery worker دارند
   ```bash
   docker compose ps worker  # باید Up باشد
   ```

3. **Redis:** برای صف Celery
   ```bash
   docker compose ps redis   # باید Up باشد
   ```

### بعد از تست:

1. **پاکسازی داده‌های test:**
   ```bash
   docker compose exec web python manage.py flush --noinput
   ```

2. **بررسی لاگ‌ها:**
   ```bash
   docker compose logs -f worker
   docker compose logs -f web
   ```

---

## 🔧 عیب‌یابی

### تست‌ها fail می‌شوند؟

#### 1. **Embedding تولید نمی‌شود**
```bash
# بررسی worker
docker compose logs worker | grep -i embedding

# بررسی Celery status
docker compose exec worker celery -A ingest status
```

#### 2. **Timeout در تست‌ها**
```python
# افزایش زمان انتظار در تست
time.sleep(10)  # به جای 5
```

#### 3. **Database connection error**
```bash
# بررسی دیتابیس
docker compose exec web python manage.py dbshell
```

#### 4. **ImportError**
```bash
# بررسی PYTHONPATH
docker compose exec web python -c "import sys; print('\n'.join(sys.path))"
```

---

## 📝 ایجاد تست جدید

### Template:

```python
"""
Description of the test module.
"""
from django.test import TestCase

class MyFeatureTest(TestCase):
    """Test my feature"""
    
    def setUp(self):
        """Set up test data"""
        # Create test objects
        pass
    
    def tearDown(self):
        """Clean up after test"""
        # Remove test objects
        pass
    
    def test_something(self):
        """Test specific functionality"""
        # Arrange
        # Act
        # Assert
        self.assertEqual(expected, actual)
```

### Best Practices:

1. **نام‌گذاری:**
   - فایل: `test_feature_name.py`
   - کلاس: `FeatureNameTest`
   - متد: `test_specific_behavior`

2. **ساختار:**
   - Arrange (آماده‌سازی)
   - Act (اجرا)
   - Assert (بررسی)

3. **مستقل بودن:**
   - هر تست باید مستقل باشد
   - نباید به ترتیب اجرا وابسته باشد

4. **پاکسازی:**
   - از `tearDown` استفاده کنید
   - یا از `TransactionTestCase`

---

## 📈 Coverage Report

### اجرا و نمایش:
```bash
# نصب coverage
docker compose exec web pip install coverage

# اجرای تست‌ها با coverage
docker compose exec web coverage run manage.py test ingest.tests

# نمایش گزارش
docker compose exec web coverage report

# ایجاد گزارش HTML
docker compose exec web coverage html
# سپس باز کنید: htmlcov/index.html
```

### هدف Coverage:
- **Functions:** >80%
- **Lines:** >75%
- **Branches:** >70%

---

## ✅ Checklist تست

قبل از commit:

- [ ] همه تست‌ها pass می‌شوند
- [ ] Coverage کافی است (>75%)
- [ ] تست‌های جدید برای feature جدید
- [ ] تست‌ها سریع هستند (<10 ثانیه)
- [ ] تست‌ها مستقل هستند
- [ ] README به‌روز است

---

## 🎯 خلاصه

```
📊 آمار تست‌ها:
- تعداد فایل: 6 فایل
- تست‌های واحد: 25+
- پوشش: Embedding, Core API, Jalali, Forms, Templates

🚀 اجرا:
docker compose exec web python manage.py test ingest.tests

✅ همه تست‌ها باید pass شوند
```

---

**نگهدارنده:** Ingest Development Team  
**مسیر:** `/srv/ingest/tests/`
