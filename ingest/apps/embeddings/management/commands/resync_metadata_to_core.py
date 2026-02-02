"""
Management command to resync metadata for TextEntry and QAEntry chunks to Core.
This fixes the missing unit_type issue in existing nodes.
"""
from django.core.management.base import BaseCommand
from django.db.models import Q
from ingest.apps.embeddings.models import Embedding, CoreConfig
from ingest.apps.embeddings.models_synclog import SyncLog
from ingest.apps.documents.models import Chunk
from ingest.core.sync.payload_builder import build_summary_payload
import requests
import hashlib
import time


class Command(BaseCommand):
    help = 'Resync metadata for TextEntry and QAEntry chunks to Core (fix missing unit_type)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without actually doing it',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=50,
            help='Number of embeddings to process in each batch (default: 50)',
        )
        parser.add_argument(
            '--limit',
            type=int,
            help='Limit the number of embeddings to process (for testing)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        batch_size = options['batch_size']
        limit = options.get('limit')
        
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('🔄 Resync Metadata to Core'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        
        if dry_run:
            self.stdout.write(self.style.WARNING('⚠️  DRY RUN MODE - No changes will be made'))
        
        # Get Core config
        config = CoreConfig.get_config()
        if not config or not config.is_active:
            self.stdout.write(self.style.ERROR('❌ Core sync is disabled'))
            return
        
        self.stdout.write(f'Core API: {config.core_api_url}')
        self.stdout.write(f'Batch Size: {batch_size}')
        
        # Find TextEntry and QAEntry chunks that are synced
        chunks = Chunk.objects.filter(
            Q(textentry__isnull=False) | Q(qaentry__isnull=False)
        ).exclude(
            node_id__isnull=True
        ).select_related('textentry', 'qaentry')
        
        if limit:
            chunks = chunks[:limit]
            self.stdout.write(f'Limit: {limit}')
        
        total_chunks = chunks.count()
        self.stdout.write(f'\n📊 Found {total_chunks} TextEntry/QAEntry chunks to resync')
        
        if total_chunks == 0:
            self.stdout.write(self.style.SUCCESS('✅ Nothing to resync'))
            return
        
        # Process in batches
        processed = 0
        updated = 0
        deleted_recreated = 0
        failed = 0
        skipped = 0
        
        for i in range(0, total_chunks, batch_size):
            batch = chunks[i:i + batch_size]
            self.stdout.write(f'\n📦 Processing batch {i//batch_size + 1} ({i+1}-{min(i+batch_size, total_chunks)} of {total_chunks})')
            
            for chunk in batch:
                processed += 1
                
                # Get embedding for this chunk
                from django.contrib.contenttypes.models import ContentType
                chunk_ct = ContentType.objects.get_for_model(Chunk)
                embedding = Embedding.objects.filter(
                    content_type=chunk_ct,
                    object_id=chunk.id,
                    synced_to_core=True
                ).first()
                
                if not embedding:
                    skipped += 1
                    continue
                
                # Build new payload with fixed metadata
                payload = build_summary_payload(embedding)
                if not payload:
                    self.stdout.write(self.style.WARNING(f'  ⚠️  Could not build payload for chunk {chunk.id}'))
                    failed += 1
                    continue
                
                # Try to update in Core (POST /api/v1/sync/embeddings)
                if not dry_run:
                    success = self._update_in_core(config, payload, chunk)
                    if success:
                        updated += 1
                        self.stdout.write(f'  ✅ Updated chunk {str(chunk.id)[:8]}... ({chunk.textentry_id or chunk.qaentry_id})')
                    else:
                        # If update fails, try delete and recreate
                        self.stdout.write(f'  ⚠️  Update failed, trying delete+recreate for chunk {str(chunk.id)[:8]}...')
                        success = self._delete_and_recreate(config, payload, chunk)
                        if success:
                            deleted_recreated += 1
                            self.stdout.write(f'  ✅ Deleted and recreated chunk {str(chunk.id)[:8]}...')
                        else:
                            failed += 1
                            self.stdout.write(self.style.ERROR(f'  ❌ Failed to resync chunk {str(chunk.id)[:8]}...'))
                else:
                    self.stdout.write(f'  [DRY RUN] Would update chunk {str(chunk.id)[:8]}... (type: {payload["document_type"]})')
                    updated += 1
            
            # Small delay between batches
            if not dry_run and i + batch_size < total_chunks:
                time.sleep(0.5)
        
        # Summary
        self.stdout.write(self.style.SUCCESS('\n' + '=' * 70))
        self.stdout.write(self.style.SUCCESS('📊 Summary'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(f'Total processed: {processed}')
        self.stdout.write(self.style.SUCCESS(f'✅ Updated: {updated}'))
        if deleted_recreated > 0:
            self.stdout.write(self.style.WARNING(f'🔄 Deleted+Recreated: {deleted_recreated}'))
        if skipped > 0:
            self.stdout.write(self.style.WARNING(f'⏭️  Skipped (no embedding): {skipped}'))
        if failed > 0:
            self.stdout.write(self.style.ERROR(f'❌ Failed: {failed}'))
        
        if not dry_run:
            self.stdout.write(self.style.SUCCESS('\n✅ Resync completed!'))
        else:
            self.stdout.write(self.style.WARNING('\n⚠️  DRY RUN completed - no changes were made'))
    
    def _update_in_core(self, config, payload, chunk):
        """Update node in Core using POST /api/v1/sync/embeddings"""
        try:
            headers = {'Content-Type': 'application/json'}
            if config.core_api_key:
                headers['X-API-Key'] = config.core_api_key
            
            url = f"{config.core_api_url}/api/v1/sync/embeddings"
            response = requests.post(
                url,
                json={'embeddings': [payload], 'sync_type': 'metadata_update'},
                headers=headers,
                timeout=10
            )
            
            return response.status_code in [200, 201]
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'    Error updating in Core: {e}'))
            return False
    
    def _delete_and_recreate(self, config, payload, chunk):
        """Delete node from Core and recreate with new metadata"""
        try:
            headers = {'Content-Type': 'application/json'}
            if config.core_api_key:
                headers['X-API-Key'] = config.core_api_key
            
            # Convert UUID to Point ID
            node_id = str(chunk.node_id)
            md5_hash = hashlib.md5(node_id.encode()).hexdigest()
            point_id = int(md5_hash[:16], 16)
            
            # Delete
            delete_url = f"{config.core_api_url}/api/v1/sync/node/{point_id}"
            delete_response = requests.delete(delete_url, headers=headers, timeout=10)
            
            if delete_response.status_code not in [200, 204, 404]:
                return False
            
            # Small delay
            time.sleep(0.2)
            
            # Recreate
            create_url = f"{config.core_api_url}/api/v1/sync/embeddings"
            create_response = requests.post(
                create_url,
                json={'embeddings': [payload], 'sync_type': 'incremental'},
                headers=headers,
                timeout=10
            )
            
            return create_response.status_code in [200, 201]
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'    Error in delete+recreate: {e}'))
            return False
