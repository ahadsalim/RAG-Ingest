#!/bin/bash

# =============================================================================
# RAG-Ingest Production Installation Script
# =============================================================================
# This script installs the complete RAG-Ingest system for production use.
# It generates secure passwords, configures all services, and provides
# comprehensive post-installation guidance.
# =============================================================================

set -e
# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="/opt/backups/ingest"
LOG_DIR="/var/log/ingest"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m'
BOLD='\033[1m'

# =============================================================================
# Helper Functions
# =============================================================================

print_header() {
    echo ""
    echo -e "${PURPLE}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${PURPLE}║${NC} ${BOLD}$1${NC}"
    echo -e "${PURPLE}╚══════════════════════════════════════════════════════════════╝${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_step() {
    echo -e "${CYAN}▶ $1${NC}"
}

generate_password() {
    openssl rand -base64 32 | tr -d "=+/" | cut -c1-$1
}

# =============================================================================
# Pre-flight Checks
# =============================================================================

check_root() {
    if [[ $EUID -ne 0 ]]; then
        print_error "این اسکریپت باید با دسترسی root اجرا شود"
        echo "لطفاً با sudo اجرا کنید: sudo $0"
        exit 1
    fi
}

check_system_requirements() {
    print_header "بررسی پیش‌نیازها"
    
    # Check RAM
    local ram_gb=$(free -g | awk '/^Mem:/{print $2}')
    if [ "$ram_gb" -lt 4 ]; then
        print_warning "RAM کمتر از 4GB است. حداقل 8GB توصیه می‌شود."
    else
        print_success "RAM: ${ram_gb}GB"
    fi
    
    # Check disk space
    local disk_gb=$(df -BG / | awk 'NR==2 {print $4}' | tr -d 'G')
    if [ "$disk_gb" -lt 20 ]; then
        print_error "فضای دیسک کافی نیست. حداقل 20GB نیاز است."
        exit 1
    else
        print_success "فضای دیسک: ${disk_gb}GB"
    fi
    
    # Check if ports are available
    for port in 80 443 81 8001 15432 6380; do
        if netstat -tuln 2>/dev/null | grep -q ":$port " || ss -tuln 2>/dev/null | grep -q ":$port "; then
            print_warning "پورت $port در حال استفاده است"
        fi
    done
}

# =============================================================================
# Installation Functions
# =============================================================================

install_dependencies() {
    print_header "نصب وابستگی‌های سیستم"
    
    print_step "به‌روزرسانی لیست پکیج‌ها..."
    apt update -qq
    
    print_step "نصب پکیج‌های ضروری..."
    apt install -y -qq \
        curl wget git unzip \
        software-properties-common apt-transport-https \
        ca-certificates gnupg lsb-release \
        openssl htop tree jq \
        python3 python3-pip \
        ufw net-tools
    
    print_success "وابستگی‌ها نصب شدند"
}

install_docker() {
    print_header "نصب Docker"
    
    if command -v docker &> /dev/null; then
        print_info "Docker قبلاً نصب شده است"
        docker --version
    else
        print_step "نصب Docker..."
        
        # Remove old versions
        apt remove -y docker docker-engine docker.io containerd runc 2>/dev/null || true
        
        # Add Docker GPG key
        curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
        
        # Add Docker repository
        echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
        
        # Install Docker
        apt update -qq
        apt install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
        
        # Enable Docker
        systemctl enable docker
        systemctl start docker
        
        print_success "Docker نصب شد"
    fi
    
    # Detect compose command
    if docker compose version >/dev/null 2>&1; then
        DOCKER_COMPOSE="docker compose"
    else
        DOCKER_COMPOSE="docker-compose"
    fi
}

# =============================================================================
# Configuration
# =============================================================================

generate_credentials() {
    print_header "تولید رمزهای امن"
    
    # Generate all passwords
    SECRET_KEY=$(generate_password 64)
    DB_PASSWORD=$(generate_password 32)
    REDIS_PASSWORD=$(generate_password 32)
    BALE_CLIENT_ID=""
    BALE_CLIENT_SECRET=""
    
    print_success "رمزهای امن تولید شدند"
}

configure_domain() {
    print_header "تنظیم دامنه"
    
    echo ""
    echo "لطفاً نام دامنه یا آدرس IP سرور را وارد کنید:"
    echo "(مثال: ingest.example.com یا 192.168.1.100)"
    echo ""
    read -p "دامنه: " DOMAIN_NAME
    DOMAIN_NAME=${DOMAIN_NAME:-localhost}
    
    print_success "دامنه تنظیم شد: $DOMAIN_NAME"
}

