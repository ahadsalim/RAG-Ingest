"""
Management command for processing documents and legal units into chunks.

This command provides utilities for chunking documents and legal units,
with options for batch processing and custom chunking parameters.
"""
from __future__ import annotations

import importlib.util
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

# Add project root to Python path
PROJECT_ROOT = str(Path(__file__).parent.parent.parent.parent.parent.absolute())
sys.path.insert(0, PROJECT_ROOT)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def import_django() -> tuple[bool, dict[str, Any]]:
    """Attempt to import Django and set up the environment."""
    try:
        import django
        from django.conf import settings
        from django.core.management.base import BaseCommand, CommandError, CommandParser
        from django.core.exceptions import ObjectDoesNotExist, ValidationError
        from django.db import transaction
        from django.db.models import Q, Count, Model
        
        # Configure Django settings if not already configured
        if not settings.configured:
            os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ingest.settings')
            django.setup()
        
        # Import models after Django setup
        from ingest.apps.documents.models import Document, LegalUnit
        from ingest.apps.documents.processing import ChunkProcessingService, get_chunk_processing_service
        from ingest.apps.documents.processing.chunking import DEFAULT_CHUNK_SIZE, DEFAULT_CHUNK_OVERLAP
        
        return True, {
            'django': django,
            'settings': settings,
            'BaseCommand': BaseCommand,
            'CommandError': CommandError,
            'CommandParser': CommandParser,
            'ObjectDoesNotExist': ObjectDoesNotExist,
            'ValidationError': ValidationError,
            'transaction': transaction,
            'Q': Q,
            'Count': Count,
            'Model': Model,
            'Document': Document,
            'LegalUnit': LegalUnit,
            'ChunkProcessingService': ChunkProcessingService,
            'get_chunk_processing_service': get_chunk_processing_service,
            'DEFAULT_CHUNK_SIZE': DEFAULT_CHUNK_SIZE,
            'DEFAULT_CHUNK_OVERLAP': DEFAULT_CHUNK_OVERLAP,
        }
        
    except ImportError as e:
        logger.warning("Failed to import Django: %s", e)
        return False, {}

# Try to import Django and get all necessary components
_django_available, django = import_django()

if not _django_available:
    # Define minimal stubs for type checking when Django is not available
    class CommandError(Exception):
        pass
    
    class BaseCommand:
        def handle(self, *args, **options):
            logger.error("Django is not properly configured. Please install Django and required dependencies.")
            sys.exit(1)
    
    class CommandParser:
        def add_argument(self, *args, **kwargs):
            pass
    
    # Add stubs to the django dict for consistent access
django.update({
    'BaseCommand': BaseCommand,
    'CommandError': CommandError,
    'CommandParser': CommandParser,
    'ObjectDoesNotExist': Exception,
    'ValidationError': Exception,
})

# Extract commonly used Django components
BaseCommand = django['BaseCommand']
CommandError = django['CommandError']
ObjectDoesNotExist = django['ObjectDoesNotExist']
Document = django.get('Document')
LegalUnit = django.get('LegalUnit')
ChunkProcessingService = django.get('ChunkProcessingService')
DEFAULT_CHUNK_SIZE = django.get('DEFAULT_CHUNK_SIZE', 1000)
DEFAULT_CHUNK_OVERLAP = django.get('DEFAULT_CHUNK_OVERLAP', 200)

def get_chunk_processor(**kwargs):
    """Get a configured ChunkProcessingService instance."""
    if not _django_available:
        raise CommandError("Django is not properly configured. Cannot initialize ChunkProcessingService.")
    
    # Get the service class or factory function
    service_class = django.get('ChunkProcessingService')
    get_service = django.get('get_chunk_processing_service')
    
    if get_service and callable(get_service):
        return get_service()
    elif service_class and callable(service_class):
        return service_class(
            chunk_size=kwargs.get('chunk_size', DEFAULT_CHUNK_SIZE),
            chunk_overlap=kwargs.get('chunk_overlap', DEFAULT_CHUNK_OVERLAP)
        )
    else:
        raise CommandError("Could not initialize ChunkProcessingService. Check your Django setup.")

