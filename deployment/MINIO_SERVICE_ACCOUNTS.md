# راهنمای ساخت Service Account در MinIO

## دسترسی به رابط مدیریتی

1. به آدرس Console دسترسی پیدا کنید:
   ```
   https://storage.tejarat.chat
   ```

2. با اطلاعات Root وارد شوید:
   - **Username:** `BoCO7EEwQXd59s6lTVrX` (از فایل .env)
   - **Password:** `DpLVnCPXEhvj0gakhlBWhj8XsabfztsY7NLljZHk` (از فایل .env)

---

## نحوه ساخت Service Account از طریق رابط گرافیکی

### مرحله 1: ورود به بخش Access Keys

1. بعد از ورود به MinIO Console
2. از منوی سمت چپ، روی **"Access Keys"** کلیک کنید
3. دکمه **"Create access key +"** را بزنید

### مرحله 2: تنظیمات Service Account

در صفحه باز شده:

**گزینه‌های موجود:**

1. **Access Key (اختیاری):**
   - می‌توانید یک نام دلخواه بدهید
   - یا خالی بگذارید تا MinIO خودکار تولید کند

2. **Secret Key (اختیاری):**
   - می‌توانید یک رمز دلخواه بدهید
   - یا خالی بگذارید تا MinIO خودکار تولید کند

3. **Expiry (تاریخ انقضا):**
   - می‌توانید تاریخ انقضا تعیین کنید
   - یا بدون تاریخ انقضا بسازید

4. **Policy (سیاست دسترسی):**
   
   **گزینه A: استفاده از Policy از پیش تعریف شده**
   - `readonly` - فقط خواندن
   - `readwrite` - خواندن و نوشتن
   - `writeonly` - فقط نوشتن
   - `diagnostics` - برای مانیتورینگ
   - `consoleAdmin` - دسترسی کامل Console

   **گزینه B: Policy سفارشی (JSON)**
   
   مثال برای دسترسی فقط به یک bucket خاص:
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Action": [
           "s3:GetObject",
           "s3:PutObject",
           "s3:DeleteObject"
         ],
         "Resource": [
           "arn:aws:s3:::ingest-system/*"
         ]
       },
       {
         "Effect": "Allow",
         "Action": [
           "s3:ListBucket"
         ],
         "Resource": [
           "arn:aws:s3:::ingest-system"
         ]
       }
     ]
   }
   ```

   مثال برای دسترسی فقط خواندن:
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Action": [
           "s3:GetObject",
           "s3:ListBucket"
         ],
         "Resource": [
           "arn:aws:s3:::ingest-system",
           "arn:aws:s3:::ingest-system/*"
         ]
       }
     ]
   }
   ```

### مرحله 3: ذخیره و دریافت Credentials

1. روی **"Create"** کلیک کنید
2. **مهم:** یک صفحه با Access Key و Secret Key نمایش داده می‌شود
3. **حتماً این اطلاعات را کپی و ذخیره کنید** - بعد از بستن این صفحه، دیگر نمی‌توانید Secret Key را ببینید
4. می‌توانید دکمه **"Download"** را بزنید تا فایل JSON دانلود شود

---

## مدیریت Service Accounts موجود

### مشاهده لیست

1. از منوی چپ، **"Access Keys"** را انتخاب کنید
2. لیست تمام Service Accounts نمایش داده می‌شود

### ویرایش یا حذف

1. روی هر Service Account کلیک کنید
2. می‌توانید:
   - **Status** را تغییر دهید (Enable/Disable)
   - **Policy** را ویرایش کنید
   - Service Account را **حذف** کنید

---

## استفاده از Service Account در ماشین‌های دیگر

بعد از ساخت Service Account، در ماشین دیگر از این اطلاعات استفاده کنید:

### Python (boto3):
```python
import boto3

s3_client = boto3.client(
    's3',
    endpoint_url='https://s3.tejarat.chat',
    aws_access_key_id='SERVICE_ACCOUNT_ACCESS_KEY',
    aws_secret_access_key='SERVICE_ACCOUNT_SECRET_KEY',
    region_name='us-east-1'
)
```

### AWS CLI:
```bash
aws configure set aws_access_key_id SERVICE_ACCOUNT_ACCESS_KEY
aws configure set aws_secret_access_key SERVICE_ACCOUNT_SECRET_KEY
aws configure set default.s3.endpoint_url https://s3.tejarat.chat
```

### MinIO Client (mc):
```bash
mc alias set mytejarat https://s3.tejarat.chat SERVICE_ACCOUNT_ACCESS_KEY SERVICE_ACCOUNT_SECRET_KEY
mc ls mytejarat/ingest-system
```

---

## توصیه‌های امنیتی

1. ✅ **برای هر ماشین یک Service Account جداگانه بسازید**
2. ✅ **از Policy محدودکننده استفاده کنید** (کمترین دسترسی لازم)
3. ✅ **Root credentials را فقط برای مدیریت استفاده کنید**
4. ✅ **Service Accounts غیرفعال را حذف کنید**
5. ✅ **برای Service Accounts مهم، تاریخ انقضا تعیین کنید**
6. ✅ **Secret Keys را در فایل‌های محیطی (.env) ذخیره کنید، نه در کد**

---

## عیب‌یابی

### مشکل: Service Account کار نمی‌کند

1. بررسی کنید که Status آن **Enabled** باشد
2. Policy را چک کنید - شاید دسترسی کافی نداشته باشد
3. مطمئن شوید از endpoint صحیح استفاده می‌کنید: `https://s3.tejarat.chat`
4. Access Key و Secret Key را دوباره چک کنید

### مشکل: دسترسی به bucket خاص ندارد

Policy را ویرایش کنید و Resource مناسب را اضافه کنید:
```json
"Resource": [
  "arn:aws:s3:::bucket-name",
  "arn:aws:s3:::bucket-name/*"
]
```

---

## لینک‌های مفید

- MinIO Console: https://storage.tejarat.chat
- S3 API Endpoint: https://s3.tejarat.chat
- MinIO Documentation: https://min.io/docs/minio/linux/administration/identity-access-management/minio-user-management.html
