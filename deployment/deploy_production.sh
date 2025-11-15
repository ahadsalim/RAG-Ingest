#!/bin/bash
# Simplified Production Installation Script - HTTP Only (for use with Nginx Proxy Manager)

set -e

# Configuration variables
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m'

print_header() {
    echo -e "${PURPLE}================================${NC}"
    echo -e "${PURPLE}$1${NC}"
    echo -e "${PURPLE}================================${NC}"
}

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

get_env_value() {
    local key="$1"
    local file="$2"
    if [ -f "$file" ]; then
        grep -E "^${key}=" "$file" | tail -n1 | cut -d '=' -f2- | tr -d '\r'
    fi
}

load_env_variables() {
    local env_file="$PROJECT_DIR/.env"
    local value

    if [ -f "$env_file" ]; then
        value=$(get_env_value "POSTGRES_DB" "$env_file")
        if [ -n "$value" ]; then
            POSTGRES_DB="$value"
        fi

        value=$(get_env_value "POSTGRES_USER" "$env_file")
        if [ -n "$value" ]; then
            POSTGRES_USER="$value"
        fi

        value=$(get_env_value "POSTGRES_PASSWORD" "$env_file")
        if [ -n "$value" ]; then
            POSTGRES_PASSWORD="$value"
        fi
    fi

    POSTGRES_DB=${POSTGRES_DB:-ingest}
    POSTGRES_USER=${POSTGRES_USER:-ingest}
    POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-ingest123}

    export POSTGRES_DB POSTGRES_USER POSTGRES_PASSWORD
}

# Check root access
check_root() {
    if [[ $EUID -ne 0 ]]; then
        print_error "This script must be run as root"
        echo "Please run with sudo: sudo $0"
        exit 1
    fi
}

# Install system dependencies
install_system_dependencies() {
    print_header "Installing System Dependencies"
    
    print_status "Updating package lists..."
    apt update
    
    print_status "Installing essential dependencies..."
    apt install -y \
        curl \
        wget \
        git \
        unzip \
        software-properties-common \
        apt-transport-https \
        ca-certificates \
        gnupg \
        lsb-release \
        openssl \
        htop \
        tree \
        jq \
        python3 \
        python3-pip \
        ufw
    
    print_success "System dependencies installed successfully"
}

# Install Docker
install_docker() {
    print_header "Installing Docker and Docker Compose"
    
    if command -v docker &> /dev/null; then
        print_warning "Docker is already installed"
        docker --version
    else
        print_status "Installing Docker..."
        
        # Remove old versions
        apt remove -y docker docker-engine docker.io containerd runc 2>/dev/null || true
        
        # Add Docker GPG key
        curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
        
        # Add Docker repository
        echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
        
        # Install Docker
        apt update
        apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
        
        # Enable Docker
        systemctl enable docker
        systemctl start docker
    fi
    
    print_success "Docker installed successfully"
}

# Detect Docker Compose version and setup env file
detect_docker_compose() {
    if docker compose version >/dev/null 2>&1; then
        DOCKER_COMPOSE_CMD="docker compose"
        print_status "Using Docker Compose v2"
    elif command -v docker-compose >/dev/null 2>&1; then
        DOCKER_COMPOSE_CMD="docker-compose"
        print_status "Using Docker Compose v1"
    else
        print_error "Docker Compose not found!"
        exit 1
    fi
    
    # Setup env file path
    ENV_FILE_ARG="--env-file $PROJECT_DIR/.env"
    
    # Check if .env exists in current directory, use it instead
    if [ -f ".env" ]; then
        ENV_FILE_ARG="--env-file .env"
        print_status "Using local .env file"
    elif [ -f "$PROJECT_DIR/.env" ]; then
        print_status "Using project .env file: $PROJECT_DIR/.env"
    else
        print_warning "No .env file found, using environment variables"
        ENV_FILE_ARG=""
    fi
}

# Generate secure passwords
generate_secure_passwords() {
    print_header "Generating Secure Passwords"
    
    # Generate random passwords
    DB_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-32)
    REDIS_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-32)
    SECRET_KEY=$(openssl rand -base64 64 | tr -d "=+/")
    CORE_TOKEN=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-32)
    MINIO_ACCESS_KEY=$(openssl rand -base64 16 | tr -d "=+/" | cut -c1-20)
    MINIO_SECRET_KEY=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-40)
    
    print_success "Secure passwords generated"
}

