"""
Management command برای process کردن بندهای بدون Chunk.
"""
from django.core.management.base import BaseCommand
from django.db.models import Count
from ingest.apps.documents.models import LegalUnit
from ingest.apps.documents.processing.tasks import process_legal_unit_chunks


class Command(BaseCommand):
    help = 'Process LegalUnit items without chunks'

    def add_arguments(self, parser):
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Number of units to process in one run (default: 100)',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Process all units without chunks',
        )

    def handle(self, *args, **options):
        batch_size = options['batch_size']
        process_all = options['all']
        
        # پیدا کردن بندهای بدون Chunk
        units_without_chunks = LegalUnit.objects.annotate(
            chunk_count=Count('chunks')
        ).filter(chunk_count=0).order_by('created_at')
        
        total = units_without_chunks.count()
        
        if total == 0:
            self.stdout.write(self.style.SUCCESS('✅ همه بندها Chunk دارند!'))
            return
        
        self.stdout.write(f"\n{'='*100}")
        self.stdout.write(f"بندهای بدون Chunk: {total}")
        self.stdout.write(f"{'='*100}\n")
        
        # تعیین تعداد برای process
        if process_all:
            to_process = total
            units_to_process = units_without_chunks
        else:
            to_process = min(batch_size, total)
            units_to_process = units_without_chunks[:batch_size]
        
        self.stdout.write(f"Processing {to_process} units...\n")
        
        # Queue کردن tasks
        processed = 0
        failed = 0
        
        for unit in units_to_process:
            try:
                process_legal_unit_chunks.delay(str(unit.id))
                processed += 1
                
                if processed % 10 == 0:
                    self.stdout.write(f"  Queued: {processed}/{to_process}")
            except Exception as e:
                failed += 1
                self.stdout.write(self.style.ERROR(f"  ✗ Error queuing {unit.id}: {e}"))
        
        self.stdout.write(f"\n{'='*100}")
        self.stdout.write(self.style.SUCCESS(f'✅ {processed} tasks queued'))
        if failed > 0:
            self.stdout.write(self.style.WARNING(f'⚠️  {failed} tasks failed'))
        self.stdout.write(f"⏳ Tasks will be processed by worker...")
        
        remaining = total - processed
        if remaining > 0:
            self.stdout.write(f"\n💡 {remaining} بند باقی مانده")
            self.stdout.write(f"   برای process کردن بقیه:")
            self.stdout.write(f"   python manage.py process_units_without_chunks")
            if process_all:
                self.stdout.write(f"   یا با --all برای همه")
        
        self.stdout.write(f"{'='*100}\n")
