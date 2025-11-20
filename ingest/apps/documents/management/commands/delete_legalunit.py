"""
Management command to safely delete a LegalUnit with all related objects.
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from ingest.apps.documents.models import LegalUnit
from ingest.apps.embeddings.models_synclog import SyncLog
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Safely delete a LegalUnit by its ID, cleaning up SyncLogs first'

    def add_arguments(self, parser):
        parser.add_argument('legalunit_id', type=str, help='UUID of the LegalUnit to delete')
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force deletion without confirmation',
        )

    def handle(self, *args, **options):
        legalunit_id = options['legalunit_id']
        force = options['force']

        try:
            legal_unit = LegalUnit.objects.get(pk=legalunit_id)
        except LegalUnit.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'LegalUnit with ID {legalunit_id} not found'))
            return

        # Show info
        self.stdout.write(f'\n{"="*60}')
        self.stdout.write(f'LegalUnit: {legal_unit.id}')
        self.stdout.write(f'Content: {legal_unit.content[:100]}...' if legal_unit.content else 'No content')
        
        # Count related objects
        chunks_count = legal_unit.chunks.count()
        self.stdout.write(f'Chunks: {chunks_count}')
        
        if chunks_count > 0:
            chunk_ids = list(legal_unit.chunks.values_list('id', flat=True))
            synclog_count = SyncLog.objects.filter(chunk_id__in=chunk_ids).count()
            self.stdout.write(f'SyncLogs: {synclog_count}')
        else:
            synclog_count = 0
        
        files_count = legal_unit.files.count()
        self.stdout.write(f'Files: {files_count}')
        
        self.stdout.write(f'{"="*60}\n')

        # Confirmation
        if not force:
            confirm = input('Are you sure you want to delete this LegalUnit? (yes/no): ')
            if confirm.lower() != 'yes':
                self.stdout.write(self.style.WARNING('Deletion cancelled'))
                return

        # Delete with transaction
        try:
            with transaction.atomic():
                # Step 1: Delete SyncLogs first
                if synclog_count > 0:
                    self.stdout.write('Deleting SyncLogs...')
                    chunk_ids = list(legal_unit.chunks.values_list('id', flat=True))
                    deleted_synclogs = SyncLog.objects.filter(chunk_id__in=chunk_ids).delete()[0]
                    self.stdout.write(self.style.SUCCESS(f'✓ Deleted {deleted_synclogs} SyncLogs'))

                # Step 2: Delete the LegalUnit (will cascade to chunks, files, etc.)
                self.stdout.write('Deleting LegalUnit...')
                legal_unit.delete()
                
                self.stdout.write(self.style.SUCCESS(f'\n✓ Successfully deleted LegalUnit {legalunit_id}'))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\n✗ Error deleting LegalUnit: {e}'))
            logger.error(f'Error deleting LegalUnit {legalunit_id}: {e}', exc_info=True)
            raise