configure_minio() {
    print_header "تنظیم سرور MinIO (Object Storage)"
    
    echo ""
    echo "MinIO به عنوان سرور مستقل خارجی اجرا می‌شود."
    echo "لطفاً اطلاعات اتصال به سرور MinIO را وارد کنید."
    echo ""
    read -p "آدرس MinIO (مثال: http://10.10.10.50:9000): " MINIO_ENDPOINT
    MINIO_ENDPOINT=${MINIO_ENDPOINT:-http://10.10.10.50:9000}
    
    read -p "Access Key: " MINIO_ACCESS_KEY
    MINIO_ACCESS_KEY=${MINIO_ACCESS_KEY:-minioadmin}
    
    read -p "Secret Key: " MINIO_SECRET_KEY
    MINIO_SECRET_KEY=${MINIO_SECRET_KEY:-minioadmin123}
    
    read -p "نام Bucket (پیش‌فرض: ingest-system): " MINIO_BUCKET
    MINIO_BUCKET=${MINIO_BUCKET:-ingest-system}
    
    print_success "تنظیمات MinIO:"
    print_info "  Endpoint: $MINIO_ENDPOINT"
    print_info "  Bucket: $MINIO_BUCKET"
}

configure_bale_api() {
    print_header "تنظیم سرویس بله (Safir API)"
    
    echo ""
    echo "برای استفاده از احراز هویت OTP، به اکانت Safir بله نیاز دارید."
    echo ""
    echo "مراحل دریافت اطلاعات دسترسی:"
    echo "  1. به سایت https://safir.bale.ai مراجعه کنید"
    echo "  2. ثبت‌نام کنید و یک Application بسازید"
    echo "  3. Client ID و Client Secret را دریافت کنید"
    echo "  4. موجودی پیامک OTP را شارژ کنید"
    echo ""
    read -p "Client ID (اختیاری - بعداً قابل تنظیم): " BALE_CLIENT_ID
    read -p "Client Secret (اختیاری - بعداً قابل تنظیم): " BALE_CLIENT_SECRET
    
    if [ -n "$BALE_CLIENT_ID" ] && [ -n "$BALE_CLIENT_SECRET" ]; then
        print_success "اطلاعات سرویس بله تنظیم شد"
    else
        print_warning "اطلاعات سرویس بله تنظیم نشد. بعداً در فایل .env تنظیم کنید."
    fi
}

create_env_file() {
    print_header "ایجاد فایل تنظیمات"
    
    local env_file="$PROJECT_DIR/.env"
    
    cat > "$env_file" << EOF
# =============================================================================
# RAG-Ingest Production Configuration
# Generated: $(date -Iseconds)
# =============================================================================

# Django Core
DEBUG=false
SECRET_KEY=${SECRET_KEY}

# Domain & Hosts
DOMAIN_NAME=${DOMAIN_NAME}
ALLOWED_HOSTS=${DOMAIN_NAME},localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=https://${DOMAIN_NAME},http://${DOMAIN_NAME},http://localhost:8001
CORS_ALLOWED_ORIGINS=https://${DOMAIN_NAME},http://${DOMAIN_NAME},http://localhost:8001
CORS_ALLOW_CREDENTIALS=true

# Proxy settings (for Nginx Proxy Manager)
USE_X_FORWARDED_HOST=True
SECURE_PROXY_SSL_HEADER=HTTP_X_FORWARDED_PROTO,https

# Static files
STATIC_URL=/static/
STATIC_ROOT=/app/staticfiles
MEDIA_URL=/media/
MEDIA_ROOT=/app/media

# Security (enable after SSL setup)
SECURE_SSL_REDIRECT=False
SESSION_COOKIE_SECURE=False
CSRF_COOKIE_SECURE=False
SECURE_HSTS_SECONDS=0

# =============================================================================
# Database
# =============================================================================
POSTGRES_DB=ingest
POSTGRES_USER=ingest
POSTGRES_PASSWORD=${DB_PASSWORD}
POSTGRES_HOST=db
DB_PORT=15432

# =============================================================================
# Redis
# =============================================================================
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# =============================================================================
# MinIO Storage (External Server)
# =============================================================================
AWS_ACCESS_KEY_ID=${MINIO_ACCESS_KEY}
AWS_SECRET_ACCESS_KEY=${MINIO_SECRET_KEY}
AWS_STORAGE_BUCKET_NAME=${MINIO_BUCKET}
AWS_S3_ENDPOINT_URL=${MINIO_ENDPOINT}
AWS_S3_REGION_NAME=us-east-1
AWS_S3_USE_SSL=false

# =============================================================================
# Bale Messenger OTP Authentication (Safir API)
# =============================================================================
BALE_API_URL=https://safir.bale.ai/api/v2
BALE_CLIENT_ID=${BALE_CLIENT_ID}
BALE_CLIENT_SECRET=${BALE_CLIENT_SECRET}

# =============================================================================
# Embedding Configuration
# =============================================================================
EMBEDDING_PROVIDER=e5
EMBEDDING_E5_MODEL_NAME=intfloat/multilingual-e5-large
EMBEDDING_DIMENSION=1024
EMBEDDING_MAX_SEQ_LENGTH=512
EMBEDDING_BATCH_SIZE=8
EMBEDDING_DEVICE=cpu
EMBEDDING_MODEL_CACHE_DIR=/app/models

# Chunking
DEFAULT_CHUNK_SIZE=350
DEFAULT_CHUNK_OVERLAP=80

# =============================================================================
# Localization
# =============================================================================
DISPLAY_TIME_ZONE=Asia/Tehran
DISPLAY_LOCALE=fa_IR
LANGUAGE_CODE=fa

# =============================================================================
# Logging
# =============================================================================
DJANGO_LOG_LEVEL=INFO
EOF

    chmod 600 "$env_file"
    
    # Create symlink in deployment directory
    ln -sf "$env_file" "$SCRIPT_DIR/.env"
    
    print_success "فایل تنظیمات ایجاد شد: $env_file"
}

# =============================================================================
# Deployment
# =============================================================================

setup_directories() {
    print_step "ایجاد دایرکتوری‌ها..."
    mkdir -p "$BACKUP_DIR"
    mkdir -p "$LOG_DIR"
    chmod 755 "$BACKUP_DIR" "$LOG_DIR"
}

setup_network() {
    print_step "تنظیم شبکه Docker..."
    if ! docker network ls | grep -q ingest_net; then
        docker network create ingest_net
    fi
}

build_and_start() {
    print_header "ساخت و اجرای سرویس‌ها"
    
    cd "$PROJECT_DIR"
    
    setup_network
    
    print_step "ساخت Docker images..."
    $DOCKER_COMPOSE -f deployment/docker-compose.ingest.yml --env-file .env build
    
    print_step "اجرای سرویس‌ها..."
    $DOCKER_COMPOSE -f deployment/docker-compose.ingest.yml --env-file .env up -d
    
    print_step "انتظار برای آماده شدن دیتابیس..."
    sleep 10
    
    local max_attempts=30
    local attempt=1
    while [ $attempt -le $max_attempts ]; do
        if $DOCKER_COMPOSE -f deployment/docker-compose.ingest.yml exec -T db pg_isready -U ingest >/dev/null 2>&1; then
            break
        fi
        sleep 2
        attempt=$((attempt + 1))
    done
    
    print_step "اجرای migrations..."
    $DOCKER_COMPOSE -f deployment/docker-compose.ingest.yml exec -T web python manage.py migrate --noinput
    
    print_step "جمع‌آوری فایل‌های استاتیک..."
    $DOCKER_COMPOSE -f deployment/docker-compose.ingest.yml exec -T web python manage.py collectstatic --noinput
    
    print_step "ایجاد کاربر ادمین..."
    $DOCKER_COMPOSE -f deployment/docker-compose.ingest.yml exec -T web python manage.py shell -c "
from django.contrib.auth.models import User
from ingest.apps.accounts.models import UserProfile
if not User.objects.filter(username='admin').exists():
    user = User.objects.create_superuser('admin', 'admin@${DOMAIN_NAME}', 'admin123')
    UserProfile.objects.create(user=user, mobile='09123456789', is_mobile_verified=True)
    print('کاربر ادمین ایجاد شد')
else:
    print('کاربر ادمین موجود است')
"
    
    print_success "سرویس‌ها اجرا شدند"
}

configure_firewall() {
    print_header "تنظیم فایروال (UFW)"
    
    if ! command -v ufw >/dev/null 2>&1; then
        print_warning "UFW نصب نیست"
        return
    fi
    
    ufw --force disable >/dev/null 2>&1 || true
    ufw --force reset >/dev/null 2>&1
    
    ufw default deny incoming
    ufw default allow outgoing
    
    # --- Public ports (accessible from internet) ---
    ufw allow OpenSSH          # SSH
    ufw allow 80/tcp           # HTTP
    ufw allow 443/tcp          # HTTPS
    
    # --- LAN-only ports (internal services) ---
    # Detect LAN subnet
    local lan_subnet=""
    read -p "سابنت شبکه داخلی (LAN) را وارد کنید (مثال: 192.168.100.0/24): " lan_subnet
    lan_subnet=${lan_subnet:-192.168.100.0/24}
    
    ufw allow from "$lan_subnet" to any port 81 proto tcp comment 'NPM Admin - LAN only'
    ufw allow from "$lan_subnet" to any port 8001 proto tcp comment 'Django direct - LAN only'
    ufw allow from "$lan_subnet" to any port 6380 proto tcp comment 'Redis - LAN only'
    ufw allow from "$lan_subnet" to any port 15432 proto tcp comment 'PostgreSQL - LAN only'
    ufw allow from "$lan_subnet" to any port 8080 proto tcp comment 'cAdvisor - LAN only'
    
    ufw --force enable
    
    print_success "فایروال تنظیم شد"
    print_info "پورت‌های عمومی: 22 (SSH), 80 (HTTP), 443 (HTTPS)"
    print_info "پورت‌های داخلی (فقط $lan_subnet): 81, 8001, 6380, 15432, 8080"
}

configure_docker_security() {
    print_header "تنظیمات امنیتی Docker"
    
    # --- DOCKER-USER iptables chain ---
    # Docker bypasses UFW by default. DOCKER-USER chain is the ONLY way
    # to filter traffic destined for Docker containers.
    print_step "تنظیم DOCKER-USER iptables chain..."
    
    local lan_subnet="192.168.100.0/24"
    local dmz_subnet="10.10.10.0/24"
    
    # Detect LAN subnet from existing interfaces
    local detected_lan=$(ip -4 addr show | grep 'inet 192\.' | awk '{print $2}' | head -1)
    if [ -n "$detected_lan" ]; then
        lan_subnet=$(echo "$detected_lan" | sed 's/\.[0-9]*\//.0\//')
    fi
    local detected_dmz=$(ip -4 addr show | grep 'inet 10\.' | awk '{print $2}' | head -1)
    if [ -n "$detected_dmz" ]; then
        dmz_subnet=$(echo "$detected_dmz" | sed 's/\.[0-9]*\//.0\//')
    fi
    
    # Add DOCKER-USER rules to /etc/ufw/after.rules
    if ! grep -q "DOCKER-USER" /etc/ufw/after.rules 2>/dev/null; then
        cat >> /etc/ufw/after.rules << DOCKER_EOF

# ============================================================
# DOCKER-USER chain: Control Docker container traffic
# Docker bypasses ufw by default. This chain is the ONLY way
# to filter traffic destined for Docker containers.
# Added by start.sh - Security hardening
# ============================================================
*filter
:DOCKER-USER - [0:0]

# Allow established/related connections
-A DOCKER-USER -m conntrack --ctstate ESTABLISHED,RELATED -j RETURN

# Allow all traffic from Docker internal networks
-A DOCKER-USER -s 172.16.0.0/12 -j RETURN

# Allow all traffic from LAN
-A DOCKER-USER -s ${lan_subnet} -j RETURN

# Allow all traffic from DMZ
-A DOCKER-USER -s ${dmz_subnet} -j RETURN

# Allow all traffic from localhost
-A DOCKER-USER -s 127.0.0.0/8 -j RETURN

# Allow HTTP/HTTPS (Nginx Proxy Manager) from anywhere
-A DOCKER-USER -p tcp --dport 80 -j RETURN
-A DOCKER-USER -p tcp --dport 443 -j RETURN

# DROP everything else destined for Docker containers
-A DOCKER-USER -j DROP

COMMIT
DOCKER_EOF
        print_success "DOCKER-USER chain به /etc/ufw/after.rules اضافه شد"
    else
        print_info "DOCKER-USER chain قبلاً تنظیم شده است"
    fi
    
    # --- Create systemd service for persistent DOCKER-USER rules ---
    print_step "ایجاد systemd service برای DOCKER-USER..."
    
    cat > /etc/systemd/system/docker-user-iptables.service << SYSTEMD_EOF
[Unit]
Description=Apply DOCKER-USER iptables rules
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/bin/bash -c '\
  iptables -F DOCKER-USER 2>/dev/null; \
  iptables -A DOCKER-USER -m conntrack --ctstate ESTABLISHED,RELATED -j RETURN; \
  iptables -A DOCKER-USER -s 172.16.0.0/12 -j RETURN; \
  iptables -A DOCKER-USER -s ${lan_subnet} -j RETURN; \
  iptables -A DOCKER-USER -s ${dmz_subnet} -j RETURN; \
  iptables -A DOCKER-USER -s 127.0.0.0/8 -j RETURN; \
  iptables -A DOCKER-USER -p tcp --dport 80 -j RETURN; \
  iptables -A DOCKER-USER -p tcp --dport 443 -j RETURN; \
  iptables -A DOCKER-USER -j DROP'

[Install]
WantedBy=multi-user.target
SYSTEMD_EOF
    
    systemctl daemon-reload
    systemctl enable docker-user-iptables.service
    
    # Apply rules immediately
    iptables -F DOCKER-USER 2>/dev/null || true
    iptables -A DOCKER-USER -m conntrack --ctstate ESTABLISHED,RELATED -j RETURN
    iptables -A DOCKER-USER -s 172.16.0.0/12 -j RETURN
    iptables -A DOCKER-USER -s "$lan_subnet" -j RETURN
    iptables -A DOCKER-USER -s "$dmz_subnet" -j RETURN
    iptables -A DOCKER-USER -s 127.0.0.0/8 -j RETURN
    iptables -A DOCKER-USER -p tcp --dport 80 -j RETURN
    iptables -A DOCKER-USER -p tcp --dport 443 -j RETURN
    iptables -A DOCKER-USER -j DROP
    
    # Reload UFW to apply after.rules
    ufw reload 2>/dev/null || true
    
    print_success "DOCKER-USER chain فعال شد"
    print_success "systemd service ایجاد شد (بعد از restart سرور هم اعمال می‌شود)"
    
    # --- Verify ---
    print_step "بررسی نهایی امنیت..."
    
    # Check Redis is not exposed
    if ss -tlnp | grep -q "0.0.0.0:6380"; then
        print_warning "⚠️ پورت Redis (6380) از بیرون قابل دسترسی است! docker-compose را بررسی کنید."
    else
        print_success "Redis فقط از localhost قابل دسترسی است"
    fi
    
    # Check PostgreSQL is not exposed
    if ss -tlnp | grep -q "0.0.0.0:15432"; then
        print_warning "⚠️ پورت PostgreSQL (15432) از بیرون قابل دسترسی است!"
    else
        print_success "PostgreSQL فقط از localhost قابل دسترسی است"
    fi
    
    print_success "تنظیمات امنیتی Docker انجام شد"
}

setup_cron_jobs() {
    print_info "تنظیم Cron Jobs برای Backup خودکار..."
    
    # Remove existing backup cron jobs
    crontab -l 2>/dev/null | grep -v "backup_auto.sh" | crontab - 2>/dev/null || true
    
    # Add new cron jobs
    (crontab -l 2>/dev/null; cat << 'CRON_EOF'
# RAG-Ingest Backup Cron Jobs
0 */6 * * * /srv/deployment/backup_auto.sh >> /var/log/ingest_auto_backup.log 2>&1
CRON_EOF
    ) | crontab -
    
    print_success "Cron Jobs تنظیم شد:"
    print_info "  • backup_auto.sh: هر 6 ساعت"
}

setup_monitoring() {
    print_header "بررسی سرویس‌های مانیتورینگ"
    
    print_info "Exporterها به صورت خودکار با سایر سرویس‌ها راه‌اندازی شده‌اند"
    
    # Test exporters
    sleep 5
    print_step "بررسی وضعیت Exporterها..."
    
    local all_ok=true
    
    if curl -sf http://localhost:9100/metrics > /dev/null 2>&1; then
        print_success "Node Exporter: OK"
    else
        print_warning "Node Exporter: در دسترس نیست"
        all_ok=false
    fi
    
    if curl -sf http://localhost:9187/metrics > /dev/null 2>&1; then
        print_success "PostgreSQL Exporter: OK"
    else
        print_warning "PostgreSQL Exporter: در دسترس نیست"
        all_ok=false
    fi
    
    if curl -sf http://localhost:9121/metrics > /dev/null 2>&1; then
        print_success "Redis Exporter: OK"
    else
        print_warning "Redis Exporter: در دسترس نیست"
        all_ok=false
    fi
    
    if curl -sf http://localhost:8080/metrics > /dev/null 2>&1; then
        print_success "cAdvisor: OK"
    else
        print_warning "cAdvisor: در دسترس نیست"
        all_ok=false
    fi
    
    if docker ps | grep -q promtail-ingest; then
        print_success "Promtail: OK"
    else
        print_warning "Promtail: در حال اجرا نیست"
        all_ok=false
    fi
    
    if [ "$all_ok" = true ]; then
        print_success "تمام Exporterها با موفقیت راه‌اندازی شدند"
    else
        print_warning "برخی Exporterها مشکل دارند - لاگ‌ها را بررسی کنید"
    fi
    
    print_info ""
    print_info "سرویس‌های مانیتورینگ نصب شده:"
    print_info "  • Node Exporter (پورت 9100) - متریک‌های سیستم"
    print_info "  • PostgreSQL Exporter (پورت 9187) - متریک‌های دیتابیس"
    print_info "  • Redis Exporter (پورت 9121) - متریک‌های Redis"
    print_info "  • Promtail (پورت 9080) - ارسال لاگ به Loki"
    print_info "  • cAdvisor (پورت 8080) - متریک‌های کانتینرها"
}

# =============================================================================
# Post-Installation Guide
# =============================================================================

show_credentials() {
    print_header "اطلاعات دسترسی"
    
    echo ""
    echo -e "${BOLD}🔐 رمزهای تولید شده (این اطلاعات را ذخیره کنید):${NC}"
    echo -e "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "  ${CYAN}Django Admin:${NC}"
    echo -e "    Username: ${GREEN}admin${NC}"
    echo -e "    Password: ${GREEN}admin123${NC} ${RED}(فوراً تغییر دهید!)${NC}"
    echo -e "    Mobile:   ${GREEN}09123456789${NC} ${YELLOW}(در پروفایل تغییر دهید)${NC}"
    echo ""
    echo -e "  ${CYAN}Database:${NC}"
    echo -e "    Password: ${GREEN}${DB_PASSWORD}${NC}"
    echo ""
    echo -e "  ${CYAN}MinIO (External):${NC}"
    echo -e "    Endpoint: ${GREEN}${MINIO_ENDPOINT}${NC}"
    echo -e "    Access Key: ${GREEN}${MINIO_ACCESS_KEY}${NC}"
    echo -e "    Secret Key: ${GREEN}${MINIO_SECRET_KEY}${NC}"
    echo -e "    Bucket: ${GREEN}${MINIO_BUCKET}${NC}"
    echo ""
    if [ -n "$BALE_CLIENT_ID" ]; then
        echo -e "  ${CYAN}Bale Safir API:${NC}"
        echo -e "    Client ID: ${GREEN}${BALE_CLIENT_ID}${NC}"
        echo -e "    Client Secret: ${GREEN}${BALE_CLIENT_SECRET:0:10}...${NC}"
    fi
    echo -e "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

show_urls() {
    print_header "آدرس‌های دسترسی"
    
    local server_ip=$(hostname -I | awk '{print $1}')
    
    echo ""
    echo -e "${BOLD}🌐 آدرس‌های سیستم:${NC}"
    echo -e "  • پنل مدیریت:  ${CYAN}http://${DOMAIN_NAME}:8001/admin/${NC}"
    echo -e "  • صفحه ورود:   ${CYAN}http://${DOMAIN_NAME}:8001/accounts/login/${NC}"
    echo -e "  • API Health:  ${CYAN}http://${DOMAIN_NAME}:8001/api/health/${NC}"
    echo -e "  • MinIO:       ${CYAN}${MINIO_ENDPOINT}${NC} (سرور خارجی)"
    echo ""
    echo -e "${BOLD}📊 Monitoring Endpoints (برای سرور مانیتورینگ):${NC}"
    echo -e "  • Node Exporter:       ${CYAN}http://${server_ip}:9100/metrics${NC}"
    echo -e "  • PostgreSQL Exporter: ${CYAN}http://${server_ip}:9187/metrics${NC}"
    echo -e "  • Redis Exporter:      ${CYAN}http://${server_ip}:9121/metrics${NC}"
    echo -e "  • cAdvisor:            ${CYAN}http://${server_ip}:8080/metrics${NC}"
    echo -e "  • Promtail → Loki:     ${CYAN}http://10.10.10.40:3100${NC}"
    echo ""
}

show_nginx_config() {
    print_header "تنظیمات Nginx Proxy Manager"
    
    echo ""
    echo -e "${BOLD}📝 مراحل تنظیم Nginx Proxy Manager:${NC}"
    echo ""
    echo "1. نصب Nginx Proxy Manager:"
    echo -e "   ${CYAN}docker run -d --name npm --network ingest_net \\
     -p 80:80 -p 443:443 -p 81:81 \\
     -v npm_data:/data -v npm_letsencrypt:/etc/letsencrypt \\
     jc21/nginx-proxy-manager:latest${NC}"
    echo ""
    echo "2. ورود به پنل NPM:"
    echo -e "   آدرس: ${CYAN}http://${DOMAIN_NAME}:81${NC}"
    echo -e "   Email: ${GREEN}admin@example.com${NC}"
    echo -e "   Password: ${GREEN}changeme${NC}"
    echo ""
    echo "3. ایجاد Proxy Host برای ${DOMAIN_NAME}:"
    echo -e "   • Domain: ${GREEN}${DOMAIN_NAME}${NC}"
    echo -e "   • Forward Hostname: ${GREEN}web${NC} (یا ${GREEN}host.docker.internal${NC})"
    echo -e "   • Forward Port: ${GREEN}8001${NC}"
    echo -e "   • Enable: ${GREEN}Websockets Support${NC}"
    echo ""
    echo -e "${BOLD}⚙️ تنظیمات پیشرفته (Advanced):${NC}"
    echo "در قسمت Custom Nginx Configuration این کد را وارد کنید:"
    echo ""
    echo -e "${YELLOW}# Proxy headers
proxy_set_header Host \$host;
proxy_set_header X-Real-IP \$remote_addr;
proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto \$scheme;
proxy_set_header X-Forwarded-Host \$host;

# Timeouts
proxy_connect_timeout 60s;
proxy_send_timeout 60s;
proxy_read_timeout 60s;

# Buffer settings
proxy_buffer_size 128k;
proxy_buffers 4 256k;
proxy_busy_buffers_size 256k;

# File upload size
client_max_body_size 100M;${NC}"
    echo ""
    echo "4. فعال‌سازی SSL:"
    echo "   • در تب SSL گزینه Request a new SSL Certificate را انتخاب کنید"
    echo "   • Force SSL را فعال کنید"
    echo ""
    echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo -e "${BOLD}⚠️  نکته: MinIO روی سرور خارجی مستقل اجرا می‌شود.${NC}"
    echo -e "   آدرس: ${GREEN}${MINIO_ENDPOINT}${NC}"
    echo -e "   تنظیمات Proxy برای MinIO باید روی سرور MinIO انجام شود."
    echo ""
}

show_post_install_steps() {
    print_header "مراحل بعد از نصب"
    
    echo ""
    echo -e "${BOLD}✅ کارهایی که باید انجام دهید:${NC}"
    echo ""
    echo "1. ${RED}[فوری]${NC} رمز عبور ادمین را تغییر دهید"
    echo "   - وارد پنل مدیریت شوید"
    echo "   - به بخش کاربران بروید"
    echo "   - رمز عبور admin را تغییر دهید"
    echo ""
    echo "2. ${RED}[فوری]${NC} شماره موبایل ادمین را تنظیم کنید"
    echo "   - به بخش پروفایل‌های کاربران بروید"
    echo "   - شماره موبایل واقعی را وارد کنید"
    echo ""
    echo "3. ${YELLOW}[مهم]${NC} سرویس بله (Safir API) را تنظیم کنید"
    echo "   - به سایت https://safir.bale.ai مراجعه کنید"
    echo "   - ثبت‌نام کنید و Application بسازید"
    echo "   - Client ID و Client Secret را در .env وارد کنید"
    echo "   - موجودی پیامک OTP را شارژ کنید"
    echo "   - سرویس‌ها را restart کنید"
    echo ""
    echo "4. ${YELLOW}[مهم]${NC} Nginx Proxy Manager را نصب و تنظیم کنید"
    echo "   - دستورات بالا را اجرا کنید"
    echo "   - SSL را فعال کنید"
    echo ""
    echo "5. ${GREEN}[توصیه]${NC} Backup خودکار را تنظیم کنید"
    echo -e "   ${CYAN}./backup_manager.sh${NC}"
    echo ""
    echo "6. ${GREEN}[توصیه]${NC} تنظیمات امنیتی SSL را فعال کنید"
    echo "   - بعد از تنظیم SSL، در .env این موارد را true کنید:"
    echo "     SECURE_SSL_REDIRECT=True"
    echo "     SESSION_COOKIE_SECURE=True"
    echo "     CSRF_COOKIE_SECURE=True"
    echo "     SECURE_HSTS_SECONDS=31536000"
    echo ""
    echo "7. ${RED}[فوری]${NC} بررسی امنیت شبکه"
    echo "   - مطمئن شوید Redis/PostgreSQL از اینترنت قابل دسترسی نیستند"
    echo "   - دستور بررسی: ss -tlnp | grep -v 127.0.0.1"
    echo "   - DOCKER-USER chain فعال باشد: sudo iptables -L DOCKER-USER -n"
    echo "   - مستند امنیتی: /srv/documents/SECURITY_INCIDENT_2026.md"
    echo ""
    echo "8. ${YELLOW}[مهم]${NC} اطلاعات مانیتورینگ را به سرور مانیتورینگ منتقل کنید"
    echo -e "   - اطلاعات در فایل ${CYAN}CREDENTIALS.txt${NC} موجود است"
    echo "   - بخش 'اطلاعات مانیتورینگ' را به سرور 10.10.10.40 منتقل کنید"
    echo "   - پیکربندی‌های Prometheus را در prometheus.yml اضافه کنید"
    echo ""
}

show_useful_commands() {
    print_header "دستورات مفید"
    
    echo ""
    echo -e "${BOLD}🔧 مدیریت سرویس‌ها:${NC}"
    echo -e "  # وضعیت سرویس‌ها"
    echo -e "  ${CYAN}docker compose -f deployment/docker-compose.ingest.yml ps${NC}"
    echo ""
    echo -e "  # مشاهده لاگ‌ها"
    echo -e "  ${CYAN}docker compose -f deployment/docker-compose.ingest.yml logs -f${NC}"
    echo ""
    echo -e "  # Restart سرویس‌ها"
    echo -e "  ${CYAN}docker compose -f deployment/docker-compose.ingest.yml restart${NC}"
    echo ""
    echo -e "  # Django Shell"
    echo -e "  ${CYAN}docker compose -f deployment/docker-compose.ingest.yml exec web python manage.py shell${NC}"
    echo ""
    echo -e "${BOLD}💾 Backup:${NC}"
    echo -e "  ${CYAN}cd $SCRIPT_DIR && ./backup_manager.sh${NC}"
    echo ""
    echo -e "${BOLD}📁 مسیرهای مهم:${NC}"
    echo -e "  • پروژه:    ${CYAN}$PROJECT_DIR${NC}"
    echo -e "  • تنظیمات:  ${CYAN}$PROJECT_DIR/.env${NC}"
    echo -e "  • لاگ‌ها:    ${CYAN}$LOG_DIR${NC}"
    echo -e "  • Backup:   ${CYAN}$BACKUP_DIR${NC}"
    echo ""
}

show_cron_jobs() {
    print_header "⏰ Cron Jobs سیستم"
    
    echo ""
    echo -e "${BOLD}Cron های فعال برای Backup خودکار:${NC}"
    echo ""
    echo -e "  ${CYAN}0 */6 * * *${NC} backup_auto.sh    → بکاپ DB+NPM هر 6 ساعت"
    echo ""
    echo -e "${BOLD}دستورات ایجاد مجدد (اگر پاک شده باشند):${NC}"
    echo -e "  ${CYAN}$SCRIPT_DIR/backup_auto.sh --setup${NC}"
    echo ""
    echo -e "${BOLD}مشاهده cron های فعلی:${NC}"
    echo -e "  ${CYAN}crontab -l${NC}"
    echo ""
    echo -e "${BOLD}فایل‌های لاگ:${NC}"
    echo -e "  • Auto Backup:  ${CYAN}/var/log/ingest_auto_backup.log${NC}"
    echo ""
}

# =============================================================================
# Main
# =============================================================================

main() {
    clear
    print_header "🚀 نصب RAG-Ingest Production"
    
    echo ""
    echo "این اسکریپت سیستم RAG-Ingest را برای محیط Production نصب می‌کند."
    echo ""
    echo "موارد زیر نصب و تنظیم می‌شوند:"
    echo "  • Docker و Docker Compose"
    echo "  • PostgreSQL با pgvector"
    echo "  • Redis"
    echo "  • Celery (Background Tasks)"
    echo "  • Django Application"
    echo ""
    read -p "آیا ادامه می‌دهید؟ (y/N): " confirm
    if [[ ! $confirm =~ ^[Yy]$ ]]; then
        echo "عملیات لغو شد."
        exit 0
    fi
    
    # Pre-flight
    check_root
    check_system_requirements
    
    # Installation
    install_dependencies
    install_docker
    
    # Configuration
    generate_credentials
    configure_domain
    configure_minio
    configure_bale_api
    create_env_file
    setup_directories
    
    # Deployment
    build_and_start
    configure_firewall
    configure_docker_security
    setup_cron_jobs
    setup_monitoring
    
    # Post-installation guide
    echo ""
    echo ""
    print_header "✅ نصب با موفقیت انجام شد!"
    
    show_credentials
    show_urls
    show_nginx_config
    show_post_install_steps
    show_useful_commands
    show_cron_jobs
    
    # Save credentials to file
    local creds_file="$PROJECT_DIR/CREDENTIALS.txt"
    local server_ip=$(hostname -I | awk '{print $1}')
    cat > "$creds_file" << EOF
# RAG-Ingest Credentials
# Generated: $(date)
# ⚠️ این فایل را در جای امن ذخیره کنید و سپس حذف کنید!

Domain: ${DOMAIN_NAME}

Django Admin:
  Username: admin
  Password: admin123 (تغییر دهید!)
  Mobile: 09123456789 (تغییر دهید!)

Database:
  Password: ${DB_PASSWORD}

MinIO (External):
  Endpoint: ${MINIO_ENDPOINT}
  Access Key: ${MINIO_ACCESS_KEY}
  Secret Key: ${MINIO_SECRET_KEY}
  Bucket: ${MINIO_BUCKET}

Bale Safir API:
  Client ID: ${BALE_CLIENT_ID:-"تنظیم نشده"}
  Client Secret: ${BALE_CLIENT_SECRET:-"تنظیم نشده"}

================================================================================
اطلاعات مانیتورینگ - برای سرور مانیتورینگ (10.10.10.40)
================================================================================

Server IP: ${server_ip}

Exporters (برای Prometheus):
  • Node Exporter:       http://${server_ip}:9100/metrics
  • PostgreSQL Exporter: http://${server_ip}:9187/metrics
  • Redis Exporter:      http://${server_ip}:9121/metrics
  • cAdvisor:            http://${server_ip}:8080/metrics

Promtail (برای Loki):
  • Loki Endpoint: http://10.10.10.40:3100
  • Config File: /srv/deployment/promtail-config.yml
  • Label: server="ingest"

پیکربندی Prometheus (اضافه کنید به prometheus.yml):

scrape_configs:
  - job_name: 'node-exporter-ingest'
    static_configs:
      - targets: ['${server_ip}:9100']
        labels:
          server: 'ingest'
          environment: 'production'

  - job_name: 'postgres-exporter-ingest'
    static_configs:
      - targets: ['${server_ip}:9187']
        labels:
          server: 'ingest'
          db_name: 'ingest-db'
          environment: 'production'

  - job_name: 'redis-exporter-ingest'
    static_configs:
      - targets: ['${server_ip}:9121']
        labels:
          server: 'ingest'
          redis_instance: 'ingest-redis'
          environment: 'production'

  - job_name: 'cadvisor-ingest'
    static_configs:
      - targets: ['${server_ip}:8080']
        labels:
          server: 'ingest'
          environment: 'production'

نکات مهم:
  • مطمئن شوید Loki در 10.10.10.40:3100 در حال اجرا است
  • Promtail به صورت خودکار لاگ‌ها را به Loki ارسال می‌کند
  • تمام Exporterها با network_mode: host اجرا می‌شوند
================================================================================
EOF
    chmod 600 "$creds_file"
    
    echo ""
    print_warning "اطلاعات دسترسی در فایل زیر ذخیره شد:"
    echo -e "  ${CYAN}$creds_file${NC}"
    print_warning "این فایل را در جای امن ذخیره کنید و سپس حذف کنید!"
    echo ""
    
    print_success "🎉 سیستم آماده استفاده است!"
}

# Run main function
main "$@"
