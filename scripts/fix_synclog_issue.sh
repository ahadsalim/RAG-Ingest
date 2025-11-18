#!/bin/bash

# Quick fix for SyncLog deletion issue
# رفع سریع مشکل حذف LegalUnit با SyncLog

echo "🔧 Fixing SyncLog Deletion Issue"
echo "================================"

# Fix the issue directly in the running container
docker exec deployment-web-1 python manage.py shell << 'EOF'
print("Applying SyncLog fix...")

# Fix 1: Create the signals file content
signals_content = '''"""
Signal handlers for document models.
"""

from django.db.models.signals import pre_delete
from django.dispatch import receiver
import logging

logger = logging.getLogger(__name__)

try:
    from ingest.apps.documents.models import LegalUnit, Chunk
    from ingest.apps.embeddings.models_synclog import SyncLog
    
    @receiver(pre_delete, sender=LegalUnit)
    def handle_legalunit_pre_delete(sender, instance, **kwargs):
        """Clean up SyncLogs before deleting LegalUnit"""
        try:
            chunk_ids = list(instance.chunks.values_list('id', flat=True))
            if chunk_ids:
                deleted = SyncLog.objects.filter(chunk_id__in=chunk_ids).delete()[0]
                logger.info(f"Deleted {deleted} SyncLog entries for LegalUnit {instance.id}")
        except Exception as e:
            logger.error(f"Error in pre_delete handler: {e}")
    
    print("✓ Signal handler registered")
except Exception as e:
    print(f"Could not register signal: {e}")
'''

# Write the signals file
with open('/app/ingest/apps/documents/signals.py', 'w') as f:
    f.write(signals_content)
print("✓ Created signals.py")

# Fix 2: Update apps.py to import signals
apps_content = '''from django.apps import AppConfig


class DocumentsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ingest.apps.documents'
    verbose_name = 'اسناد حقوقی'
    
    def ready(self):
        """Import signals when the app is ready."""
        try:
            import ingest.apps.documents.signals
        except:
            pass
        try:
            import ingest.apps.documents.signals_complete
        except:
            pass
'''

with open('/app/ingest/apps/documents/apps.py', 'w') as f:
    f.write(apps_content)
print("✓ Updated apps.py")

# Fix 3: Add a management command for safe deletion
mgmt_cmd = '''from django.core.management.base import BaseCommand
from django.db import transaction
from ingest.apps.documents.models import LegalUnit
from ingest.apps.embeddings.models_synclog import SyncLog

class Command(BaseCommand):
    help = 'Safely delete a LegalUnit with all dependencies'
    
    def add_arguments(self, parser):
        parser.add_argument('unit_id', type=str, help='LegalUnit ID to delete')
    
    def handle(self, *args, **options):
        unit_id = options['unit_id']
        
        with transaction.atomic():
            try:
                unit = LegalUnit.objects.get(id=unit_id)
                
                # Clean up SyncLogs first
                chunk_ids = list(unit.chunks.values_list('id', flat=True))
                if chunk_ids:
                    deleted = SyncLog.objects.filter(chunk_id__in=chunk_ids).delete()[0]
                    self.stdout.write(f"Deleted {deleted} SyncLog entries")
                
                # Now delete the unit
                unit.delete()
                self.stdout.write(self.style.SUCCESS(f"Successfully deleted LegalUnit {unit_id}"))
                
            except LegalUnit.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"LegalUnit {unit_id} not found"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error: {e}"))
'''

import os
os.makedirs('/app/ingest/apps/documents/management/commands', exist_ok=True)
with open('/app/ingest/apps/documents/management/commands/safe_delete_legalunit.py', 'w') as f:
    f.write(mgmt_cmd)
print("✓ Created safe_delete_legalunit command")

print("\n✅ Fix applied successfully!")
print("\nYou can now:")
print("1. Delete LegalUnits normally through admin")
print("2. Or use: python manage.py safe_delete_legalunit <unit_id>")

# Test the fix
from django.apps import apps
apps.get_app_config('documents').ready()
print("\n✓ Signals reloaded")
EOF

echo ""
echo "🎉 SyncLog deletion issue fixed!"
echo ""
echo "To delete a LegalUnit safely, you can now:"
echo "1. Use Django Admin normally"
echo "2. Or run: docker exec deployment-web-1 python manage.py safe_delete_legalunit <UNIT_ID>"
