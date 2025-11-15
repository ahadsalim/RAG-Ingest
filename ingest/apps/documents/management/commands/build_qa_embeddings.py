"""
Management command to build embeddings for approved QA entries.
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.contrib.contenttypes.models import ContentType
from ingest.apps.documents.models import QAEntry
from ingest.apps.embeddings.models import Embedding
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Build embeddings for approved QA entries'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force rebuild embeddings even if they already exist',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=10,
            help='Number of QA entries to process in each batch (default: 10)',
        )
        parser.add_argument(
            '--model-name',
            type=str,
            default='default',
            help='Embedding model name to use (default: "default")',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be processed without actually creating embeddings',
        )

    def handle(self, *args, **options):
        force = options['force']
        batch_size = options['batch_size']
        model_name = options['model_name']
        dry_run = options['dry_run']

        self.stdout.write(
            self.style.SUCCESS(f'Starting QA embeddings build with model: {model_name}')
        )

        # Get approved QA entries
        qa_entries = QAEntry.objects.filter(status='approved')
        
        if not force:
            # Exclude entries that already have embeddings
            qa_content_type = ContentType.objects.get_for_model(QAEntry)
            existing_embedding_ids = Embedding.objects.filter(
                content_type=qa_content_type,
                model_name=model_name
            ).values_list('object_id', flat=True)
            
            qa_entries = qa_entries.exclude(id__in=existing_embedding_ids)

        total_count = qa_entries.count()
        
        if total_count == 0:
            self.stdout.write(
                self.style.WARNING('No QA entries to process.')
            )
            return

        self.stdout.write(
            self.style.SUCCESS(f'Found {total_count} QA entries to process')
        )

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - No embeddings will be created'))
            for qa_entry in qa_entries[:10]:  # Show first 10
                self.stdout.write(f'Would process: {qa_entry.short_question}')
            if total_count > 10:
                self.stdout.write(f'... and {total_count - 10} more entries')
            return

        processed_count = 0
        error_count = 0

        # Process in batches
        for i in range(0, total_count, batch_size):
            batch = qa_entries[i:i + batch_size]
            
            self.stdout.write(
                f'Processing batch {i//batch_size + 1} '
                f'({i + 1}-{min(i + batch_size, total_count)} of {total_count})'
            )

            for qa_entry in batch:
                try:
                    self._create_embedding(qa_entry, model_name)
                    processed_count += 1
                    self.stdout.write('.', ending='')
                except Exception as e:
                    error_count += 1
                    logger.error(f'Error processing QA entry {qa_entry.id}: {e}')
                    self.stdout.write(
                        self.style.ERROR(f'Error processing {qa_entry.short_question}: {e}')
                    )

            self.stdout.write('')  # New line after batch

        # Summary
        self.stdout.write(
            self.style.SUCCESS(
                f'\nCompleted! Processed: {processed_count}, Errors: {error_count}'
            )
        )

    def _create_embedding(self, qa_entry, model_name):
        """Create embedding for a QA entry."""
        try:
            # Import embedding service (adjust import based on your embedding setup)
            from ingest.apps.embeddings.services import EmbeddingService
            
            # Get the embedding text
            text = qa_entry.embedding_text
            
            # Create embedding service instance
            embedding_service = EmbeddingService(model_name=model_name)
            
            # Generate embedding vector
            vector = embedding_service.embed_text(text)
            
            # Create embedding record
            with transaction.atomic():
                embedding = Embedding.objects.create(
                    content_object=qa_entry,
                    model_name=model_name,
                    vector=vector,
                    dimension=len(vector) if vector else 0
                )
                
                logger.info(f'Created embedding for QA entry {qa_entry.id}')
                return embedding
                
        except ImportError:
            # Fallback if embedding service is not available
            self.stdout.write(
                self.style.WARNING(
                    'EmbeddingService not available. Creating placeholder embedding.'
                )
            )
            
            # Create a placeholder embedding (for development/testing)
            with transaction.atomic():
                embedding = Embedding.objects.create(
                    content_object=qa_entry,
                    model_name=model_name,
                    vector=[0.0] * 384,  # Placeholder vector
                    dimension=384
                )
                
                logger.info(f'Created placeholder embedding for QA entry {qa_entry.id}')
                return embedding
        
        except Exception as e:
            logger.error(f'Failed to create embedding for QA entry {qa_entry.id}: {e}')
            raise CommandError(f'Failed to create embedding: {e}')

    def _get_embedding_backend(self, model_name):
        """Get the appropriate embedding backend based on configuration."""
        # This is a placeholder - implement based on your embedding architecture
        # You might have different backends like OpenAI, HuggingFace, etc.
        
        try:
            from django.conf import settings
            
            # Example configuration structure
            embedding_config = getattr(settings, 'EMBEDDING_BACKENDS', {})
            backend_config = embedding_config.get(model_name, {})
            
            backend_type = backend_config.get('type', 'default')
            
            if backend_type == 'openai':
                from ingest.apps.embeddings.backends.openai import OpenAIEmbeddingBackend
                return OpenAIEmbeddingBackend(config=backend_config)
            elif backend_type == 'huggingface':
                from ingest.apps.embeddings.backends.huggingface import HuggingFaceEmbeddingBackend
                return HuggingFaceEmbeddingBackend(config=backend_config)
            else:
                # Default/fallback backend
                from ingest.apps.embeddings.backends.default import DefaultEmbeddingBackend
                return DefaultEmbeddingBackend(config=backend_config)
                
        except (ImportError, AttributeError) as e:
            logger.warning(f'Could not load embedding backend: {e}')
            return None
