#!/bin/bash

# سازماندهی و پاکسازی فایل‌های پروژه
echo "🧹 Organizing and Cleaning Up Project Files"
echo "==========================================="

# Create organized directory structure
echo "📁 Creating organized directory structure..."
mkdir -p /srv/scripts/{deployment,optimization,fixes,utilities}
mkdir -p /srv/Documentation/{guides,reports}
mkdir -p /srv/tests/performance

# Move scripts to appropriate folders
echo "📦 Organizing scripts..."

# Move optimization scripts
[ -f "/srv/scripts/apply_optimizations.sh" ] && mv /srv/scripts/apply_optimizations.sh /srv/scripts/optimization/ 2>/dev/null
[ -f "/srv/scripts/deploy_optimizations.sh" ] && mv /srv/scripts/deploy_optimizations.sh /srv/scripts/optimization/ 2>/dev/null
[ -f "/srv/scripts/quick_apply_optimizations.sh" ] && mv /srv/scripts/quick_apply_optimizations.sh /srv/scripts/optimization/ 2>/dev/null

# Move fix scripts
[ -f "/srv/scripts/fix_synclog_delete.sh" ] && mv /srv/scripts/fix_synclog_delete.sh /srv/scripts/fixes/ 2>/dev/null
[ -f "/srv/scripts/fix_synclog_issue.sh" ] && mv /srv/scripts/fix_synclog_issue.sh /srv/scripts/fixes/ 2>/dev/null

# Delete empty/duplicate files
echo "🗑️ Removing empty and duplicate files..."
find /srv -name "*.sh" -size 0 -delete 2>/dev/null
find /srv -name "*~" -delete 2>/dev/null
find /srv -name "*.pyc" -delete 2>/dev/null
find /srv -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null

# Remove duplicate scripts from root
[ -f "/srv/apply_optimizations.sh" ] && rm /srv/apply_optimizations.sh
[ -f "/srv/quick_apply_optimizations.sh" ] && rm /srv/quick_apply_optimizations.sh
[ -f "/srv/fix_synclog_issue.sh" ] && rm /srv/fix_synclog_issue.sh
[ -f "/srv/deploy_optimizations.sh" ] && rm /srv/deploy_optimizations.sh

# Organize documentation
echo "📚 Organizing documentation..."
[ -f "/srv/Documentation/PERFORMANCE_OPTIMIZATION_REPORT.md" ] && mv /srv/Documentation/PERFORMANCE_OPTIMIZATION_REPORT.md /srv/Documentation/reports/ 2>/dev/null
[ -f "/srv/Documentation/PERFORMANCE_ANALYSIS.md" ] && mv /srv/Documentation/PERFORMANCE_ANALYSIS.md /srv/Documentation/reports/ 2>/dev/null

# Create README for scripts directory
cat > /srv/scripts/README.md << 'EOF'
# Scripts Directory

## Directory Structure

- **deployment/** - Scripts for deploying the application
- **optimization/** - Performance optimization scripts
- **fixes/** - Bug fix and issue resolution scripts
- **utilities/** - General utility scripts

## Important Scripts

### Optimization Scripts
- `optimization/quick_apply_optimizations.sh` - Quick apply optimizations to running containers
- `optimization/deploy_optimizations.sh` - Full deployment with optimizations

### Fix Scripts
- `fixes/fix_synclog_delete.sh` - Fix LegalUnit deletion issue with SyncLog

## Usage

All scripts should be run from the `/srv` directory:

```bash
bash scripts/optimization/quick_apply_optimizations.sh
```
EOF

echo "✅ Project organized and cleaned up!"
echo ""
echo "📁 New structure:"
tree -L 2 /srv/scripts/ 2>/dev/null || ls -la /srv/scripts/
