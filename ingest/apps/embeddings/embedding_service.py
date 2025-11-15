"""
Embedding service for Persian legal RAG with pluggable backends.

Provides high-level interface for:
- Generating embeddings with dual-encoder support
- Semantic search with model versioning
- Batch processing and caching
- Blue/green deployment support
"""

import logging
from typing import List, Optional, Dict, Any, Union
from django.conf import settings
from django.db.models import QuerySet
from django.core.cache import cache

from .models import Embedding
from .backends.factory import get_backend
from .backends.base import EmbeddingResult, EmbeddingError

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    High-level service for embedding operations with pluggable backends.
    
    Handles:
    - Dual encoder logic (query vs passage)
    - Model versioning and blue/green deployment
    - Caching and batch processing
    - Error handling and fallbacks
    """
    
    def __init__(self, provider: Optional[str] = None, model_id: Optional[str] = None):
        """
        Initialize embedding service.
        
        Args:
            provider: Override default provider from settings
            model_id: Override default model_id from settings
        """
        self.provider = provider or settings.EMBEDDING_PROVIDER
        self.backend = get_backend(self.provider)
        self.model_id = model_id or self._get_effective_model_id()
        self.read_model_id = settings.EMBEDDINGS_READ_MODEL_ID or self.model_id
        
        logger.info(f"Initialized EmbeddingService: provider={self.provider}, model_id={self.model_id}")
    
    def _get_effective_model_id(self) -> str:
        """Get the effective model ID from settings or backend."""
        if settings.EMBEDDING_MODEL_ID:
            return settings.EMBEDDING_MODEL_ID
        return self.backend.model_id()
    
    def embed_query(self, query: str, **kwargs) -> List[float]:
        """
        Embed a search query with dual-encoder support.
        
        Args:
            query: Search query text
            **kwargs: Additional arguments for embedding
            
        Returns:
            Normalized embedding vector
        """
        try:
            # Use query-specific task if backend supports dual encoder
            task = "retrieval.query" if self.backend.supports_dual_encoder() else None
            
            result = self.backend.embed([query], task=task, **kwargs)
            
            if not result.vectors:
                raise EmbeddingError("No vectors returned for query")
            
            return result.vectors[0]
            
        except Exception as e:
            logger.error(f"Failed to embed query: {e}")
            raise EmbeddingError(f"Query embedding failed: {e}")
    
    def embed_passages(self, texts: List[str], **kwargs) -> EmbeddingResult:
        """
        Embed document passages/chunks with dual-encoder support.
        
        Args:
            texts: List of text passages to embed
            **kwargs: Additional arguments for embedding
            
        Returns:
            EmbeddingResult with normalized vectors
        """
        try:
            # Use passage-specific task if backend supports dual encoder
            task = "retrieval.passage" if self.backend.supports_dual_encoder() else None
            
            result = self.backend.embed(texts, task=task, **kwargs)
            
            if len(result.vectors) != len(texts):
                raise EmbeddingError(f"Vector count mismatch: {len(texts)} texts, {len(result.vectors)} vectors")
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to embed passages: {e}")
            raise EmbeddingError(f"Passage embedding failed: {e}")
    
    def semantic_search(
        self,
        query: Union[str, List[float]],
        limit: int = 10,
        similarity_threshold: Optional[float] = None,
        model_id: Optional[str] = None,
        **filters
    ) -> QuerySet:
        """
        Perform semantic search using embeddings.
        
        Args:
            query: Query string or pre-computed query vector
            limit: Maximum number of results
            similarity_threshold: Minimum similarity score (0-1)
            model_id: Override model to search (for blue/green deployment)
            **filters: Additional filters for the search
            
        Returns:
            QuerySet of Embedding objects with similarity scores
        """
        try:
            # Get query vector
            if isinstance(query, str):
                query_vector = self.embed_query(query)
            else:
                query_vector = query
            
            # Determine which model to search
            search_model_id = model_id or self.read_model_id
            
            # Get dimension from first embedding of this model
            sample_embedding = Embedding.objects.filter(model_id=search_model_id).first()
            if not sample_embedding:
                logger.warning(f"No embeddings found for model {search_model_id}")
                return Embedding.objects.none()
            
            dimension = sample_embedding.dim
            
            # Perform search using the updated manager method
            return Embedding.objects.cosine_search_v2(
                query_vector=query_vector,
                model_id=search_model_id,
                dimension=dimension,
                limit=limit,
                similarity_threshold=similarity_threshold,
                **filters
            )
            
        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            raise EmbeddingError(f"Search failed: {e}")
    
    def create_embeddings(
        self,
        objects: List[Any],
        texts: List[str],
        batch_size: int = 100,
        **kwargs
    ) -> List[Embedding]:
        """
        Create embeddings for multiple objects in batches.
        
        Args:
            objects: List of Django model instances
            texts: List of text contents
            batch_size: Batch size for processing
            **kwargs: Additional arguments
            
        Returns:
            List of created Embedding instances
        """
        if len(objects) != len(texts):
            raise ValueError("objects and texts must have the same length")
        
        all_embeddings = []
        
        # Process in batches
        for i in range(0, len(objects), batch_size):
            batch_objects = objects[i:i + batch_size]
            batch_texts = texts[i:i + batch_size]
            
            # Generate embeddings for batch
            result = self.embed_passages(batch_texts)
            
            # Create Embedding instances
            embeddings_to_create = []
            for obj, text, vector in zip(batch_objects, batch_texts, result.vectors):
                embeddings_to_create.append(
                    Embedding(
                        content_object=obj,
                        text_content=text[:1000],  # Truncate for storage
                        vector=vector,
                        model_id=self.model_id,
                        model_version=getattr(self.backend, 'model_version', None),
                        dim=result.dim,
                        model_name=self.backend.__class__.__name__  # Legacy field
                    )
                )
            
            # Bulk create
            created = Embedding.objects.bulk_create(
                embeddings_to_create,
                batch_size=len(embeddings_to_create),
                ignore_conflicts=True
            )
            
            all_embeddings.extend(created)
            logger.info(f"Created {len(created)} embeddings in batch")
        
        return all_embeddings
    
    def get_or_create_embedding(
        self,
        content_object: Any,
        text_content: str,
        force_recreate: bool = False
    ) -> Embedding:
        """
        Get existing embedding or create new one for a content object.
        
        Args:
            content_object: Django model instance
            text_content: Text content to embed
            force_recreate: Force recreation even if embedding exists
            
        Returns:
            Embedding instance
        """
        from django.contrib.contenttypes.models import ContentType
        
        content_type = ContentType.objects.get_for_model(content_object)
        
        # Check for existing embedding
        if not force_recreate:
            existing = Embedding.objects.filter(
                content_type=content_type,
                object_id=content_object.pk,
                model_id=self.model_id
            ).first()
            
            if existing:
                return existing
        
        # Create new embedding
        result = self.embed_passages([text_content])
        
        embedding = Embedding.objects.create(
            content_object=content_object,
            text_content=text_content[:1000],
            vector=result.vectors[0],
            model_id=self.model_id,
            model_version=getattr(self.backend, 'model_version', None),
            dim=result.dim,
            model_name=self.backend.__class__.__name__
        )
        
        return embedding
    
    def get_model_stats(self) -> Dict[str, Any]:
        """Get statistics about embeddings for this model."""
        stats = {
            'model_id': self.model_id,
            'provider': self.provider,
            'backend_class': self.backend.__class__.__name__,
            'supports_dual_encoder': self.backend.supports_dual_encoder(),
            'default_dim': self.backend.default_dim(),
        }
        
        # Database stats
        embeddings = Embedding.objects.filter(model_id=self.model_id)
        stats.update({
            'total_embeddings': embeddings.count(),
            'dimensions': list(embeddings.values_list('dim', flat=True).distinct()),
        })
        
        return stats


# Global service instance
_default_service = None


def get_embedding_service(provider: Optional[str] = None, model_id: Optional[str] = None) -> EmbeddingService:
    """
    Get embedding service instance.
    
    Args:
        provider: Override provider
        model_id: Override model_id
        
    Returns:
        EmbeddingService instance
    """
    global _default_service
    
    # Return cached default service if no overrides
    if provider is None and model_id is None:
        if _default_service is None:
            _default_service = EmbeddingService()
        return _default_service
    
    # Create new service with overrides
    return EmbeddingService(provider=provider, model_id=model_id)


# Convenience functions
def embed_query(query: str, **kwargs) -> List[float]:
    """Embed a search query."""
    return get_embedding_service().embed_query(query, **kwargs)


def embed_passages(texts: List[str], **kwargs) -> EmbeddingResult:
    """Embed document passages."""
    return get_embedding_service().embed_passages(texts, **kwargs)


def semantic_search(query: Union[str, List[float]], **kwargs) -> QuerySet:
    """Perform semantic search."""
    return get_embedding_service().semantic_search(query, **kwargs)