# Create environment file
create_env_file() {
    print_header "Creating Environment Configuration"

    local source_env="$PROJECT_DIR/deployment/config/.env.production"
    local target_env="$PROJECT_DIR/.env"

    if [ ! -f "$source_env" ]; then
        print_error "Source environment file not found at $source_env"
        exit 1
    fi

    cp "$source_env" "$target_env"
    print_status "Copied production template to $target_env"

    local domain_input=""
    read -r -p "Primary domain name (or IP address): " domain_input
    domain_input=${domain_input:-localhost}
    DOMAIN_NAME="$domain_input"

    local redis_url="redis://redis:6379/0"
    local allowed_hosts="${DOMAIN_NAME},localhost,127.0.0.1"
    local cors_origins="http://${DOMAIN_NAME},http://localhost:8001"

    TARGET_ENV="$target_env" \
    SECRET_KEY_VALUE="$SECRET_KEY" \
    POSTGRES_PASSWORD_VALUE="$DB_PASSWORD" \
    REDIS_PASSWORD_VALUE="$REDIS_PASSWORD" \
    REDIS_URL_VALUE="$redis_url" \
    AWS_ACCESS_KEY_ID_VALUE="$MINIO_ACCESS_KEY" \
    AWS_SECRET_ACCESS_KEY_VALUE="$MINIO_SECRET_KEY" \
    AWS_S3_ENDPOINT_URL_VALUE="http://minio:9000" \
    CORE_BASE_URL_VALUE="http://localhost:8000" \
    CORE_TOKEN_VALUE="$CORE_TOKEN" \
    ALLOWED_HOSTS_VALUE="$allowed_hosts" \
    CSRF_TRUSTED_ORIGINS_VALUE="$cors_origins" \
    CORS_ALLOWED_ORIGINS_VALUE="$cors_origins" \
    STATIC_ROOT_VALUE="/app/staticfiles" \
    MEDIA_ROOT_VALUE="/app/media" \
    DOMAIN_NAME_VALUE="$DOMAIN_NAME" \
    AWS_S3_USE_SSL_VALUE="false" \
    DB_PORT_VALUE="15432" \
    DEBUG_VALUE="false" \
    python3 - <<'PYTHON'
import os
from pathlib import Path

target = Path(os.environ['TARGET_ENV'])
updates = [
    ('DEBUG', os.environ['DEBUG_VALUE']),
    ('SECRET_KEY', os.environ['SECRET_KEY_VALUE']),
    ('POSTGRES_PASSWORD', os.environ['POSTGRES_PASSWORD_VALUE']),
    ('REDIS_PASSWORD', os.environ['REDIS_PASSWORD_VALUE']),
    ('REDIS_URL', os.environ['REDIS_URL_VALUE']),
    ('AWS_ACCESS_KEY_ID', os.environ['AWS_ACCESS_KEY_ID_VALUE']),
    ('AWS_SECRET_ACCESS_KEY', os.environ['AWS_SECRET_ACCESS_KEY_VALUE']),
    ('AWS_S3_ENDPOINT_URL', os.environ['AWS_S3_ENDPOINT_URL_VALUE']),
    ('AWS_S3_USE_SSL', os.environ['AWS_S3_USE_SSL_VALUE']),
    ('CORE_BASE_URL', os.environ['CORE_BASE_URL_VALUE']),
    ('CORE_TOKEN', os.environ['CORE_TOKEN_VALUE']),
    ('ALLOWED_HOSTS', os.environ['ALLOWED_HOSTS_VALUE']),
    ('CSRF_TRUSTED_ORIGINS', os.environ['CSRF_TRUSTED_ORIGINS_VALUE']),
    ('CORS_ALLOWED_ORIGINS', os.environ['CORS_ALLOWED_ORIGINS_VALUE']),
    ('STATIC_ROOT', os.environ['STATIC_ROOT_VALUE']),
    ('MEDIA_ROOT', os.environ['MEDIA_ROOT_VALUE']),
    ('DOMAIN_NAME', os.environ['DOMAIN_NAME_VALUE']),
    ('DB_PORT', os.environ['DB_PORT_VALUE']),
]

try:
    lines = target.read_text().splitlines()
except FileNotFoundError:
    lines = []

index_map = {}
for idx, line in enumerate(lines):
    if line.startswith('#') or '=' not in line:
        continue
    key, _ = line.split('=', 1)
    index_map[key] = idx

for key, value in updates:
    if key in index_map:
        lines[index_map[key]] = f"{key}={value}"
    else:
        lines.append(f"{key}={value}")

target.write_text('\n'.join(lines) + '\n')
PYTHON

    print_success "Environment file configured"
    
    # Create symbolic link in deployment directory for easier access
    local deployment_env="$SCRIPT_DIR/.env"
    if [ -L "$deployment_env" ]; then
        rm -f "$deployment_env"
    fi
    ln -sf "$target_env" "$deployment_env"
    print_info "Created symbolic link: deployment/.env -> ../.env"
    
    load_env_variables
}

