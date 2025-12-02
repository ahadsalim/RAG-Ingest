"""
Services for text chunking and embedding operations.

DEPRECATED: این فایل منسوخ شده است.
- برای Chunking از ingest.apps.documents.processing.chunking استفاده کنید
- برای Embedding از ingest.apps.embeddings.embedding_service استفاده کنید

این فایل فقط برای backward compatibility نگه داشته شده است.
"""
import warnings

warnings.warn(
    "ingest.apps.documents.services is deprecated. "
    "Use ingest.apps.documents.processing.chunking or "
    "ingest.apps.embeddings.embedding_service instead.",
    DeprecationWarning,
    stacklevel=2
)

import logging
logger = logging.getLogger(__name__)

# Re-export from new locations for backward compatibility
from .processing.chunking import ChunkProcessingService, get_chunk_processing_service

# Re-export EmbeddingService from embeddings app
try:
    from ingest.apps.embeddings.embedding_service import EmbeddingService, get_embedding_service
except ImportError:
    # If embeddings not available, provide stub
    class EmbeddingService:
        """Stub for backward compatibility."""
        def __init__(self):
            logger.warning("EmbeddingService imported from deprecated location")
    
    def get_embedding_service():
        return EmbeddingService()


# Legacy class names - deprecated aliases
TextChunkingService = ChunkProcessingService  # Deprecated alias


# Old function - deprecated
def get_text_chunking_service():
    """DEPRECATED: Use get_chunk_processing_service instead."""
    warnings.warn(
        "get_text_chunking_service is deprecated. "
        "Use get_chunk_processing_service from processing.chunking instead.",
        DeprecationWarning,
        stacklevel=2
    )
    return get_chunk_processing_service()


# کد قدیمی حذف شده است.
# برای پیاده‌سازی جدید به processing/chunking.py مراجعه کنید.
