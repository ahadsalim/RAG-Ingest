# پرامپت امن‌سازی سرور برای هوش مصنوعی

> این پرامپت را به AI (مثل Cascade/Cursor/ChatGPT) بدهید تا سرور شما را بررسی و امن کند.
> قبل از اجرا، مطمئن شوید SSH دسترسی دارید و از تنظیمات فعلی بکاپ گرفته‌اید.
> قسمت «اطلاعات این سرور» را پر کنید و سپس کل پرامپت را کپی کنید.

---

## پرامپت (کپی کنید):

```
یک بررسی امنیتی کامل روی این سرور Production انجام بده و مشکلات را اصلاح کن.
ما قبلاً در یکی از سرورهایمان از طریق Redis هک شدیم. مهاجم از پورت باز Redis
(بدون رمز، بدون protected-mode) وارد شد، دستور SLAVEOF زد و بدافزار crypto miner
تزریق کرد. می‌خواهیم مطمئن شویم این سرور هم همین مشکلات را ندارد.

## اطلاعات این سرور
- نام/کاربرد سرور: _____________
- دامنه: _____________
- مسیر پروژه: _____________
- مسیر docker-compose: _____________
- سابنت LAN (شبکه داخلی): _____________ (مثال: 192.168.100.0/24)
- سابنت DMZ (در صورت وجود): _____________ (مثال: 10.10.10.0/24)
- پورت‌هایی که باید از اینترنت باز باشند: 22 (SSH), 80 (HTTP), 443 (HTTPS)
- پورت‌های دیگری که از اینترنت لازم هستند: _____________ (یا هیچ)

## مرحله ۱: بررسی وضعیت فعلی (فقط بررسی — هیچ تغییری نده)
1. لیست تمام کانتینرهای Docker و وضعیتشان: docker ps -a
2. فایل docker-compose را پیدا و بررسی کن — به خصوص بخش ports هر سرویس
3. تمام پورت‌هایی که از بیرون (0.0.0.0) listen می‌کنند: ss -tlnp | grep "0.0.0.0"
4. وضعیت فایروال: sudo ufw status verbose
5. اینترفیس‌های شبکه و IPها: ip -br addr show
6. قوانین iptables مربوط به Docker: sudo iptables -L DOCKER-USER -n -v
7. نتایج را به من گزارش بده و بگو چه مشکلاتی وجود دارد، قبل از هر تغییری.

## مرحله ۲: بستن پورت‌های داخلی در docker-compose
هر سرویسی که نباید از اینترنت قابل دسترسی باشد (مثل Redis, PostgreSQL, MongoDB,
RabbitMQ, MinIO, Elasticsearch, cAdvisor, Grafana, Prometheus و ...) باید پورتش
به 127.0.0.1 محدود شود.

در docker-compose، هر جا ports داری بررسی کن:

❌ اشتباه (از اینترنت قابل دسترسی):
  ports:
    - "6379:6379"
    - "5432:5432"
    - "9200:9200"

✅ درست (فقط از localhost):
  ports:
    - "127.0.0.1:6379:6379"
    - "127.0.0.1:5432:5432"
    - "127.0.0.1:9200:9200"

فقط پورت‌هایی که در «اطلاعات این سرور» مشخص شده می‌توانند بدون 127.0.0.1 باشند.
قبل از تغییر، لیست تغییرات پیشنهادی را نشان بده و تأیید بگیر.

## مرحله ۳: امن‌سازی سرویس‌های حساس

### Redis (اگر وجود دارد):
- در command یا redis.conf اضافه کن:
  --protected-mode yes
  --rename-command SLAVEOF ""
  --rename-command REPLICAOF ""
  --rename-command DEBUG ""
  --rename-command CONFIG ""
- بررسی کن role:master باشد: docker exec <container> redis-cli INFO replication
- کلیدهای مشکوک را بررسی کن: docker exec <container> redis-cli KEYS '*'
  کلیدهایی مثل x, backup, crackit, 1, 2, 3 مشکوک هستند — محتوایشان را بررسی کن.
- اگر رمز ندارد، requirepass تنظیم کن.

### PostgreSQL (اگر وجود دارد):
- مطمئن شو pg_hba.conf فقط اتصال از Docker network را اجازه می‌دهد
- رمز عبور قوی داشته باشد

### MongoDB (اگر وجود دارد):
- authentication فعال باشد
- bind به 127.0.0.1

### RabbitMQ (اگر وجود دارد):
- رمز پیش‌فرض guest/guest تغییر کرده باشد
- Management UI فقط از LAN

### Elasticsearch (اگر وجود دارد):
- xpack.security فعال باشد یا bind به 127.0.0.1

## مرحله ۴: تنظیم UFW (فایروال)
ufw را نصب و فعال کن (اگر نیست). قوانین:
  - پورت‌های عمومی (از «اطلاعات سرور»): ALLOW from Anywhere
  - بقیه پورت‌ها: ALLOW فقط از سابنت LAN

دستورات نمونه:
  sudo ufw default deny incoming
  sudo ufw default allow outgoing
  sudo ufw allow OpenSSH
  sudo ufw allow 80/tcp
  sudo ufw allow 443/tcp
  sudo ufw allow from <LAN_SUBNET> to any port <PORT> proto tcp comment '<SERVICE> - LAN only'
  sudo ufw --force enable

⚠️ قبل از enable کردن، مطمئن شو SSH ALLOW شده وگرنه از سرور قفل می‌شوی!

## مرحله ۵: DOCKER-USER iptables chain (بسیار مهم!)
⚠️ Docker به طور پیش‌فرض UFW را کاملاً دور می‌زند!
حتی اگر UFW فعال باشد، پورت‌های Docker از اینترنت باز هستند.
تنها راه کنترل: DOCKER-USER chain.

۱. به انتهای /etc/ufw/after.rules اضافه کن (با sudo):

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

(اگر DMZ ندارید، خط مربوطه را حذف کنید)
(اگر پورت‌های دیگری از اینترنت لازم است، خط RETURN برایشان اضافه کنید)

۲. یک systemd service بساز: /etc/systemd/system/docker-user-iptables.service
   - Type=oneshot, RemainAfterExit=yes
   - After=docker.service, Requires=docker.service
   - ExecStart: همین قوانین بالا را با iptables -A اعمال کند
   - systemctl daemon-reload && systemctl enable آن
   (دلیل: Docker هنگام restart، DOCKER-USER chain را خالی می‌کند)

۳. قوانین را فوراً هم با iptables اعمال کن.
۴. sudo ufw reload

## مرحله ۶: بررسی نفوذ احتمالی
بررسی کن آیا سرور قبلاً هک شده:
  - crontab -l (برای هر کاربر)
  - cat /etc/crontab
  - ls -la /etc/cron.d/
  - cat ~/.ssh/authorized_keys (فقط کلیدهای مجاز باشند)
  - ps aux | grep -iE "mine|xmr|kinsing|jack5tr|cryptonight" (پروسه مشکوک)
  - find /tmp /var/tmp /dev/shm -type f -name "*.sh" (اسکریپت مشکوک)
  - docker ps -a (کانتینر ناشناخته)
  - grep "Accepted" /var/log/auth.log | tail -30 (لاگین‌های اخیر SSH)
  - last -20 (آخرین لاگین‌ها)
  اگر چیز مشکوکی پیدا کردی، فوراً گزارش بده.

## مرحله ۷: تأیید نهایی
بعد از اعمال همه تغییرات:
  1. کانتینرها را restart کن (docker compose down && docker compose up -d)
  2. ss -tlnp | grep "0.0.0.0" → فقط پورت‌های مجاز باید باشند
  3. sudo iptables -L DOCKER-USER -n -v → قوانین DROP فعال باشد
  4. sudo ufw status → قوانین صحیح
  5. وب‌سایت/سرویس اصلی را تست کن
  6. دسترسی SSH را تست کن
  7. یک گزارش کامل از تغییرات انجام شده بده

## ⚠️ قوانین مهم
- قبل از هر تغییری، وضعیت فعلی را گزارش بده و تأیید بگیر
- تغییرات را مرحله به مرحله اعمال کن، نه همه یکجا
- بعد از هر تغییر، دسترسی SSH را تست کن
- اگر مشکلی پیش آمد، فوراً rollback کن
- هرگز پورت SSH را ببند بدون اینکه مطمئن شوی از راه دیگری دسترسی داری
```