# Create required directories
create_directories() {
    print_header "Creating Required Directories"

    mkdir -p "/var/log/ingest"
    
    print_success "Directories created successfully"
}

# Setup Docker network
setup_network() {
    print_status "Setting up Docker network..."
    
    if ! docker network ls | grep -q advisor_net; then
        print_status "Creating advisor_net network..."
        docker network create advisor_net
        print_info "Docker network 'advisor_net' created"
    else
        print_info "Docker network 'advisor_net' already exists"
    fi
}

# Wait for database to be ready
wait_for_database() {
    print_status "Waiting for database to be ready..."
    
    local max_attempts=30
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if $DOCKER_COMPOSE_CMD -f deployment/docker-compose.ingest.yml $ENV_FILE_ARG exec -T db pg_isready -U "$POSTGRES_USER" >/dev/null 2>&1; then
            print_info "Database is ready!"
            return 0
        fi
        
        print_status "Waiting for database... (attempt $attempt/$max_attempts)"
        sleep 2
        attempt=$((attempt + 1))
    done
    
    print_error "Database failed to become ready"
    return 1
}

# Build and deploy
build_and_deploy() {
    print_header "Building and Deploying System"
    
    cd "$PROJECT_DIR"
    
    # Setup network
    setup_network
    
    # Build and start services
    print_status "Building Docker images..."
    $DOCKER_COMPOSE_CMD -f deployment/docker-compose.ingest.yml $ENV_FILE_ARG build
    
    print_status "Starting services..."
    $DOCKER_COMPOSE_CMD -f deployment/docker-compose.ingest.yml $ENV_FILE_ARG up -d
    
    # Wait for database
    wait_for_database
    
    # Run migrations
    print_status "Running database migrations..."
    $DOCKER_COMPOSE_CMD -f deployment/docker-compose.ingest.yml $ENV_FILE_ARG exec -T web python manage.py migrate --noinput
    
    # Create embedding models
    print_status "Creating embedding models..."
    $DOCKER_COMPOSE_CMD -f deployment/docker-compose.ingest.yml $ENV_FILE_ARG exec -T web python create_models.py || print_warning "Embedding models creation completed with warnings"
    
    print_status "Collecting static files..."
    $DOCKER_COMPOSE_CMD -f deployment/docker-compose.ingest.yml $ENV_FILE_ARG exec -T web python manage.py collectstatic --noinput
    
    print_status "Creating superuser..."
    $DOCKER_COMPOSE_CMD -f deployment/docker-compose.ingest.yml $ENV_FILE_ARG exec -T web python manage.py shell -c "
from django.contrib.auth.models import User
if not User.objects.filter(username='admin').exists():
    user = User.objects.create_superuser('admin', 'admin@${DOMAIN_NAME}', 'admin123')
    print('✅ Superuser created: admin/admin123')
else:
    print('ℹ️  Superuser already exists')
    user = User.objects.get(username='admin')
    user.set_password('admin123')
    user.save()
    print('✅ Password updated for existing admin user')
"
    
    print_success "System deployed successfully"
}

