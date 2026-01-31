# تنظیمات Nginx Proxy Manager برای MinIO

## مشکل و راه حل

**مشکل قبلی:**
- `storage.tejarat.chat` درست کار می‌کرد (Console - پورت 9001)
- `s3.tejarat.chat` redirect می‌شد و درست کار نمی‌کرد

**راه حل:**
- پورت‌های MinIO از `127.0.0.1` binding حذف شدند
- NPM حالا می‌تواند از طریق شبکه Docker به MinIO دسترسی داشته باشد

---

## تنظیمات NPM

در Nginx Proxy Manager (http://your-server-ip:81) دو Proxy Host جداگانه ایجاد کنید:

### 1️⃣ S3 API Endpoint (برای عملیات فایل)

**Domain Names:**
```
s3.tejarat.chat
```

**Forward Hostname / IP:**
```
minio
```

**Forward Port:**
```
9000
```

**تنظیمات اضافی:**
- ✅ Cache Assets
- ✅ Block Common Exploits
- ✅ Websockets Support
- ✅ Force SSL (بعد از تنظیم SSL Certificate)

**Custom Nginx Configuration (در تب Advanced):**
```nginx
# Increase timeouts for large file uploads
client_max_body_size 1000M;
proxy_connect_timeout 600;
proxy_send_timeout 600;
proxy_read_timeout 600;
send_timeout 600;

# S3 specific headers
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
proxy_set_header Host $http_host;

# Disable buffering for streaming
proxy_buffering off;
proxy_request_buffering off;
```

**SSL Certificate:**
- Request a new SSL Certificate با Let's Encrypt
- یا از SSL Certificate موجود استفاده کنید

---

### 2️⃣ MinIO Console (رابط مدیریتی)

**Domain Names:**
```
storage.tejarat.chat
```

**Forward Hostname / IP:**
```
minio
```

**Forward Port:**
```
9001
```

**تنظیمات اضافی:**
- ✅ Cache Assets
- ✅ Block Common Exploits
- ✅ Websockets Support (مهم برای Console)
- ✅ Force SSL

**Custom Nginx Configuration (در تب Advanced):**
```nginx
# Console specific settings
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
proxy_set_header Host $http_host;

# WebSocket support for real-time updates
proxy_http_version 1.1;
proxy_set_header Upgrade $http_upgrade;
proxy_set_header Connection "upgrade";

# Timeouts
proxy_connect_timeout 600;
proxy_send_timeout 600;
proxy_read_timeout 600;
```

---

## تست کانکشن

### از ماشین دیگر (Python):
```python
import boto3

s3_client = boto3.client(
    's3',
    endpoint_url='https://s3.tejarat.chat',
    aws_access_key_id='YOUR_ACCESS_KEY',
    aws_secret_access_key='YOUR_SECRET_KEY',
    region_name='us-east-1'
)

# لیست buckets
response = s3_client.list_buckets()
print(response)

# آپلود فایل
s3_client.upload_file('local_file.txt', 'bucket-name', 'remote_file.txt')
```

### با curl:
```bash
# تست S3 API
curl -I https://s3.tejarat.chat

# تست Console
curl -I https://storage.tejarat.chat
```

---

## یادداشت‌های مهم

1. **پورت 9000** = S3 API (برای عملیات فایل از ماشین‌های دیگر)
2. **پورت 9001** = MinIO Console (رابط مدیریتی وب)
3. بعد از تغییر docker-compose، حتماً restart کنید:
   ```bash
   cd /srv/deployment
   docker-compose -f docker-compose.ingest.yml restart minio
   ```
4. SSL Certificate را برای هر دو domain تنظیم کنید
5. از `s3.tejarat.chat` برای API access استفاده کنید (نه `storage.tejarat.chat`)
