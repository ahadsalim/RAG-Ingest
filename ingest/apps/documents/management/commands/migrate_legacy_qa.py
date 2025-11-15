"""
Management command to migrate legacy QA data to new FRBR-compatible schema.
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction, connection
from django.contrib.auth.models import User
from ingest.apps.documents.models import QAEntry
from ingest.apps.documents.enums import QAStatus
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Migrate legacy QA entries to new FRBR-compatible schema'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be migrated without actually doing it',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Number of entries to process in each batch (default: 100)',
        )
        parser.add_argument(
            '--legacy-table',
            type=str,
            default='documents_qaentry_old',
            help='Name of the legacy QA table (default: documents_qaentry_old)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        batch_size = options['batch_size']
        legacy_table = options['legacy_table']

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No data will be migrated'))

        self.stdout.write(
            self.style.SUCCESS(f'Starting legacy QA migration from table: {legacy_table}')
        )

        # Check if legacy table exists
        if not self._table_exists(legacy_table):
            self.stdout.write(
                self.style.WARNING(f'Legacy table {legacy_table} does not exist. Nothing to migrate.')
            )
            return

        # Get legacy data
        legacy_entries = self._get_legacy_entries(legacy_table)
        total_count = len(legacy_entries)

        if total_count == 0:
            self.stdout.write(
                self.style.WARNING('No legacy QA entries found.')
            )
            return

        self.stdout.write(
            self.style.SUCCESS(f'Found {total_count} legacy QA entries to migrate')
        )

        if dry_run:
            self._show_migration_preview(legacy_entries[:10])  # Show first 10
            return

        # Migrate data
        migrated_count = 0
        error_count = 0

        for i in range(0, total_count, batch_size):
            batch = legacy_entries[i:i + batch_size]
            
            self.stdout.write(
                f'Processing batch {i//batch_size + 1} '
                f'({i + 1}-{min(i + batch_size, total_count)} of {total_count})'
            )

            batch_migrated, batch_errors = self._migrate_batch(batch)
            migrated_count += batch_migrated
            error_count += batch_errors

            self.stdout.write('.', ending='')

        self.stdout.write('')  # New line

        # Summary
        self.stdout.write(
            self.style.SUCCESS(
                f'\nMigration completed! Migrated: {migrated_count}, Errors: {error_count}'
            )
        )

        if error_count > 0:
            self.stdout.write(
                self.style.WARNING(
                    f'Check logs for details about {error_count} failed migrations.'
                )
            )

    def _table_exists(self, table_name):
        """Check if a table exists in the database."""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*) 
                FROM information_schema.tables 
                WHERE table_name = %s
            """, [table_name])
            return cursor.fetchone()[0] > 0

    def _get_legacy_entries(self, table_name):
        """Get legacy QA entries from the old table."""
        with connection.cursor() as cursor:
            # Adjust column names based on your legacy schema
            cursor.execute(f"""
                SELECT 
                    id, question, answer, status, created_at, updated_at,
                    created_by_id, approved_by_id, approved_at,
                    document_id, legal_unit_id
                FROM {table_name}
                ORDER BY created_at
            """)
            
            columns = [col[0] for col in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def _show_migration_preview(self, entries):
        """Show preview of what would be migrated."""
        self.stdout.write(self.style.SUCCESS('\nMigration Preview:'))
        self.stdout.write('-' * 80)
        
        for entry in entries:
            question_preview = entry['question'][:50] + "..." if len(entry['question']) > 50 else entry['question']
            self.stdout.write(
                f"ID: {entry['id']} | Status: {entry['status']} | Q: {question_preview}"
            )
        
        if len(entries) == 10:
            self.stdout.write("... (showing first 10 entries)")

    def _migrate_batch(self, batch):
        """Migrate a batch of legacy entries."""
        migrated_count = 0
        error_count = 0

        for legacy_entry in batch:
            try:
                with transaction.atomic():
                    self._migrate_single_entry(legacy_entry)
                    migrated_count += 1
            except Exception as e:
                error_count += 1
                logger.error(f'Error migrating entry {legacy_entry["id"]}: {e}')

        return migrated_count, error_count

    def _migrate_single_entry(self, legacy_entry):
        """Migrate a single legacy QA entry to new schema."""
        # Map legacy status to new status
        status_mapping = {
            'draft': QAStatus.DRAFT,
            'pending': QAStatus.UNDER_REVIEW,
            'approved': QAStatus.APPROVED,
            'rejected': QAStatus.REJECTED,
        }
        
        # Get or create users
        created_by = None
        if legacy_entry['created_by_id']:
            try:
                created_by = User.objects.get(id=legacy_entry['created_by_id'])
            except User.DoesNotExist:
                logger.warning(f'User {legacy_entry["created_by_id"]} not found for entry {legacy_entry["id"]}')

        approved_by = None
        if legacy_entry['approved_by_id']:
            try:
                approved_by = User.objects.get(id=legacy_entry['approved_by_id'])
            except User.DoesNotExist:
                logger.warning(f'Approver {legacy_entry["approved_by_id"]} not found for entry {legacy_entry["id"]}')

        # Map legacy document/unit relationships to new FRBR schema
        source_work = None
        source_unit = None
        
        # Try to map legacy document_id to InstrumentWork
        if legacy_entry.get('document_id'):
            source_work = self._map_legacy_document_to_work(legacy_entry['document_id'])
        
        # Try to map legacy legal_unit_id to LegalUnit
        if legacy_entry.get('legal_unit_id'):
            source_unit = self._map_legacy_unit_to_unit(legacy_entry['legal_unit_id'])

        # Create new QA entry
        qa_entry = QAEntry.objects.create(
            question=legacy_entry['question'],
            answer=legacy_entry['answer'],
            status=status_mapping.get(legacy_entry['status'], QAStatus.DRAFT),
            created_by=created_by,
            approved_by=approved_by,
            approved_at=legacy_entry.get('approved_at'),
            source_work=source_work,
            source_unit=source_unit,
            created_at=legacy_entry['created_at'],
            updated_at=legacy_entry['updated_at'],
        )

        logger.info(f'Migrated legacy QA entry {legacy_entry["id"]} to new entry {qa_entry.id}')
        return qa_entry

    def _map_legacy_document_to_work(self, legacy_document_id):
        """Map legacy document ID to InstrumentWork."""
        try:
            # This is a placeholder - implement based on your legacy schema
            # You might need to query a mapping table or use some logic
            # to connect legacy documents to new FRBR Works
            
            from ingest.apps.documents.models import InstrumentWork
            
            # Example: if you have a mapping table or can derive the relationship
            # return InstrumentWork.objects.get(legacy_document_id=legacy_document_id)
            
            # For now, return None - you'll need to implement this based on your data
            logger.warning(f'Legacy document mapping not implemented for document {legacy_document_id}')
            return None
            
        except Exception as e:
            logger.warning(f'Could not map legacy document {legacy_document_id}: {e}')
            return None

    def _map_legacy_unit_to_unit(self, legacy_unit_id):
        """Map legacy legal unit ID to LegalUnit."""
        try:
            from ingest.apps.documents.models import LegalUnit
            
            # Try direct ID mapping first (if IDs are preserved)
            return LegalUnit.objects.get(id=legacy_unit_id)
            
        except LegalUnit.DoesNotExist:
            logger.warning(f'Could not find LegalUnit with ID {legacy_unit_id}')
            return None
        except Exception as e:
            logger.warning(f'Error mapping legacy unit {legacy_unit_id}: {e}')
            return None

    def _cleanup_legacy_table(self, table_name):
        """Optionally cleanup legacy table after successful migration."""
        # This is intentionally not implemented for safety
        # You can manually drop the table after verifying migration success
        self.stdout.write(
            self.style.WARNING(
                f'Legacy table {table_name} preserved. '
                'Drop it manually after verifying migration success.'
            )
        )
