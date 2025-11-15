"""
Management command to rebuild all chunks and embeddings with new settings.

This command:
1. Deletes all existing chunks
2. Deletes all existing embeddings
3. Recreates chunks with new chunk_size and overlap settings
4. Creates embeddings for all new chunks with updated model

Usage:
    python manage.py rebuild_chunks_and_embeddings --dry-run  # Preview changes
    python manage.py rebuild_chunks_and_embeddings  # Execute changes
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.conf import settings
import logging
from tqdm import tqdm

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Rebuild all chunks and embeddings with new settings'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes'
        )
        parser.add_argument(
            '--skip-chunks',
            action='store_true',
            help='Skip chunk deletion and recreation (only create embeddings)'
        )
        parser.add_argument(
            '--skip-embeddings',
            action='store_true',
            help='Skip embedding creation (only recreate chunks)'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=10,
            help='Batch size for processing (default: 10)'
        )
    
    def handle(self, *args, **options):
        dry_run = options['dry_run']
        skip_chunks = options['skip_chunks']
        skip_embeddings = options['skip_embeddings']
        batch_size = options['batch_size']
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\n{"="*60}\n'
                f'🔄 REBUILD CHUNKS AND EMBEDDINGS\n'
                f'{"="*60}\n'
                f'Mode: {"DRY RUN" if dry_run else "EXECUTE"}\n'
                f'Chunk Size: {settings.DEFAULT_CHUNK_SIZE}\n'
                f'Chunk Overlap: {settings.DEFAULT_CHUNK_OVERLAP}\n'
                f'Embedding Model: {settings.EMBEDDING_E5_MODEL_NAME}\n'
                f'Embedding Dimension: {settings.EMBEDDING_DIMENSION}\n'
                f'{"="*60}\n'
            )
        )
        
        try:
            from ingest.apps.documents.models import Chunk, LegalUnit
            from ingest.apps.embeddings.models import Embedding
            from ingest.apps.documents.processing.chunking import get_chunk_processing_service
            
            # Step 1: Count and delete chunks
            if not skip_chunks:
                self.stdout.write('\n📦 Step 1: Processing Chunks')
                self._delete_chunks(dry_run)
                if not dry_run:
                    self._recreate_chunks(batch_size)
            else:
                self.stdout.write('\n⏭️  Skipping chunk processing')
            
            # Step 2: Delete and recreate embeddings
            if not skip_embeddings:
                self.stdout.write('\n🔢 Step 2: Processing Embeddings')
                self._delete_embeddings(dry_run)
                if not dry_run:
                    self._create_embeddings(batch_size)
            else:
                self.stdout.write('\n⏭️  Skipping embedding processing')
            
            # Final summary
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n{"="*60}\n'
                    f'✅ Process {"would be" if dry_run else "was"} completed successfully!\n'
                    f'{"="*60}\n'
                )
            )
            
            if dry_run:
                self.stdout.write(
                    self.style.WARNING(
                        '\n⚠️  This was a DRY RUN. No changes were made.\n'
                        'Run without --dry-run to execute changes.\n'
                    )
                )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'\n❌ Error: {str(e)}')
            )
            logger.error(f'Rebuild process failed: {e}', exc_info=True)
            raise
    
    def _delete_chunks(self, dry_run: bool):
        """Delete all existing chunks."""
        from ingest.apps.documents.models import Chunk
        
        chunk_count = Chunk.objects.count()
        self.stdout.write(f'  Found {chunk_count:,} existing chunks')
        
        if chunk_count == 0:
            self.stdout.write('  No chunks to delete')
            return
        
        if dry_run:
            self.stdout.write(f'  Would delete {chunk_count:,} chunks')
        else:
            self.stdout.write(f'  Deleting {chunk_count:,} chunks...')
            Chunk.objects.all().delete()
            self.stdout.write(self.style.SUCCESS(f'  ✅ Deleted {chunk_count:,} chunks'))
    
    def _recreate_chunks(self, batch_size: int):
        """Recreate all chunks with new settings."""
        from ingest.apps.documents.models import LegalUnit
        from ingest.apps.documents.processing.chunking import get_chunk_processing_service
        
        legal_units = LegalUnit.objects.all()
        total_count = legal_units.count()
        
        self.stdout.write(f'  Creating chunks for {total_count:,} legal units...')
        
        chunk_service = get_chunk_processing_service()
        
        success_count = 0
        error_count = 0
        
        with tqdm(total=total_count, desc="Creating chunks") as pbar:
            for unit in legal_units:
                try:
                    result = chunk_service.process_legal_unit(unit.id)
                    if result.get('success'):
                        success_count += 1
                    else:
                        error_count += 1
                except Exception as e:
                    logger.error(f'Error creating chunks for unit {unit.id}: {e}')
                    error_count += 1
                
                pbar.update(1)
        
        self.stdout.write(
            self.style.SUCCESS(
                f'  ✅ Created chunks for {success_count:,} legal units'
            )
        )
        if error_count > 0:
            self.stdout.write(
                self.style.WARNING(
                    f'  ⚠️  Failed for {error_count:,} legal units'
                )
            )
    
    def _delete_embeddings(self, dry_run: bool):
        """Delete all existing embeddings."""
        from ingest.apps.embeddings.models import Embedding
        
        embedding_count = Embedding.objects.count()
        self.stdout.write(f'  Found {embedding_count:,} existing embeddings')
        
        if embedding_count == 0:
            self.stdout.write('  No embeddings to delete')
            return
        
        if dry_run:
            self.stdout.write(f'  Would delete {embedding_count:,} embeddings')
        else:
            self.stdout.write(f'  Deleting {embedding_count:,} embeddings...')
            Embedding.objects.all().delete()
            self.stdout.write(self.style.SUCCESS(f'  ✅ Deleted {embedding_count:,} embeddings'))
    
    def _create_embeddings(self, batch_size: int):
        """Create embeddings for all chunks."""
        from ingest.apps.embeddings.tasks import generate_embeddings_for_new_content
        
        self.stdout.write(f'  Queuing embedding generation task...')
        
        try:
            # Queue the batch embedding task
            result = generate_embeddings_for_new_content.delay(
                model_name=settings.EMBEDDING_E5_MODEL_NAME,
                batch_size=batch_size
            )
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'  ✅ Embedding generation task queued (Task ID: {result.id})'
                )
            )
            
            self.stdout.write(
                self.style.WARNING(
                    f'\n  ℹ️  Embeddings will be generated asynchronously by Celery workers.\n'
                    f'  Monitor progress with: python manage.py embeddings_status\n'
                    f'  Or check Celery logs for task {result.id}\n'
                )
            )
            
        except Exception as e:
            logger.error(f'Error queuing embedding task: {e}')
            self.stdout.write(
                self.style.ERROR(
                    f'  ❌ Failed to queue embedding task: {e}'
                )
            )
