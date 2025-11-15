"""
Management command برای نمایش dashboard sync.
"""
import requests
from django.core.management.base import BaseCommand
from django.db.models import Count
from ingest.apps.embeddings.models import Embedding, CoreConfig, SyncLog, SyncStats


class Command(BaseCommand):
    help = 'نمایش dashboard وضعیت sync'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--save',
            action='store_true',
            help='ذخیره آمار در SyncStats'
        )
    
    def handle(self, *args, **options):
        save_stats = options['save']
        
        self.stdout.write('=' * 80)
        self.stdout.write(self.style.SUCCESS('📊 Dashboard وضعیت Sync'))
        self.stdout.write('=' * 80)
        
        # Local stats
        local_stats = self._get_local_stats()
        
        self.stdout.write('')
        self.stdout.write('📦 وضعیت Ingest (Local):')
        self.stdout.write(f"   • کل Embeddings: {local_stats['total_embeddings']:,}")
        self.stdout.write(f"   • Synced: {local_stats['synced']:,} ({local_stats['sync_percentage']:.1f}%)")
        self.stdout.write(f"   • Verified: {local_stats['verified']:,} ({local_stats['verification_percentage']:.1f}%)")
        self.stdout.write(f"   • Failed: {local_stats['failed']:,}")
        self.stdout.write(f"   • Pending: {local_stats['pending']:,}")
        
        # Core stats
        core_stats = self._get_core_stats()
        
        self.stdout.write('')
        self.stdout.write('☁️  وضعیت Core:')
        if core_stats['total_nodes'] is not None:
            self.stdout.write(f"   • نودها در Qdrant: {core_stats['total_nodes']:,}")
            
            # مقایسه
            diff = core_stats['total_nodes'] - local_stats['synced']
            if diff == 0:
                self.stdout.write(self.style.SUCCESS(f"   • ✅ همگام است"))
            elif diff > 0:
                self.stdout.write(self.style.WARNING(f"   • ⚠️  {diff} نود بیشتر در Core"))
            else:
                self.stdout.write(self.style.ERROR(f"   • ❌ {abs(diff)} نود کمتر در Core"))
        else:
            self.stdout.write(self.style.ERROR("   • ❌ خطا در دریافت آمار Core"))
        
        # SyncLog breakdown
        synclog_stats = self._get_synclog_stats()
        
        self.stdout.write('')
        self.stdout.write('📝 وضعیت SyncLog:')
        for status, count in synclog_stats.items():
            emoji = {'synced': '📤', 'verified': '✅', 'failed': '❌', 'pending_retry': '🔄', 'pending': '⏳'}.get(status, '•')
            self.stdout.write(f"   {emoji} {status}: {count:,}")
        
        # آمار به تفکیک نوع محتوا
        self.stdout.write('')
        self.stdout.write('📦 آمار Chunk:')
        chunk_stats = local_stats['chunk_stats']
        self.stdout.write(f"   • Total: {chunk_stats['total']:,}")
        self.stdout.write(f"   • Synced: {chunk_stats['synced']:,}")
        self.stdout.write(f"   • Verified: {chunk_stats['verified']:,}")
        self.stdout.write(f"   • Failed: {chunk_stats['failed']:,}")
        
        self.stdout.write('')
        self.stdout.write('💬 آمار QAEntry:')
        qaentry_stats = local_stats['qaentry_stats']
        self.stdout.write(f"   • Total: {qaentry_stats['total']:,}")
        self.stdout.write(f"   • Synced: {qaentry_stats['synced']:,}")
        self.stdout.write(f"   • Verified: {qaentry_stats['verified']:,}")
        self.stdout.write(f"   • Failed: {qaentry_stats['failed']:,}")
        
        # CoreConfig stats
        config = CoreConfig.get_config()
        
        self.stdout.write('')
        self.stdout.write('⚙️  تنظیمات Core:')
        self.stdout.write(f"   • Auto Sync: {'فعال' if config.auto_sync_enabled else 'غیرفعال'}")
        self.stdout.write(f"   • Batch Size: {config.sync_batch_size}")
        self.stdout.write(f"   • Total Synced: {config.total_synced:,}")
        self.stdout.write(f"   • Total Errors: {config.total_errors}")
        if config.last_successful_sync:
            self.stdout.write(f"   • آخرین Sync: {config.last_successful_sync.strftime('%Y-%m-%d %H:%M:%S')}")
        
        self.stdout.write('')
        self.stdout.write('=' * 80)
        
        # Save to SyncStats
        if save_stats:
            SyncStats.objects.create(
                total_embeddings=local_stats['total_embeddings'],
                synced_count=local_stats['synced'],
                verified_count=local_stats['verified'],
                failed_count=local_stats['failed'],
                pending_count=local_stats['pending'],
                core_total_nodes=core_stats['total_nodes'],
                sync_percentage=local_stats['sync_percentage'],
                verification_percentage=local_stats['verification_percentage']
            )
            self.stdout.write(self.style.SUCCESS('✅ آمار در SyncStats ذخیره شد'))
    
    def _get_local_stats(self):
        total = Embedding.objects.count()
        synced = Embedding.objects.filter(synced_to_core=True).count()
        pending = Embedding.objects.filter(synced_to_core=False).count()
        
        # آمار SyncLog کلی
        verified = SyncLog.objects.filter(status='verified').count()
        failed = SyncLog.objects.filter(status='failed').count()
        
        # آمار به تفکیک نوع
        chunk_stats = self._get_content_type_stats('chunk')
        qaentry_stats = self._get_content_type_stats('qaentry')
        
        sync_percentage = (synced / total * 100) if total > 0 else 0
        verification_percentage = (verified / synced * 100) if synced > 0 else 0
        
        return {
            'total_embeddings': total,
            'synced': synced,
            'verified': verified,
            'failed': failed,
            'pending': pending,
            'sync_percentage': sync_percentage,
            'verification_percentage': verification_percentage,
            'chunk_stats': chunk_stats,
            'qaentry_stats': qaentry_stats,
        }
    
    def _get_content_type_stats(self, content_type):
        """آمار برای یک نوع محتوا"""
        total = SyncLog.objects.filter(content_type=content_type).count()
        synced = SyncLog.objects.filter(content_type=content_type, status='synced').count()
        verified = SyncLog.objects.filter(content_type=content_type, status='verified').count()
        failed = SyncLog.objects.filter(content_type=content_type, status='failed').count()
        
        return {
            'total': total,
            'synced': synced,
            'verified': verified,
            'failed': failed,
        }
    
    def _get_core_stats(self):
        try:
            response = requests.get('https://core.arpanet.ir/report', timeout=10)
            if response.status_code == 200:
                data = response.json()
                return {
                    'total_nodes': data.get('qdrant', {}).get('total_nodes')
                }
        except:
            pass
        
        return {'total_nodes': None}
    
    def _get_synclog_stats(self):
        stats = SyncLog.objects.values('status').annotate(count=Count('id'))
        return {item['status']: item['count'] for item in stats}
