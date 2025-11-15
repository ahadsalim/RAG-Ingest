#!/bin/bash

# Installation Script for Legal Document Management System - Development Environment

set -e

# Configuration variables
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="$SCRIPT_DIR/docker-compose.dev.yml"
MODELS_DIR="$PROJECT_DIR/ingest/models"

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

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Detect Docker Compose version
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
}

# Check Docker installation
check_docker() {
    print_header "Checking Docker"
    
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed"
        echo "Please install Docker first:"
        echo "https://docs.docker.com/get-docker/"
        exit 1
    fi
    
    # Detect Docker Compose
    detect_docker_compose
    
    print_success "Docker and Docker Compose are available"
    docker --version
    $DOCKER_COMPOSE_CMD version
}

# Install system dependencies (optional for development)
install_dev_dependencies() {
    print_header "Installing Development Dependencies"
    
    # Check operating system
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux
        if command -v apt &> /dev/null; then
            print_status "Installing useful tools for development..."
            sudo apt update
            sudo apt install -y curl wget git tree jq htop
        elif command -v yum &> /dev/null; then
            print_status "Installing useful tools for development..."
            sudo yum install -y curl wget git tree jq htop
        fi
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        if command -v brew &> /dev/null; then
            print_status "Installing useful tools for development..."
            brew install curl wget git tree jq htop
        else
            print_warning "Homebrew is not installed. Additional tools will not be installed."
        fi
    fi
    
    print_success "Development dependencies checked"
}

# Prepare development environment configuration
create_dev_env() {
    print_header "Preparing Development Configuration"
    
    local source_env="$PROJECT_DIR/deployment/config/.env.develop"
    local target_env="$PROJECT_DIR/.env"
    local DB_PASSWORD="ingest123"
    local BRIDGE_TOKEN="dev-bridge-token-12345"

    if [ ! -f "$source_env" ]; then
        print_error "Source environment file not found at $source_env"
        exit 1
    fi

    cp "$source_env" "$target_env"

    print_success ".env copied from deployment/config/.env.develop"
    
    # Create symbolic link in deployment directory for easier access
    local deployment_env="$SCRIPT_DIR/.env"
    if [ -L "$deployment_env" ]; then
        rm -f "$deployment_env"
    fi
    ln -sf "$target_env" "$deployment_env"
    print_status "Created symbolic link: deployment/.env -> ../.env"
}

# Build and run development environment
build_and_run_dev() {
    print_header "Building and Running Development Environment"
    
    print_status "Cleaning up old containers..."
    $DOCKER_COMPOSE_CMD -f "$COMPOSE_FILE" --env-file "$PROJECT_DIR/.env" down -v 2>/dev/null || true
    
    print_status "Building Docker images (with development dependencies)..."
    $DOCKER_COMPOSE_CMD -f "$COMPOSE_FILE" --env-file "$PROJECT_DIR/.env" build --build-arg INSTALL_DEV=true
    
    print_status "Starting services..."
    $DOCKER_COMPOSE_CMD -f "$COMPOSE_FILE" --env-file "$PROJECT_DIR/.env" up -d
    
    print_status "Waiting for services to be ready..."
    sleep 20
    
    print_status "Running migrations..."
    $DOCKER_COMPOSE_CMD -f "$COMPOSE_FILE" --env-file "$PROJECT_DIR/.env" exec -T web python manage.py migrate
    
    print_status "Collecting static files..."
    $DOCKER_COMPOSE_CMD -f "$COMPOSE_FILE" --env-file "$PROJECT_DIR/.env" exec -T web python manage.py collectstatic --noinput
    
    # Create embedding models
    print_status "Creating embedding models..."
    $DOCKER_COMPOSE_CMD -f "$COMPOSE_FILE" --env-file "$PROJECT_DIR/.env" exec -T web python create_models.py || print_warning "Embedding models creation completed with warnings"
    
    # Create sample data
    print_status "Creating sample data..."
    $DOCKER_COMPOSE_CMD -f "$COMPOSE_FILE" --env-file "$PROJECT_DIR/.env" exec -T web python manage.py shell -c "
from ingest.apps.masterdata.models import Jurisdiction, IssuingAuthority, Language, Scheme
from django.contrib.auth.models import Group

# Create user groups
groups = ['Editors', 'Reviewers', 'Administrators']
for group_name in groups:
    group, created = Group.objects.get_or_create(name=group_name)
    if created:
        print(f'Group {group_name} created')
    else:
        print(f'Group {group_name} already exists')

# Create sample jurisdiction
jurisdiction, created = Jurisdiction.objects.get_or_create(
    code='IRN',
    defaults={'name': 'جمهوری اسلامی ایران', 'is_active': True}
)
if created:
    print('✅ Sample jurisdiction created')

# Create sample authority
authority, created = IssuingAuthority.objects.get_or_create(
    short_name='MAJLIS',
    defaults={
        'name': 'مجلس شورای اسلامی',
        'jurisdiction': jurisdiction,
        'is_active': True
    }
)
if created:
    print('✅ Sample authority created')

# Create sample language
language, created = Language.objects.get_or_create(
    code='fa',
    defaults={'name': 'فارسی', 'is_active': True}
)
if created:
    print('✅ Sample language created')

print('✅ Sample data creation completed')
" || print_warning "Sample data may already exist"

    print_status "Creating superuser..."
    $DOCKER_COMPOSE_CMD -f "$COMPOSE_FILE" --env-file "$PROJECT_DIR/.env" exec -T web python manage.py shell << 'EOF'
from django.contrib.auth.models import User
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
    print("Superuser created successfully")
else:
    print("Superuser already exists")
EOF
    
    print_success "Development environment started"
}

