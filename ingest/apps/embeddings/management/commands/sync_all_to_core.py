"""
Management command to sync all embeddings to Core system.
"""
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from ingest.apps.embeddings.models import Embedding, CoreConfig
from ingest.core.sync.sync_service import CoreSyncService


class Command(BaseCommand):
    help = 'Sync all embeddings to Core system with Summary metadata model'

    def add_arguments(self, parser):
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Number of embeddings to sync in each batch (default: 100)'
        )
        
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Reset all sync status before starting (re-sync everything)'
        )
        
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be synced without actually syncing'
        )

    def handle(self, *args, **options):
        batch_size = options['batch_size']
        reset = options['reset']
        dry_run = options['dry_run']
        
        # Check config
        config = CoreConfig.get_config()
        
        if not config.is_active:
            raise CommandError('Core sync is disabled in config. Enable it first.')
        
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('🚀 Starting Sync to Core System'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(f'Core API: {config.core_api_url}')
        self.stdout.write(f'Batch Size: {batch_size}')
        self.stdout.write(f'Auto Sync: {"Enabled" if config.auto_sync_enabled else "Disabled"}')
        self.stdout.write(f'Track Changes: {"Enabled" if config.track_metadata_changes else "Disabled"}')
        self.stdout.write('')
        
        # Test connection first
        self.stdout.write('Testing connection to Core...')
        if not config.test_connection():
            raise CommandError('❌ Cannot connect to Core API. Check your configuration.')
        self.stdout.write(self.style.SUCCESS('✓ Connection successful'))
        self.stdout.write('')
        
        # Get statistics
        total_embeddings = Embedding.objects.count()
        synced_count = Embedding.objects.filter(synced_to_core=True).count()
        unsynced_count = Embedding.objects.filter(synced_to_core=False).count()
        error_count = Embedding.objects.exclude(sync_error='').count()
        
        self.stdout.write('📊 Current Statistics:')
        self.stdout.write(f'   Total Embeddings: {total_embeddings}')
        self.stdout.write(f'   Already Synced: {synced_count}')
        self.stdout.write(f'   Not Synced: {unsynced_count}')
        self.stdout.write(f'   With Errors: {error_count}')
        self.stdout.write('')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('🔍 DRY RUN MODE - No changes will be made'))
            self.stdout.write(f'Would sync {unsynced_count} embeddings')
            return
        
        # Reset if requested
        if reset:
            self.stdout.write(self.style.WARNING('⚠️  Resetting all sync status...'))
            Embedding.objects.all().update(
                synced_to_core=False,
                synced_at=None,
                sync_error='',
                sync_retry_count=0
            )
            unsynced_count = total_embeddings
            self.stdout.write(self.style.SUCCESS('✓ Reset complete'))
            self.stdout.write('')
        
        if unsynced_count == 0:
            self.stdout.write(self.style.SUCCESS('✓ All embeddings are already synced!'))
            return
        
        # Start syncing
        service = CoreSyncService()
        total_synced = 0
        total_errors = 0
        batch_num = 0
        
        self.stdout.write(f'Starting sync of {unsynced_count} embeddings...')
        self.stdout.write('')
        
        while True:
            batch_num += 1
            self.stdout.write(f'Batch {batch_num}... ', ending='')
            
            result = service.sync_new_embeddings(batch_size=batch_size)
            
            if result['status'] == 'nothing_to_sync':
                self.stdout.write(self.style.SUCCESS('Done!'))
                break
            elif result['status'] == 'success':
                synced = result['synced']
                total_synced += synced
                self.stdout.write(self.style.SUCCESS(f'✓ Synced {synced} embeddings'))
            elif result['status'] == 'disabled':
                raise CommandError(f'Sync is disabled: {result["message"]}')
            else:
                total_errors += 1
                error_msg = result.get('error', 'Unknown error')
                self.stdout.write(self.style.ERROR(f'✗ Error: {error_msg}'))
                
                # Ask if should continue
                if batch_num > 1:
                    response = input('\nContinue despite error? [y/N]: ')
                    if response.lower() != 'y':
                        break
                else:
                    break
        
        # Final statistics
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('📊 Sync Complete'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(f'Total Synced: {total_synced}')
        self.stdout.write(f'Total Errors: {total_errors}')
        self.stdout.write(f'Batches Processed: {batch_num}')
        
        # Updated config stats
        config.refresh_from_db()
        self.stdout.write('')
        self.stdout.write('Config Statistics:')
        self.stdout.write(f'   Total Synced (all time): {config.total_synced}')
        self.stdout.write(f'   Total Errors (all time): {config.total_errors}')
        self.stdout.write(f'   Last Successful Sync: {config.last_successful_sync or "Never"}')
        
        if total_errors > 0:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING(f'⚠️  Completed with {total_errors} errors'))
            self.stdout.write('Check sync_error field in Embedding admin for details')
        else:
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS('✓ All embeddings synced successfully!'))
