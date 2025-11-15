"""
Management command برای verification نودهای sync شده.
"""
from django.core.management.base import BaseCommand
from ingest.core.sync.sync_service import CoreSyncService
from ingest.apps.embeddings.models import SyncLog


class Command(BaseCommand):
    help = 'بررسی نودهای sync شده در Core'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='تعداد نودها در هر batch'
        )
        parser.add_argument(
            '--max-retries',
            type=int,
            default=3,
            help='حداکثر تعداد retry'
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='بررسی تمام نودهای unverified'
        )
    
    def handle(self, *args, **options):
        batch_size = options['batch_size']
        max_retries = options['max_retries']
        verify_all = options['all']
        
        service = CoreSyncService()
        
        self.stdout.write('=' * 70)
        self.stdout.write(self.style.SUCCESS('🔍 شروع Verification'))
        self.stdout.write('=' * 70)
        
        if verify_all:
            # Verify all unverified nodes
            total_verified = 0
            total_failed = 0
            
            while True:
                result = service.verify_batch(batch_size=batch_size, max_retries=max_retries)
                
                if result['total'] == 0:
                    break
                
                total_verified += result['verified']
                total_failed += result['failed']
                
                self.stdout.write(
                    f"Batch: {result['total']} نود | "
                    f"✅ {result['verified']} verified | "
                    f"❌ {result['failed']} failed"
                )
            
            self.stdout.write('')
            self.stdout.write('=' * 70)
            self.stdout.write(self.style.SUCCESS(f'✅ کل Verified: {total_verified}'))
            self.stdout.write(self.style.ERROR(f'❌ کل Failed: {total_failed}'))
            self.stdout.write('=' * 70)
        else:
            # Verify one batch
            result = service.verify_batch(batch_size=batch_size, max_retries=max_retries)
            
            self.stdout.write('')
            self.stdout.write(f"📊 نتیجه:")
            self.stdout.write(f"   • کل: {result['total']}")
            self.stdout.write(self.style.SUCCESS(f"   • ✅ Verified: {result['verified']}"))
            self.stdout.write(self.style.ERROR(f"   • ❌ Failed: {result['failed']}"))
            self.stdout.write('=' * 70)
        
        # آمار کلی
        stats = self._get_stats()
        self.stdout.write('')
        self.stdout.write('📈 آمار کلی SyncLog:')
        self.stdout.write(f"   • Synced: {stats['synced']}")
        self.stdout.write(f"   • Verified: {stats['verified']}")
        self.stdout.write(f"   • Failed: {stats['failed']}")
        self.stdout.write(f"   • Pending Retry: {stats['pending_retry']}")
        self.stdout.write('=' * 70)
    
    def _get_stats(self):
        return {
            'synced': SyncLog.objects.filter(status='synced').count(),
            'verified': SyncLog.objects.filter(status='verified').count(),
            'failed': SyncLog.objects.filter(status='failed').count(),
            'pending_retry': SyncLog.objects.filter(status='pending_retry').count(),
        }
