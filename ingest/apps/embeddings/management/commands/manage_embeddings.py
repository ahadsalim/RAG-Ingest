"""
Management command for managing embeddings.

Features:
- Interactive menu for managing embeddings
- List items needing embeddings
- Manually generate embeddings
- Delete all embeddings
- Show embedding status
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction, models
from django.contrib.contenttypes.models import ContentType
from typing import List, Dict, Any, Optional
import sys

from ...models import Embedding
from ...tasks import batch_generate_embeddings_for_queryset
from ingest.apps.documents.models import Chunk, QAEntry


class Command(BaseCommand):
    help = 'Manage embeddings for search functionality'

    def add_arguments(self, parser):
        parser.add_argument(
            '--delete-all',
            action='store_true',
            help='Delete all embeddings'
        )
        parser.add_argument(
            '--generate',
            action='store_true',
            help='Generate missing embeddings (non-interactive)'
        )
        parser.add_argument(
            '--model',
            type=str,
            default='intfloat/multilingual-e5-base',
            help='Model name to use for embeddings (default: intfloat/multilingual-e5-base)'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=50,
            help='Batch size for processing (default: 50)'
        )
        parser.add_argument(
            '--interactive',
            action='store_true',
            help='Start interactive embedding management menu'
        )

    def handle(self, *args, **options):
        if options['interactive']:
            self.interactive_menu()
            return
            
        if options['delete_all']:
            self.delete_all_embeddings()
            return
            
        if options['generate']:
            self.generate_embeddings(
                model_name=options['model'],
                batch_size=options['batch_size'],
                interactive=False
            )
            return
        
        # Default action: show status
        self.show_status()
    
    def delete_all_embeddings(self):
        """Delete all embeddings from the database."""
        self.stdout.write('Deleting all embeddings...')
        count, _ = Embedding.objects.all().delete()
        self.stdout.write(
            self.style.SUCCESS(f'Successfully deleted {count} embeddings')
        )
        return count

    def list_items_needing_embeddings(self, model_name: str = 'intfloat/multilingual-e5-base'):
        """List items that need embeddings without generating them."""
        self.stdout.write('\n' + '='*50)
        self.stdout.write(self.style.SUCCESS('Items Needing Embeddings'))
        self.stdout.write('='*50)
        
        # List chunks needing embeddings
        chunk_ct = ContentType.objects.get_for_model(Chunk)
        chunks_count = Chunk.objects.exclude(
            id__in=Embedding.objects.filter(
                content_type=chunk_ct,
                model_id=model_name
            ).values_list('object_id', flat=True)
        ).count()
        
        # List QA entries needing embeddings
        qa_ct = ContentType.objects.get_for_model(QAEntry)
        qa_count = QAEntry.objects.filter(
            status='approved'
        ).exclude(
            id__in=Embedding.objects.filter(
                content_type=qa_ct,
                model_id=model_name
            ).values_list('object_id', flat=True)
        ).count()
        
        self.stdout.write(f'\n{self.style.SUCCESS("Items needing embeddings:")}')
        self.stdout.write(f'- {chunks_count} chunks')
        self.stdout.write(f'- {qa_count} QA entries')
        
        return chunks_count + qa_count > 0
    
    def generate_embeddings(self, model_name: str, batch_size: int, interactive: bool = True):
        """
        Generate missing embeddings with optional user confirmation.
        
        Args:
            model_name: Name of the model to use for embeddings
            batch_size: Number of items to process in each batch
            interactive: If True, will ask for confirmation before proceeding
        """
        # First show what needs to be processed
        has_items = self.list_items_needing_embeddings(model_name)
        
        if not has_items:
            self.stdout.write(self.style.SUCCESS('\nAll items already have embeddings!'))
            return False
        
        if interactive:
            confirm = input('\nDo you want to generate embeddings for these items? (y/n): ').strip().lower()
            if confirm != 'y':
                self.stdout.write(self.style.WARNING('Embedding generation cancelled.'))
                return False
        
        self.stdout.write('\nStarting embedding generation...')
        
        # Process Chunks
        chunk_ct = ContentType.objects.get_for_model(Chunk)
        chunks_to_process = Chunk.objects.exclude(
            id__in=Embedding.objects.filter(
                content_type=chunk_ct,
                model_id=model_name
            ).values_list('object_id', flat=True)
        )
        
        if chunks_to_process.exists():
            self.stdout.write('\nProcessing chunks...')
            chunk_ids = list(chunks_to_process.values_list('id', flat=True))
            async_result = batch_generate_embeddings_for_queryset.delay(
                [str(i) for i in chunk_ids],
                'Chunk',
                model_name,
                batch_size,
            )
            self.stdout.write(self.style.SUCCESS(f"Enqueued chunks embedding task: {async_result.id} ({len(chunk_ids)} items)"))
        
        # Process QA Entries (only approved ones)
        qa_ct = ContentType.objects.get_for_model(QAEntry)
        qa_to_process = QAEntry.objects.filter(
            status='approved'
        ).exclude(
            id__in=Embedding.objects.filter(
                content_type=qa_ct,
                model_id=model_name
            ).values_list('object_id', flat=True)
        )
        
        if qa_to_process.exists():
            self.stdout.write('\nProcessing QA entries...')
            qa_ids = list(qa_to_process.values_list('id', flat=True))
            async_result = batch_generate_embeddings_for_queryset.delay(
                [str(i) for i in qa_ids],
                'QAEntry',
                model_name,
                batch_size,
            )
            self.stdout.write(self.style.SUCCESS(f"Enqueued QA entries embedding task: {async_result.id} ({len(qa_ids)} items)"))
        
        return True
    
    def _print_results(self, label: str, results: Dict[str, Any]):
        """Print formatted results."""
        if results.get('success', False):
            self.stdout.write(self.style.SUCCESS(
                f"{label} - Processed: {results['processed']}, "
                f"Created: {results['created']}, "
                f"Updated: {results['updated']}, "
                f"Errors: {results['errors']}"
            ))
        else:
            self.stdout.write(self.style.ERROR(
                f"{label} - Error: {results.get('error', 'Unknown error')}"
            ))
    
    def show_status(self):
        """Show current embedding status."""
        self.stdout.write(self.style.MIGRATE_HEADING('Embedding Status'))
        self.stdout.write('=' * 50)
        
        # Chunks status
        chunk_ct = ContentType.objects.get_for_model(Chunk)
        total_chunks = Chunk.objects.count()
        chunks_with_embeddings = Embedding.objects.filter(
            content_type=chunk_ct
        ).values('model_id').annotate(count=models.Count('id'))
        
        self.stdout.write(f'\n{self.style.SUCCESS("Chunks:")} {total_chunks} total')
        for stat in chunks_with_embeddings:
            self.stdout.write(f"  - {stat['model_id']}: {stat['count']} embeddings")
        
        # QA Entries status
        qa_ct = ContentType.objects.get_for_model(QAEntry)
        total_qa = QAEntry.objects.filter(status='approved').count()
        qa_with_embeddings = Embedding.objects.filter(
            content_type=qa_ct
        ).values('model_id').annotate(count=models.Count('id'))
        
        self.stdout.write(f'\n{self.style.SUCCESS("QA Entries:")} {total_qa} approved')
        for stat in qa_with_embeddings:
            self.stdout.write(f"  - {stat['model_id']}: {stat['count']} embeddings")
    
    def interactive_menu(self):
        """Display an interactive menu for managing embeddings."""
        while True:
            self.stdout.write('\n' + '='*50)
            self.stdout.write(self.style.SUCCESS('Embedding Management'))
            self.stdout.write('='*50)
            
            # Show current status
            self.show_status()
            
            # Show menu options
            self.stdout.write('\nOptions:')
            self.stdout.write('1. Show embedding status')
            self.stdout.write('2. List items needing embeddings')
            self.stdout.write('3. Generate missing embeddings')
            self.stdout.write(self.style.WARNING('4. Delete all embeddings'))
            self.stdout.write(self.style.ERROR('0. Exit'))
            
            choice = input('\nEnter your choice (0-4): ').strip()
            
            if choice == '0':
                self.stdout.write(self.style.SUCCESS('Exiting...'))
                break
                
            elif choice == '1':
                # Status is already shown at the top of the menu
                continue
                
            elif choice == '2':
                # Just list items needing embeddings
                self.list_items_needing_embeddings()
                
            elif choice == '3':
                # Generate embeddings with confirmation
                self.generate_embeddings(
                    model_name='intfloat/multilingual-e5-base',
                    batch_size=50,
                    interactive=True
                )
                
            elif choice == '4':
                # Delete all embeddings with confirmation
                confirm = input('\nWARNING: This will delete ALL embeddings. Are you sure? (y/n): ').strip().lower()
                if confirm == 'y':
                    self.delete_all_embeddings()
                else:
                    self.stdout.write(self.style.WARNING('Operation cancelled.'))
            else:
                self.stdout.write(self.style.ERROR('Invalid choice. Please try again.'))
    
    def generate_embeddings_for_model(self, model_class, model_name: str, batch_size: int, **filters):
        """Generate embeddings for a specific model class."""
        ct = ContentType.objects.get_for_model(model_class)
        queryset = model_class.objects.filter(**filters).exclude(
            id__in=Embedding.objects.filter(
                content_type=ct,
                model_id=model_name
            ).values_list('object_id', flat=True)
        )
        
        if queryset.exists():
            ids = list(queryset.values_list('id', flat=True))
            async_result = batch_generate_embeddings_for_queryset.delay(
                [str(i) for i in ids],
                model_class.__name__,
                model_name,
                batch_size,
            )
            self.stdout.write(self.style.SUCCESS(f"Enqueued {model_class.__name__} embedding task: {async_result.id} ({len(ids)} items)"))
        else:
            self.stdout.write(self.style.SUCCESS(f"No {model_class.__name__} need embeddings."))
