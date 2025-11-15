"""
Management command to backfill validity dates for existing LegalUnit records.
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.timezone import localdate
from datetime import date
from ingest.apps.documents.models import LegalUnit
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Backfill validity dates for existing LegalUnit records'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without actually doing it',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Number of units to process in each batch (default: 100)',
        )
        parser.add_argument(
            '--infer-from-work',
            action='store_true',
            help='Infer valid_from from associated work promulgation date',
        )
        parser.add_argument(
            '--default-valid-from',
            type=str,
            help='Default valid_from date in YYYY-MM-DD format for units without work',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        batch_size = options['batch_size']
        infer_from_work = options['infer_from_work']
        default_valid_from = options['default_valid_from']

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No data will be updated'))

        # Parse default_valid_from if provided
        default_date = None
        if default_valid_from:
            try:
                default_date = date.fromisoformat(default_valid_from)
            except ValueError:
                raise CommandError(f'Invalid date format: {default_valid_from}. Use YYYY-MM-DD')

        self.stdout.write(
            self.style.SUCCESS('Starting LegalUnit validity backfill')
        )

        # Get units without validity dates
        units_without_validity = LegalUnit.objects.filter(
            valid_from__isnull=True,
            valid_to__isnull=True
        )

        total_count = units_without_validity.count()

        if total_count == 0:
            self.stdout.write(
                self.style.WARNING('No LegalUnit records need backfilling.')
            )
            return

        self.stdout.write(
            self.style.SUCCESS(f'Found {total_count} LegalUnit records to backfill')
        )

        if dry_run:
            self._show_backfill_preview(units_without_validity[:10], infer_from_work, default_date)
            return

        updated_count = 0
        error_count = 0

        # Process in batches
        for i in range(0, total_count, batch_size):
            batch = units_without_validity[i:i + batch_size]
            
            self.stdout.write(
                f'Processing batch {i//batch_size + 1} '
                f'({i + 1}-{min(i + batch_size, total_count)} of {total_count})'
            )

            batch_updated, batch_errors = self._process_batch(
                batch, infer_from_work, default_date
            )
            updated_count += batch_updated
            error_count += batch_errors

            self.stdout.write('.', ending='')

        self.stdout.write('')  # New line

        # Summary
        self.stdout.write(
            self.style.SUCCESS(
                f'\nBackfill completed! Updated: {updated_count}, Errors: {error_count}'
            )
        )

        if error_count > 0:
            self.stdout.write(
                self.style.WARNING(
                    f'Check logs for details about {error_count} failed updates.'
                )
            )

    def _show_backfill_preview(self, units, infer_from_work, default_date):
        """Show preview of what would be backfilled."""
        self.stdout.write(self.style.SUCCESS('\nBackfill Preview:'))
        self.stdout.write('-' * 80)
        
        for unit in units:
            valid_from = self._determine_valid_from(unit, infer_from_work, default_date)
            self.stdout.write(
                f"Unit: {unit.path_label[:50]} | "
                f"Would set valid_from: {valid_from or 'None'}"
            )
        
        if len(units) == 10:
            self.stdout.write("... (showing first 10 units)")

    def _process_batch(self, batch, infer_from_work, default_date):
        """Process a batch of units."""
        updated_count = 0
        error_count = 0

        for unit in batch:
            try:
                with transaction.atomic():
                    valid_from = self._determine_valid_from(unit, infer_from_work, default_date)
                    
                    if valid_from:
                        unit.valid_from = valid_from
                        unit.save(update_fields=['valid_from'])
                        updated_count += 1
                        logger.info(f'Set valid_from={valid_from} for unit {unit.id}')
                    
            except Exception as e:
                error_count += 1
                logger.error(f'Error processing unit {unit.id}: {e}')

        return updated_count, error_count

    def _determine_valid_from(self, unit, infer_from_work, default_date):
        """Determine the valid_from date for a unit."""
        valid_from = None
        
        if infer_from_work and unit.work:
            # Try to get promulgation date from work
            if hasattr(unit.work, 'promulgation_date') and unit.work.promulgation_date:
                valid_from = unit.work.promulgation_date
            elif hasattr(unit.work, 'created_at') and unit.work.created_at:
                valid_from = unit.work.created_at.date()
        
        # Try to get from expression if work doesn't have date
        if not valid_from and infer_from_work and unit.expr:
            if hasattr(unit.expr, 'expression_date') and unit.expr.expression_date:
                valid_from = unit.expr.expression_date
            elif hasattr(unit.expr, 'created_at') and unit.expr.created_at:
                valid_from = unit.expr.created_at.date()
        
        # Use default date if nothing else found
        if not valid_from and default_date:
            valid_from = default_date
        
        return valid_from

    def _get_work_promulgation_date(self, work):
        """Get promulgation date from work (implement based on your work model)."""
        # This is a placeholder - implement based on your actual work model fields
        if hasattr(work, 'promulgation_date'):
            return work.promulgation_date
        elif hasattr(work, 'publication_date'):
            return work.publication_date
        elif hasattr(work, 'created_at'):
            return work.created_at.date()
        return None