# Validate development environment
validate_dev_deployment() {
    print_header "Validating Development Environment"
    
    local all_healthy=true
    
    # Check database
    print_status "Checking database..."
    if $DOCKER_COMPOSE_CMD -f "$COMPOSE_FILE" --env-file "$PROJECT_DIR/.env" exec -T db pg_isready -U ingest_user >/dev/null 2>&1; then
        print_info "✅ Database: Healthy"
    else
        print_warning "❌ Database: Unhealthy"
        all_healthy=false
    fi
    
    # Check Redis
    print_status "Checking Redis..."
    if $DOCKER_COMPOSE_CMD -f "$COMPOSE_FILE" --env-file "$PROJECT_DIR/.env" exec -T redis redis-cli ping | grep -q PONG 2>/dev/null; then
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
    if $DOCKER_COMPOSE_CMD -f "$COMPOSE_FILE" --env-file "$PROJECT_DIR/.env" exec -T worker celery -A ingest inspect ping >/dev/null 2>&1; then
        print_info "✅ Celery Worker: Healthy"
    else
        print_warning "❌ Celery Worker: Unhealthy"
        all_healthy=false
    fi
    
    # Check MinIO
    print_status "Checking MinIO..."
    if curl -f -s http://localhost:9000/minio/health/live >/dev/null 2>&1; then
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

# Display final development information
show_dev_info() {
    print_header "Development Environment Information"
    
    echo -e "${GREEN}✅ Development environment successfully started!${NC}"
    echo ""
    echo -e "${BLUE}🌐 Access URLs:${NC}"
    echo -e "   • Main System: http://localhost:8001"
    echo -e "   • Admin Panel: http://localhost:8001/admin/"
    echo -e "   • API Health: http://localhost:8001/api/health/"
    echo -e "   • MinIO Console: http://localhost:9001"
    echo -e "   • MinIO API: http://localhost:9000"
    echo ""
    echo -e "${BLUE}🔐 Access Credentials:${NC}"
    echo -e "   • Django Admin: admin / admin123"
    echo -e "   • MinIO Console: minioadmin / minioadmin123"
    echo -e "   • Database DSN: postgresql://ingest_user:ingest123@localhost:5432/ingest_dev"
    echo ""
    echo -e "${BLUE}🔧 Useful Commands:${NC}"
    echo -e "   • View status: docker compose -f deployment/docker-compose.dev.yml ps"
    echo -e "   • Restart: docker compose -f deployment/docker-compose.dev.yml restart"
    echo -e "   • Enter container: docker compose -f deployment/docker-compose.dev.yml exec web bash"
    echo -e "   • Run migration: docker compose -f deployment/docker-compose.dev.yml exec web python manage.py migrate"
    echo ""
    echo -e "${BLUE}📁 Important Files:${NC}"
    echo -e "   • Configuration Template: deployment/config/.env.develop"
    echo -e "   • Access Info: dev_credentials.txt"
    echo -e "   • Docker Compose: deployment/docker-compose.dev.yml"
    echo ""
    echo -e "${YELLOW}💡 Development Notes:${NC}"
    echo -e "   • Code changes are live reloaded"
    echo -e "   • DEBUG mode is enabled"
    echo -e "   • All logs are displayed in console"
    echo -e "   • Run migrations for model changes"
}

# Main function
main() {
    print_header "Installing Document Management System - Development Environment"
    
    # Check prerequisites
    check_docker
    
    # Install dependencies
    install_dev_dependencies
    
    # Configure environment
    create_dev_env

    # Build and run
    build_and_run_dev
    # Validation
    if validate_dev_deployment; then
        show_dev_info
        print_success "✅ Development environment is ready! Start coding 🚀"
    else
        print_warning "⚠️ Development environment started with some issues. Check the logs."
        echo "View logs: $DOCKER_COMPOSE_CMD -f $COMPOSE_FILE --env-file $PROJECT_DIR/.env logs"
    fi
}

# Run main function
main "$@"