---

## چرا این کارها لازم است؟

| مشکل | خطر | راه‌حل |
|---|---|---|
| Redis/MongoDB/Elasticsearch بدون رمز از اینترنت | هکر می‌تواند داده بخواند، بدافزار تزریق کند، یا سرویس را خراب کند | bind به 127.0.0.1 + رمز + protected-mode |
| PostgreSQL از اینترنت | هکر می‌تواند دیتابیس را بخواند/پاک کند | bind به 127.0.0.1 |
| Docker دور زدن UFW | حتی با UFW فعال، پورت‌های Docker از اینترنت بازند | DOCKER-USER chain |
| پورت‌های مدیریتی باز | Admin panels از اینترنت قابل دسترسی | فقط از LAN |
| بدون فایروال | همه پورت‌ها باز | UFW + DOCKER-USER |

## حادثه واقعی که باعث ایجاد این پرامپت شد
در تاریخ 2026-02-17 یکی از سرورهای ما (ingest) از طریق Redis هک شد:
- مهاجم از طریق پورت باز Redis (بدون رمز) وارد شد
- دستور `SLAVEOF` ارسال کرد و Redis را read-only کرد
- کلید مخرب با cron job برای دانلود crypto miner تزریق کرد
- خوشبختانه چون Redis داخل Docker بود، به host نفوذ نکرد
- اقدامات اصلاحی فوری انجام شد و سرور امن شد
