# پرامپت امن‌سازی سرور برای هوش مصنوعی

> این پرامپت را به AI (مثل Cascade/Cursor/ChatGPT) بدهید تا سرور شما را بررسی و امن کند.
> قبل از اجرا، مطمئن شوید SSH دسترسی دارید و از تنظیمات فعلی بکاپ گرفته‌اید.

---

## پرامپت (کپی کنید):

```
یک بررسی امنیتی کامل روی این سرور انجام بده و مشکلات را اصلاح کن.

## مرحله ۱: بررسی وضعیت فعلی
1. لیست تمام کانتینرهای Docker و وضعیتشان را نشان بده
2. فایل docker-compose را پیدا و بررسی کن
3. تمام پورت‌هایی که از بیرون (0.0.0.0) listen می‌کنند را لیست کن:
   - دستور: ss -tlnp | grep "0.0.0.0"
4. وضعیت فایروال (ufw) را بررسی کن
5. اینترفیس‌های شبکه و IPها را بررسی کن: ip -br addr show

## مرحله ۲: بستن پورت‌های داخلی
سرویس‌های داخلی (Redis, PostgreSQL, MinIO, cAdvisor و ...) نباید از اینترنت قابل دسترسی باشند.
در docker-compose، تمام پورت‌های سرویس‌های داخلی را به 127.0.0.1 محدود کن:

❌ اشتباه:
  ports:
    - "6380:6379"
    - "15432:5432"

✅ درست:
  ports:
    - "127.0.0.1:6380:6379"
    - "127.0.0.1:15432:5432"

فقط پورت‌های وب‌سرور (80, 443) و در صورت نیاز NPM Admin (81) می‌توانند بدون 127.0.0.1 باشند.

## مرحله ۳: امن‌سازی Redis
اگر Redis وجود دارد، این موارد را در command آن اضافه کن:
  --protected-mode yes
  --rename-command SLAVEOF ""
  --rename-command REPLICAOF ""
  --rename-command DEBUG ""
  --rename-command CONFIG ""

همچنین بررسی کن:
  - دستور: docker exec <redis-container> redis-cli INFO replication
    باید role:master باشد. اگر slave است، فوراً SLAVEOF NO ONE اجرا کن.
  - دستور: docker exec <redis-container> redis-cli KEYS '*'
    کلیدهای مشکوک (مثل x, backup, crackit) را بررسی و حذف کن.

## مرحله ۴: تنظیم UFW
ufw را نصب و فعال کن. قوانین:
  - SSH (22): از همه جا (یا فقط از LAN اگر VPN دارید)
  - HTTP (80): از همه جا
  - HTTPS (443): از همه جا
  - بقیه پورت‌ها (81, 8001, 9000, 9001, 15432, 6380, 8080): فقط از سابنت LAN

دستورات:
  sudo ufw default deny incoming
  sudo ufw default allow outgoing
  sudo ufw allow OpenSSH
  sudo ufw allow 80/tcp
  sudo ufw allow 443/tcp
  sudo ufw allow from <LAN_SUBNET> to any port 81 proto tcp
  ... (برای هر پورت داخلی)
  sudo ufw --force enable

## مرحله ۵: DOCKER-USER iptables chain (بسیار مهم!)
⚠️ Docker به طور پیش‌فرض UFW را دور می‌زند!
باید DOCKER-USER chain را تنظیم کنی تا فقط ترافیک مجاز به کانتینرها برسد.

۱. به انتهای /etc/ufw/after.rules اضافه کن:

*filter
:DOCKER-USER - [0:0]
-A DOCKER-USER -m conntrack --ctstate ESTABLISHED,RELATED -j RETURN
-A DOCKER-USER -s 172.16.0.0/12 -j RETURN
-A DOCKER-USER -s <LAN_SUBNET> -j RETURN
-A DOCKER-USER -s <DMZ_SUBNET> -j RETURN
-A DOCKER-USER -s 127.0.0.0/8 -j RETURN
-A DOCKER-USER -p tcp --dport 80 -j RETURN
-A DOCKER-USER -p tcp --dport 443 -j RETURN
-A DOCKER-USER -j DROP
COMMIT

۲. یک systemd service بساز (/etc/systemd/system/docker-user-iptables.service) 
   که بعد از docker.service اجرا شود و همین قوانین را با iptables اعمال کند.
   (چون Docker هنگام restart، DOCKER-USER chain را خالی می‌کند)

۳. قوانین را فوراً هم با iptables اعمال کن.

## مرحله ۶: بررسی نفوذ
بررسی کن آیا سرور قبلاً هک شده:
  - crontab -l و cat /etc/crontab و ls /etc/cron.d/
  - cat ~/.ssh/authorized_keys (فقط کلیدهای مجاز باشند)
  - ps aux | grep -E "mine|xmr|kinsing|jack5tr" (پروسه مشکوک)
  - find /tmp /var/tmp /dev/shm -type f (فایل مشکوک)
  - docker ps -a (کانتینر اضافی)
  - grep "Accepted" /var/log/auth.log | tail -20 (لاگین‌های اخیر)

## مرحله ۷: تأیید نهایی
بعد از اعمال تغییرات:
  1. docker compose restart (یا down/up)
  2. ss -tlnp | grep "0.0.0.0" → فقط 22, 80, 443 باید باشند
  3. sudo iptables -L DOCKER-USER -n -v → قوانین DROP باید فعال باشند
  4. sudo ufw status → قوانین صحیح
  5. وب‌سایت را تست کن (curl https://DOMAIN)
  6. از بیرون پورت‌های داخلی را تست کن (باید بسته باشند)

## اطلاعات اضافی
- سابنت LAN: _____________ (مثال: 192.168.100.0/24)
- سابنت DMZ: _____________ (مثال: 10.10.10.0/24)
- دامنه: _____________
- مسیر docker-compose: _____________

## ⚠️ هشدارها
- قبل از تغییر UFW مطمئن شو SSH باز است وگرنه از سرور قفل می‌شوی!
- قبل از restart کانتینرها، مطمئن شو وب‌سایت بعد از تغییرات کار می‌کند
- تغییرات را مرحله به مرحله اعمال کن، نه همه یکجا
- بعد از هر تغییر، دسترسی SSH را تست کن
```

---

## توضیحات تکمیلی

### چرا این کارها لازم است؟

| مشکل | خطر | راه‌حل |
|---|---|---|
| Redis بدون رمز از اینترنت | هکر می‌تواند SLAVEOF بزند و بدافزار تزریق کند | bind به 127.0.0.1 + protected-mode |
| PostgreSQL از اینترنت | هکر می‌تواند دیتابیس را بخواند/پاک کند | bind به 127.0.0.1 |
| Docker دور زدن UFW | حتی با UFW فعال، پورت‌های Docker از اینترنت بازند | DOCKER-USER chain |
| پورت‌های مدیریتی باز | NPM Admin, MinIO Console از اینترنت قابل دسترسی | فقط از LAN |

### حادثه واقعی (سرور ingest.tejarat.chat — 2026-02-17)
- مهاجم از IP `160.30.159.104` به Redis متصل شد
- دستور `SLAVEOF` ارسال کرد و Redis را read-only کرد
- کلید مخرب با cron job برای دانلود crypto miner تزریق کرد
- خوشبختانه چون Redis داخل Docker بود، به host نفوذ نکرد
- مستند کامل: `/srv/documents/SECURITY_INCIDENT_2026.md`
