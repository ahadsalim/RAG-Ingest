#!/bin/bash

# Quick Start Script for Ingest Project

set -e

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

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check for required files
check_prerequisites() {
    local missing_files=()
    
    if [ ! -f "deploy_development.sh" ]; then
        missing_files+=("deploy_development.sh")
    fi
    
    if [ ! -f "deploy_production.sh" ]; then
        missing_files+=("deploy_production.sh")
    fi
    
    if [ ${#missing_files[@]} -gt 0 ]; then
        print_error "Missing required files:"
        for file in "${missing_files[@]}"; do
            echo "  - $file"
        done
        exit 1
    fi
}

print_header "Ingest Project Quick Start"

# Check prerequisites
check_prerequisites

echo ""
print_info "Select deployment environment:"
echo "1) Development (local development - localhost)"
echo "2) Production (production server with document processing)"
echo ""
read -p "Choose (1-2): " choice

case $choice in
    1)
        print_info "Setting up Development environment..."
        if chmod +x deploy_development.sh && ./deploy_development.sh; then
            print_success "Development environment deployed successfully!"
        else
            print_error "Error deploying Development environment"
            exit 1
        fi
        ;;
    2)
        print_info "Setting up Production environment with document processing..."
        echo "⚠️  Warning: This operation requires root access and will configure:"
        echo "   • Complete system installation"
        echo "   • Document processing capabilities"
        echo "   • MinIO storage with secure credentials"
        echo "   • SSL certificates and security"
        read -p "Continue? (y/N): " confirm
        if [[ $confirm =~ ^[Yy]$ ]]; then
            if chmod +x deploy_production.sh && sudo ./deploy_production.sh; then
                print_success "Production environment with document processing deployed successfully!"
            else
                print_error "Error deploying Production environment"
                exit 1
            fi
        else
            echo "Operation cancelled"
            exit 0
        fi
        ;;
    *)
        print_error "Invalid selection"
        exit 1
        ;;
esac

echo ""
print_success "Deployment completed successfully!"
echo ""
print_header "Useful Information"
echo ""
echo "🔗 Available Resources:"
[ -f "backup_manager.sh" ] && echo "  💾 Backup Manager: ./backup_manager.sh"
echo ""
echo "🎯 Next Steps:"
echo "  1. Login to admin panel with admin/admin123"
echo "  2. Change default password"
echo "  3. Configure system settings"
echo "  4. Start uploading documents"
