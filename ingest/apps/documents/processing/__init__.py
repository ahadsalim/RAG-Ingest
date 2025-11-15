"""Document processing functionality for the Ingest system.

This package provides services for processing documents and legal units into chunks,
with support for batch processing, monitoring, and embedding generation.
"""

# Import core processing services
from .base import BaseProcessingService, ProcessingStats
from .chunking import ChunkProcessingService, get_chunk_processing_service
from .tasks import process_document_chunks, process_legal_unit_chunks, batch_process_units

# Signals are now in signals_complete.py and imported via apps.py

__all__ = [
    'BaseProcessingService',
    'ChunkProcessingService',
    'ProcessingStats',
    'get_chunk_processing_service',
    'process_document_chunks',
    'process_legal_unit_chunks',
    'batch_process_units',
]

# Set default logging configuration
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