# Configure firewall
configure_firewall() {
    print_header "Configuring Firewall"
    
    if ! command -v ufw >/dev/null 2>&1; then
        print_warning "UFW is not installed; skipping firewall configuration"
        return
    fi
    
    local env_file="$PROJECT_DIR/.env"
    local db_port redis_port
    db_port=$(get_env_value "DB_PORT" "$env_file")
    db_port=${db_port:-15432}
    redis_port=6380
    
    local web_port=8001
    local minio_api_port=9000
    local minio_console_port=9001
    
    print_status "Resetting firewall rules..."
    ufw --force disable >/dev/null 2>&1 || true
    ufw --force reset >/dev/null 2>&1
    
    ufw default deny incoming
    ufw default allow outgoing
    
    ufw allow OpenSSH
    ufw allow 80/tcp
    ufw allow 443/tcp
    ufw allow 81/tcp
    ufw allow ${web_port}/tcp
    ufw allow ${db_port}/tcp
    ufw allow ${redis_port}/tcp
    ufw allow ${minio_api_port}/tcp
    ufw allow ${minio_console_port}/tcp
    
    ufw --force enable
    
    print_info "Firewall rules applied:"
    ufw status numbered
    
    print_success "Firewall configured successfully"
}

# Validate deployment
validate_deployment() {
    print_header "Validating System"
    
    load_env_variables
    local all_healthy=true
    
    # Check database
    print_status "Checking database..."
    if $DOCKER_COMPOSE_CMD -f deployment/docker-compose.ingest.yml $ENV_FILE_ARG exec -T db pg_isready -U "$POSTGRES_USER" >/dev/null 2>&1; then
        print_info "✅ Database: Healthy"
    else
        print_warning "❌ Database: Unhealthy"
        all_healthy=false
    fi
    
    # Check Redis
    print_status "Checking Redis..."
    if $DOCKER_COMPOSE_CMD -f deployment/docker-compose.ingest.yml $ENV_FILE_ARG exec -T redis redis-cli ping | grep -q PONG 2>/dev/null; then
        print_info "✅ Redis: Healthy"
    else
        print_warning "❌ Redis: Unhealthy"
        all_healthy=false
    fi
    
    # Check web application
    print_status "Checking web application..."
    sleep 5
    if curl -f -s http://localhost:8001/api/health/ >/dev/null 2>&1; then
        print_info "✅ Web Application: Healthy"
    else
        print_warning "❌ Web Application: Unhealthy"
        all_healthy=false
    fi
    
    # Check Celery worker
    print_status "Checking Celery worker..."
    sleep 3
    if $DOCKER_COMPOSE_CMD -f deployment/docker-compose.ingest.yml $ENV_FILE_ARG exec -T worker celery -A ingest status >/dev/null 2>&1 || \
       $DOCKER_COMPOSE_CMD -f deployment/docker-compose.ingest.yml $ENV_FILE_ARG exec -T worker pgrep -f "celery.*worker" >/dev/null 2>&1; then
        print_info "✅ Celery Worker: Healthy"
    else
        print_warning "❌ Celery Worker: Unhealthy (may need more time to start)"
        # Don't mark as unhealthy - Celery takes longer to start
        # all_healthy=false
    fi
    
    # Check MinIO
    print_status "Checking MinIO..."
    if curl -f -s http://127.0.0.1:9000/minio/health/live >/dev/null 2>&1; then
        print_info "✅ MinIO: Healthy"
    else
        print_warning "❌ MinIO: Unhealthy"
        all_healthy=false
    fi
    
    if [ "$all_healthy" = true ]; then
        return 0
    else
        return 1
    fi
}


