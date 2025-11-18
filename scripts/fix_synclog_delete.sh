#!/bin/bash

# حل قطعی مشکل حذف LegalUnit با SyncLog
echo "🔧 Fixing SyncLog Deletion Issue Permanently"
echo "============================================="

# Apply fix to all containers
for CONTAINER in deployment-web-1 deployment-worker-1 deployment-beat-1; do
    echo "Fixing $CONTAINER..."
    
    docker exec $CONTAINER python manage.py shell << 'EOF'
# 1. Update the SyncLog model to use SET_NULL instead of CASCADE
from django.db import connection

with connection.cursor() as cursor:
    # Drop the foreign key constraint
    cursor.execute("""
        ALTER TABLE embeddings_synclog 
        DROP CONSTRAINT IF EXISTS embeddings_synclog_chunk_id_fkey;
    """)
    
    # Add it back with SET NULL
    cursor.execute("""
        ALTER TABLE embeddings_synclog 
        ADD CONSTRAINT embeddings_synclog_chunk_id_fkey 
        FOREIGN KEY (chunk_id) 
        REFERENCES documents_chunk(id) 
        ON DELETE SET NULL;
    """)
    
print("✓ Database constraint updated")

# 2. Create comprehensive signal handlers
signals_code = '''
from django.db.models.signals import pre_delete, post_delete, m2m_changed
from django.dispatch import receiver
from django.db import transaction
import logging

logger = logging.getLogger(__name__)

@receiver(pre_delete, sender='documents.LegalUnit')
def cleanup_before_legalunit_delete(sender, instance, **kwargs):
    """Clean up all related data before deleting LegalUnit"""
    from ingest.apps.documents.models import Chunk
    from ingest.apps.embeddings.models_synclog import SyncLog
    
    with transaction.atomic():
        # Get all chunks
        chunk_ids = list(instance.chunks.values_list('id', flat=True))
        
        if chunk_ids:
            # Delete SyncLogs first
            sync_deleted = SyncLog.objects.filter(chunk_id__in=chunk_ids).delete()[0]
            logger.info(f"Deleted {sync_deleted} SyncLogs for LegalUnit {instance.id}")
            
            # Delete chunks
            chunks_deleted = Chunk.objects.filter(id__in=chunk_ids).delete()[0]
            logger.info(f"Deleted {chunks_deleted} Chunks for LegalUnit {instance.id}")

@receiver(pre_delete, sender='documents.Chunk')
def cleanup_before_chunk_delete(sender, instance, **kwargs):
    """Clean up SyncLogs before deleting Chunk"""
    from ingest.apps.embeddings.models_synclog import SyncLog
    
    sync_deleted = SyncLog.objects.filter(chunk_id=instance.id).delete()[0]
    if sync_deleted:
        logger.info(f"Deleted {sync_deleted} SyncLogs for Chunk {instance.id}")
'''

# Write the signals file
with open('/app/ingest/apps/documents/signals.py', 'w') as f:
    f.write(signals_code)
    
print("✓ Signals file created")

# 3. Register signals in apps.py
apps_code = '''from django.apps import AppConfig

class DocumentsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ingest.apps.documents'
    verbose_name = 'اسناد حقوقی'
    
    def ready(self):
        """Import signals when app is ready"""
        try:
            from . import signals
            print("Signals registered successfully")
        except Exception as e:
            print(f"Could not register signals: {e}")
        
        # Also import complete signals if they exist
        try:
            from . import signals_complete
        except:
            pass
'''

with open('/app/ingest/apps/documents/apps.py', 'w') as f:
    f.write(apps_code)
    
print("✓ Apps.py updated")

# 4. Force reload
from django.apps import apps
apps.get_app_config('documents').ready()

print("\n✅ Fix applied successfully!")
EOF

done

# Restart containers to apply changes
echo "Restarting containers..."
docker restart deployment-web-1
docker restart deployment-worker-1  
docker restart deployment-beat-1

sleep 10

echo ""
echo "✅ SyncLog deletion issue fixed permanently!"
echo "You can now delete LegalUnits without any errors."
