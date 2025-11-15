from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
import logging
from typing import Dict, List
from tqdm import tqdm

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Renormalize all text content in database with updated normalization rules'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--batch-size',
            type=int,
            default=1000,
            help='Batch size for processing (default: 1000)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be changed without making changes'
        )
        parser.add_argument(
            '--models',
            nargs='+',
            choices=['all', 'documents', 'legal_units', 'chunks', 'qa_pairs', 'embeddings'],
            default=['all'],
            help='Which models to process (default: all)'
        )
    
    def handle(self, *args, **options):
        batch_size = options['batch_size']
        dry_run = options['dry_run']
        models_to_process = options['models']
        
        self.stdout.write(
            self.style.SUCCESS(
                f'🔄 Starting database renormalization (dry_run={dry_run})'
            )
        )
        
        # Import text processing
        try:
            from ingest.core.text_processing import prepare_for_embedding
            self.normalizer = prepare_for_embedding
        except ImportError as e:
            self.stdout.write(
                self.style.ERROR(f'Failed to import text normalizer: {e}')
            )
            return
        
        # Track statistics
        stats = {
            'documents': {'total': 0, 'changed': 0},
            'legal_units': {'total': 0, 'changed': 0},
            'chunks': {'total': 0, 'changed': 0},
            'qa_pairs': {'total': 0, 'changed': 0},
            'embeddings': {'total': 0, 'changed': 0},
        }
        
        try:
            # Process each model type
            if 'all' in models_to_process or 'documents' in models_to_process:
                self._process_documents(stats, batch_size, dry_run)
            
            if 'all' in models_to_process or 'legal_units' in models_to_process:
                self._process_legal_units(stats, batch_size, dry_run)
            
            if 'all' in models_to_process or 'chunks' in models_to_process:
                self._process_chunks(stats, batch_size, dry_run)
            
            if 'all' in models_to_process or 'qa_pairs' in models_to_process:
                self._process_qa_pairs(stats, batch_size, dry_run)
            
            if 'all' in models_to_process or 'embeddings' in models_to_process:
                self._process_embeddings(stats, batch_size, dry_run)
            
            # Print summary
            self._print_summary(stats, dry_run)
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error during renormalization: {e}')
            )
            logger.error(f'Renormalization failed: {e}', exc_info=True)
    
    def _process_documents(self, stats: Dict, batch_size: int, dry_run: bool):
        """Process Document model."""
        try:
            from ingest.apps.documents.models import Document
            
            self.stdout.write('📄 Processing Documents...')
            
            # Process in batches
            total_count = Document.objects.count()
            stats['documents']['total'] = total_count
            
            with tqdm(total=total_count, desc="Documents") as pbar:
                for offset in range(0, total_count, batch_size):
                    batch = Document.objects.all()[offset:offset + batch_size]
                    
                    for doc in batch:
                        if doc.title:
                            new_title = self.normalizer(doc.title)
                            if new_title != doc.title:
                                stats['documents']['changed'] += 1
                                if not dry_run:
                                    doc.title = new_title
                                    doc.save(update_fields=['title'])
                        
                        pbar.update(1)
                    
                    if not dry_run:
                        self.stdout.write(f'  Processed {min(offset + batch_size, total_count)}/{total_count} documents')
        
        except ImportError:
            self.stdout.write(self.style.WARNING('Document model not found, skipping...'))
    
    def _process_legal_units(self, stats: Dict, batch_size: int, dry_run: bool):
        """Process LegalUnit model."""
        try:
            from ingest.apps.documents.models import LegalUnit
            
            self.stdout.write('📋 Processing Legal Units...')
            
            total_count = LegalUnit.objects.count()
            stats['legal_units']['total'] = total_count
            
            with tqdm(total=total_count, desc="Legal Units") as pbar:
                for offset in range(0, total_count, batch_size):
                    batch = LegalUnit.objects.all()[offset:offset + batch_size]
                    
                    for unit in batch:
                        if unit.content:
                            new_content = self.normalizer(unit.content)
                            if new_content != unit.content:
                                stats['legal_units']['changed'] += 1
                                if not dry_run:
                                    unit.content = new_content
                                    unit.save(update_fields=['content'])
                        
                        pbar.update(1)
                    
                    if not dry_run:
                        self.stdout.write(f'  Processed {min(offset + batch_size, total_count)}/{total_count} legal units')
        
        except ImportError:
            self.stdout.write(self.style.WARNING('LegalUnit model not found, skipping...'))
    
    def _process_chunks(self, stats: Dict, batch_size: int, dry_run: bool):
        """Process Chunk model."""
        try:
            from ingest.apps.documents.models import Chunk
            
            self.stdout.write('🔤 Processing Chunks...')
            
            total_count = Chunk.objects.count()
            stats['chunks']['total'] = total_count
            
            with tqdm(total=total_count, desc="Chunks") as pbar:
                for offset in range(0, total_count, batch_size):
                    batch = Chunk.objects.all()[offset:offset + batch_size]
                    
                    for chunk in batch:
                        if chunk.chunk_text:
                            new_text = self.normalizer(chunk.chunk_text)
                            if new_text != chunk.chunk_text:
                                stats['chunks']['changed'] += 1
                                if not dry_run:
                                    chunk.chunk_text = new_text
                                    try:
                                        chunk.save(update_fields=['chunk_text'])
                                    except Exception as e:
                                        # Handle concurrency issues by saving without update_fields
                                        logger.warning(f"Concurrency issue for chunk {chunk.id}, trying full save: {e}")
                                        chunk.save()
                        
                        pbar.update(1)
                    
                    if not dry_run:
                        self.stdout.write(f'  Processed {min(offset + batch_size, total_count)}/{total_count} chunks')
        
        except ImportError:
            self.stdout.write(self.style.WARNING('Chunk model not found, skipping...'))
    
    def _process_qa_pairs(self, stats: Dict, batch_size: int, dry_run: bool):
        """Process QAPair model."""
        try:
            from ingest.apps.documents.models import QAPair
            
            self.stdout.write('❓ Processing QA Pairs...')
            
            total_count = QAPair.objects.count()
            stats['qa_pairs']['total'] = total_count
            
            with tqdm(total=total_count, desc="QA Pairs") as pbar:
                for offset in range(0, total_count, batch_size):
                    batch = QAPair.objects.all()[offset:offset + batch_size]
                    
                    for qa in batch:
                        changed = False
                        
                        if qa.question:
                            new_question = self.normalizer(qa.question)
                            if new_question != qa.question:
                                qa.question = new_question
                                changed = True
                        
                        if qa.answer:
                            new_answer = self.normalizer(qa.answer)
                            if new_answer != qa.answer:
                                qa.answer = new_answer
                                changed = True
                        
                        if changed:
                            stats['qa_pairs']['changed'] += 1
                            if not dry_run:
                                qa.save(update_fields=['question', 'answer'])
                        
                        pbar.update(1)
                    
                    if not dry_run:
                        self.stdout.write(f'  Processed {min(offset + batch_size, total_count)}/{total_count} QA pairs')
        
        except ImportError:
            self.stdout.write(self.style.WARNING('QAPair model not found, skipping...'))
    
    def _process_embeddings(self, stats: Dict, batch_size: int, dry_run: bool):
        """Process Embedding model (text_content field)."""
        try:
            from ingest.apps.embeddings.models import Embedding
            
            self.stdout.write('🔢 Processing Embeddings...')
            
            total_count = Embedding.objects.count()
            stats['embeddings']['total'] = total_count
            
            with tqdm(total=total_count, desc="Embeddings") as pbar:
                for offset in range(0, total_count, batch_size):
                    batch = Embedding.objects.all()[offset:offset + batch_size]
                    
                    for embedding in batch:
                        if embedding.text_content:
                            new_content = self.normalizer(embedding.text_content)
                            if new_content != embedding.text_content:
                                stats['embeddings']['changed'] += 1
                                if not dry_run:
                                    embedding.text_content = new_content
                                    embedding.save(update_fields=['text_content'])
                        
                        pbar.update(1)
                    
                    if not dry_run:
                        self.stdout.write(f'  Processed {min(offset + batch_size, total_count)}/{total_count} embeddings')
        
        except ImportError:
            self.stdout.write(self.style.WARNING('Embedding model not found, skipping...'))
    
    def _print_summary(self, stats: Dict, dry_run: bool):
        """Print processing summary."""
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('📊 RENORMALIZATION SUMMARY'))
        self.stdout.write('='*60)
        
        total_processed = 0
        total_changed = 0
        
        for model_name, model_stats in stats.items():
            if model_stats['total'] > 0:
                self.stdout.write(
                    f"\n{model_name.title()}:"
                    f"\n  Total: {model_stats['total']:,}"
                    f"\n  Changed: {model_stats['changed']:,}"
                    f" ({model_stats['changed']/model_stats['total']*100:.1f}%)"
                )
                total_processed += model_stats['total']
                total_changed += model_stats['changed']
        
        self.stdout.write('\n' + '-'*40)
        self.stdout.write(
            f"TOTAL: {total_processed:,} records, {total_changed:,} changed "
            f"({total_changed/total_processed*100:.1f}%)" if total_processed > 0 else "No records found"
        )
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    '\n⚠️  DRY RUN MODE - No changes were made. '
                    'Run without --dry-run to apply changes.'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n✅ Successfully updated {total_changed:,} records!'
                )
            )
        
        self.stdout.write('='*60)
