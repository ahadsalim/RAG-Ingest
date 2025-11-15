"""
Management command to register changes to legal units.
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from datetime import date
from ingest.apps.documents.models import LegalUnit, LegalUnitChange, InstrumentExpression
from ingest.apps.documents.services.legalunit_changes import LegalUnitChangeService
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Register a change to a legal unit'

    def add_arguments(self, parser):
        parser.add_argument(
            '--unit',
            type=str,
            required=True,
            help='ID of the legal unit to change',
        )
        parser.add_argument(
            '--type',
            type=str,
            required=True,
            choices=['AMEND', 'REPEAL', 'SUBSTITUTE', 'ADD', 'REMOVE'],
            help='Type of change',
        )
        parser.add_argument(
            '--effective',
            type=str,
            required=True,
            help='Effective date in YYYY-MM-DD format',
        )
        parser.add_argument(
            '--note',
            type=str,
            default='',
            help='Note about the change',
        )
        parser.add_argument(
            '--superseded-by',
            type=str,
            help='ID of the unit that supersedes this one (for SUBSTITUTE)',
        )
        parser.add_argument(
            '--source-expression',
            type=str,
            help='ID of the source expression that introduces this change',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without actually doing it',
        )

    def handle(self, *args, **options):
        unit_id = options['unit']
        change_type = options['type']
        effective_date_str = options['effective']
        note = options['note']
        superseded_by_id = options['superseded_by']
        source_expression_id = options['source_expression']
        dry_run = options['dry_run']

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))

        # Parse effective date
        try:
            effective_date = date.fromisoformat(effective_date_str)
        except ValueError:
            raise CommandError(f'Invalid date format: {effective_date_str}. Use YYYY-MM-DD')

        # Get the legal unit
        try:
            unit = LegalUnit.objects.get(id=unit_id)
        except LegalUnit.DoesNotExist:
            raise CommandError(f'LegalUnit with ID {unit_id} does not exist')

        # Get superseded_by unit if provided
        superseded_by = None
        if superseded_by_id:
            try:
                superseded_by = LegalUnit.objects.get(id=superseded_by_id)
            except LegalUnit.DoesNotExist:
                raise CommandError(f'Superseding LegalUnit with ID {superseded_by_id} does not exist')

        # Get source expression if provided
        source_expression = None
        if source_expression_id:
            try:
                source_expression = InstrumentExpression.objects.get(id=source_expression_id)
            except InstrumentExpression.DoesNotExist:
                raise CommandError(f'InstrumentExpression with ID {source_expression_id} does not exist')

        # Validate change type requirements
        if change_type == 'SUBSTITUTE' and not superseded_by:
            raise CommandError('SUBSTITUTE changes require --superseded-by parameter')

        # Show what will be done
        self.stdout.write(self.style.SUCCESS('Change Details:'))
        self.stdout.write(f'  Unit: {unit.path_label} (ID: {unit.id})')
        self.stdout.write(f'  Change Type: {change_type}')
        self.stdout.write(f'  Effective Date: {effective_date}')
        if superseded_by:
            self.stdout.write(f'  Superseded By: {superseded_by.path_label} (ID: {superseded_by.id})')
        if source_expression:
            self.stdout.write(f'  Source Expression: {source_expression} (ID: {source_expression.id})')
        if note:
            self.stdout.write(f'  Note: {note}')

        # Show current validity status
        self.stdout.write(f'\nCurrent Validity:')
        self.stdout.write(f'  Valid From: {unit.valid_from or "Not set"}')
        self.stdout.write(f'  Valid To: {unit.valid_to or "Not set"}')
        self.stdout.write(f'  Is Active: {unit.is_active}')

        if dry_run:
            self.stdout.write(self.style.WARNING('\nDRY RUN - No changes made'))
            return

        # Apply the change
        try:
            with transaction.atomic():
                change = LegalUnitChangeService.apply_change(
                    unit=unit,
                    change_type=change_type,
                    effective_date=effective_date,
                    superseded_by=superseded_by,
                    source_expression=source_expression,
                    note=note
                )

                self.stdout.write(
                    self.style.SUCCESS(f'\nChange registered successfully! Change ID: {change.id}')
                )

                # Show updated validity status
                unit.refresh_from_db()
                self.stdout.write(f'\nUpdated Validity:')
                self.stdout.write(f'  Valid From: {unit.valid_from or "Not set"}')
                self.stdout.write(f'  Valid To: {unit.valid_to or "Not set"}')
                self.stdout.write(f'  Is Active: {unit.is_active}')

                if superseded_by:
                    superseded_by.refresh_from_db()
                    self.stdout.write(f'\nSuperseding Unit Validity:')
                    self.stdout.write(f'  Valid From: {superseded_by.valid_from or "Not set"}')
                    self.stdout.write(f'  Valid To: {superseded_by.valid_to or "Not set"}')
                    self.stdout.write(f'  Is Active: {superseded_by.is_active}')

        except Exception as e:
            raise CommandError(f'Failed to register change: {e}')

    def add_arguments(self, parser):
        super().add_arguments(parser)
        
        # Add examples in help
        parser.epilog = """
Examples:
  # Repeal a unit effective today
  python manage.py register_change --unit 123 --type REPEAL --effective 2024-01-01 --note "Repealed by new law"
  
  # Substitute one unit with another
  python manage.py register_change --unit 123 --type SUBSTITUTE --effective 2024-01-01 --superseded-by 456 --note "Replaced by updated version"
  
  # Amend a unit
  python manage.py register_change --unit 123 --type AMEND --effective 2024-01-01 --source-expression 789 --note "Minor amendment"
  
  # Dry run to see what would happen
  python manage.py register_change --unit 123 --type REPEAL --effective 2024-01-01 --dry-run
        """