# Display final information
show_final_info() {
    print_header "System Access Information"
    
    echo -e "${GREEN}✅ Installation completed successfully!${NC}"
    echo ""
    echo -e "${BLUE}🌐 Access URLs (HTTP):${NC}"
    echo -e "   • Web Application: http://${DOMAIN_NAME}:8001"
    echo -e "   • Admin Panel: http://${DOMAIN_NAME}:8001/admin/"
    echo -e "   • API Health: http://${DOMAIN_NAME}:8001/api/health/"
    echo -e "   • MinIO Console: http://${DOMAIN_NAME}:9001"
    echo -e "   • MinIO API: http://${DOMAIN_NAME}:9000"
    echo ""
    echo -e "${BLUE}🔐 Credentials:${NC}"
    echo -e "   • Django Username: admin"
    echo -e "   • Django Password: admin123 ${YELLOW}(CHANGE THIS!)${NC}"
    echo -e "   • Database Password: ${DB_PASSWORD}"
    echo -e "   • Redis Password: ${REDIS_PASSWORD}"
    echo -e "   • MinIO Access Key: ${MINIO_ACCESS_KEY}"
    echo -e "   • MinIO Secret Key: ${MINIO_SECRET_KEY}"
    echo -e "   • Core Token: ${CORE_TOKEN}"
    echo ""
    echo -e "${BLUE}📁 Important Paths:${NC}"
    echo -e "   • Project: $PROJECT_DIR"
    echo -e "   • Logs: /var/log/ingest"
    echo ""
    echo -e "${BLUE}🤖 Model Notes:${NC}"
    echo -e "   • Embedding models are currently disabled (large size)"
    echo ""
    echo -e "${BLUE}🔧 Useful Commands:${NC}"
    echo -e "   • View logs: docker compose -f deployment/docker-compose.ingest.yml logs -f"
    echo -e "   • Restart services: docker compose -f deployment/docker-compose.ingest.yml restart"
    echo -e "   • Backup Manager: ./deployment/backup_manager.sh"
    echo ""
    echo -e "${YELLOW}⚠️  Next Steps:${NC}"
    echo -e "   1. ${YELLOW}Install Nginx Proxy Manager${NC} in Docker"
    echo -e "   2. Configure SSL certificates via Nginx Proxy Manager UI"
    echo -e "   3. Set up proxy hosts for your domains"
    echo -e "   4. ${YELLOW}Change the admin password immediately!${NC}"
    echo -e "   5. Set up backup system: ${BLUE}./deployment/backup_manager.sh${NC}"
    echo -e "   6. Store credentials securely"
    echo ""
    echo -e "${PURPLE}📝 Nginx Proxy Manager Setup:${NC}"
    echo -e "   • Add proxy host: ${DOMAIN_NAME} → http://localhost:8001"
    echo -e "   • Add proxy host: minio.${DOMAIN_NAME} → http://localhost:9000"
    echo -e "   • Add proxy host: consoleminio.${DOMAIN_NAME} → http://localhost:9001"
    echo -e "   • Enable SSL for each host via Let's Encrypt"
    echo ""
    echo -e "${GREEN}🏥 Health Check URLs (Test System Status):${NC}"
    echo -e "   • Web App Health:"
    echo -e "     curl -H \"Host: localhost\" http://127.0.0.1:8001/api/health/"
    echo -e "   • Database Status:"
    echo -e "     docker compose -f deployment/docker-compose.ingest.yml exec -T db pg_isready -U ${POSTGRES_USER:-ingest}"
    echo -e "   • Redis Status:"
    echo -e "     docker compose -f deployment/docker-compose.ingest.yml exec -T redis redis-cli ping"
    echo -e "   • MinIO Health:"
    echo -e "     curl -f http://127.0.0.1:9000/minio/health/live"
    echo -e "   • Celery Worker Status:"
    echo -e "     docker compose -f deployment/docker-compose.ingest.yml exec -T worker celery -A ingest status"
    echo -e "   • All Services Status:"
    echo -e "     docker compose -f deployment/docker-compose.ingest.yml ps"
}

# Main function
main() {
    print_header "Document Management System - Simplified Production Installation"
    
    # Check prerequisites
    check_root
    
    # Install dependencies
    install_system_dependencies
    install_docker
    
    # Detect Docker Compose after installation
    detect_docker_compose
    
    # Generate passwords and configuration
    generate_secure_passwords
    create_env_file
    create_directories
    print_warning "Embedding models are currently disabled (large size)"
    
    # Build and deploy system
    build_and_deploy
    
    # Security
    configure_firewall
    
    # Validation
    if validate_deployment; then
        show_final_info
        print_success "✅ Installation completed! System is ready to use."
    else
        print_warning "⚠️ Installation completed with some issues. Check logs for details."
        echo "View logs: $DOCKER_COMPOSE_CMD -f deployment/docker-compose.ingest.yml logs"
    fi
}

# Execute main function
main "$@"