class Command(BaseCommand):
    help = 'Process documents and legal units to create chunks'

    def add_arguments(self, parser):
        """Define command line arguments."""
        parser.add_argument(
            '--document-id',
            type=str,
            help='Process a specific document by ID',
        )
        parser.add_argument(
            '--unit-id',
            type=str,
            help='Process a specific legal unit by ID',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Process all documents',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=10,
            help='Number of items to process in each batch (default: 10)',
        )
        parser.add_argument(
            '--chunk-size',
            type=int,
            default=None,
            help=f'Size of each chunk in tokens (default: {DEFAULT_CHUNK_SIZE})',
        )
        parser.add_argument(
            '--chunk-overlap',
            type=int,
            default=None,
            help=f'Number of tokens to overlap between chunks (default: {DEFAULT_CHUNK_OVERLAP})',
        )

    def handle(self, *args, **options):
        """Handle the command execution."""
        if not _django_available:
            self.stderr.write(
                self.style.ERROR('Django is not properly configured. Cannot continue.')
            )
            return 1

        try:
            # Initialize the processing service
            processor = get_chunk_processor(
                chunk_size=options['chunk_size'],
                chunk_overlap=options['chunk_overlap']
            )

            if options['document_id']:
                self.process_document(processor, options['document_id'])
            elif options['unit_id']:
                self.process_unit(processor, options['unit_id'])
            elif options['all']:
                self.process_all_documents(processor, options['batch_size'])
            else:
                self.stdout.write(
                    self.style.ERROR('Please specify --document-id, --unit-id, or --all')
                )
                return 1
                
            return 0
            
        except Exception as e:
            self.stderr.write(
                self.style.ERROR(f'Error during processing: {str(e)}')
            )
            if options.get('verbosity', 1) > 1:
                import traceback
                self.stderr.write(traceback.format_exc())
            return 1

    def process_document(self, processor: Any, document_id: str):
        """Process a specific document.
        
        Args:
            processor: An instance of ChunkProcessingService or compatible
            document_id: The ID of the document to process
            
        Raises:
            CommandError: If processing fails
        """
        try:
            document_id = UUID(str(document_id))
            self.stdout.write(f'Processing document: {document_id}')
            
            # Get the document to validate it exists
            try:
                document = Document.objects.get(id=document_id)
            except Document.DoesNotExist as e:
                raise CommandError(f'Document {document_id} not found') from e
                
            # Process the document
            result = processor.process_document(document_id)
            
            if result.get('success'):
                unit_results = result.get('unit_results', {})
                success_count = sum(1 for r in unit_results.values() if r.get('success'))
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Successfully processed document {document_id}:\n'
                        f'  - Units processed: {len(unit_results)}\n'
                        f'  - Units succeeded: {success_count}'
                    )
                )
                
                # Log unit results if in verbose mode
                if self.verbosity > 1:
                    for unit_id, unit_result in unit_results.items():
                        if unit_result.get('success'):
                            self.stdout.write(
                                f'  - Unit {unit_id}: {unit_result.get("chunks_created", 0)} chunks created'
                            )
                        else:
                            self.stdout.write(
                                self.style.WARNING(
                                    f'  - Unit {unit_id}: Failed - {unit_result.get("error", "Unknown error")}'
                                )
                            )
            else:
                error_msg = result.get('error', 'No error details provided')
                self.stdout.write(
                    self.style.ERROR(f'Failed to process document {document_id}: {error_msg}')
                )
                
        except (ValueError, ObjectDoesNotExist) as e:
            raise CommandError(f'Error processing document {document_id}: {str(e)}')

    def process_unit(self, processor: Any, unit_id: str):
        """Process a specific legal unit.
        
        Args:
            processor: An instance of ChunkProcessingService or compatible
            unit_id: The ID of the legal unit to process
            
        Raises:
            CommandError: If processing fails
        """
        try:
            unit_id = UUID(str(unit_id))
            self.stdout.write(f'Processing legal unit: {unit_id}')
            
            # Get the unit to validate it exists
            try:
                unit = LegalUnit.objects.get(id=unit_id)
            except LegalUnit.DoesNotExist as e:
                raise CommandError(f'Legal unit {unit_id} not found') from e
            
            # Process the unit
            result = processor.process_legal_unit(unit_id)
            
            if result.get('success'):
                chunks_created = result.get('chunks_created', 0)
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Successfully processed unit {unit_id}:\n'
                        f'  - Chunks created: {chunks_created}'
                    )
                )
                return chunks_created
            else:
                error_msg = result.get('error', 'No error details provided')
                self.stdout.write(
                    self.style.ERROR(f'Failed to process unit {unit_id}: {error_msg}')
                )
                return 0
                
        except (ValueError, ObjectDoesNotExist) as e:
            raise CommandError(f'Error processing unit {unit_id}: {str(e)}')

    def process_all_documents(self, processor: Any, batch_size: int = 10):
        """Process all documents in batches.
        
        Args:
            processor: An instance of ChunkProcessingService or compatible
            batch_size: Number of documents to process in each batch
            
        Returns:
            tuple: (total_processed, total_chunks_created)
        """
        # Get documents with their legal unit counts
        documents = Document.objects.annotate(
            unit_count=django['Count']('legal_units')
        ).order_by('-unit_count')
        
        total_documents = documents.count()
        
        if total_documents == 0:
            self.stdout.write(self.style.WARNING('No documents found to process'))
            return 0, 0

        self.stdout.write(f'Processing {total_documents} documents in batches of {batch_size}...')
        
        total_processed = 0
        total_chunks_created = 0
        
        for i in range(0, total_documents, batch_size):
            batch = documents[i:i + batch_size]
            current_batch_size = len(batch)
            
            self.stdout.write(f'\nProcessing batch {i//batch_size + 1}/{(total_documents + batch_size - 1)//batch_size} ({current_batch_size} documents)')
            
            for doc in batch:
                try:
                    if self.verbosity > 0:
                        self.stdout.write(f'  - Processing document: {doc.id} ({doc.unit_count} units)')
                    
                    result = processor.process_document(doc.id)
                    total_processed += 1
                    
                    if result.get('success'):
                        unit_results = result.get('unit_results', {})
                        chunks_created = sum(
                            r.get('chunks_created', 0) 
                            for r in unit_results.values()
                        )
                        total_chunks_created += chunks_created
                        
                        if self.verbosity > 0:
                            success_count = sum(1 for r in unit_results.values() if r.get('success'))
                            self.stdout.write(
                                f'    ✓ Created {chunks_created} chunks for {success_count}/{len(unit_results)} units'
                            )
                    else:
                        error_msg = result.get('error', 'No error details provided')
                        self.stdout.write(
                            self.style.ERROR(f'    ✗ Failed to process document {doc.id}: {error_msg}')
                        )
                        
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'Error processing document {doc.id}: {str(e)}')
                    )
                    if self.verbosity > 1:
                        import traceback
                        self.stdout.write(traceback.format_exc())
                    continue
        
        # Print summary
        self.stdout.write(self.style.SUCCESS(
            f'\nFinished processing {total_processed}/{total_documents} documents. '
            f'Created {total_chunks_created} chunks in total.'
        ))
        
        return total_processed, total_chunks_created
