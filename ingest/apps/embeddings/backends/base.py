"""Base classes for embedding backends."""

import numpy as np
from abc import ABC, abstractmethod
from typing import Iterable, List, Dict, Optional, Union
import logging

logger = logging.getLogger(__name__)


class EmbeddingResult(Dict):
    """
    Result from embedding operation containing:
    - vectors: List[List[float]] - L2-normalized embedding vectors
    - model_id: str - Identifier of the model used
    - dim: int - Dimension of the vectors
    - usage: Optional[dict] - Usage statistics (tokens, API calls, etc.)
    """
    
    def __init__(self, vectors: List[List[float]], model_id: str, dim: int, usage: Optional[dict] = None):
        super().__init__()
        self['vectors'] = vectors
        self['model_id'] = model_id
        self['dim'] = dim
        self['usage'] = usage or {}
    
    @property
    def vectors(self) -> List[List[float]]:
        return self['vectors']
    
    @property
    def model_id(self) -> str:
        return self['model_id']
    
    @property
    def dim(self) -> int:
        return self['dim']
    
    @property
    def usage(self) -> dict:
        return self['usage']


class EmbeddingBackend(ABC):
    """Abstract base class for embedding backends."""
    
    @abstractmethod
    def embed(self, texts: Iterable[str], *, task: Optional[str] = None) -> EmbeddingResult:
        """
        Generate embeddings for the given texts.
        
        Args:
            texts: Iterable of text strings to embed
            task: Optional task hint for dual-encoder models
                 - "retrieval.query" for search queries
                 - "retrieval.passage" for document chunks
                 - None for general purpose
        
        Returns:
            EmbeddingResult with L2-normalized vectors
        """
        pass
    
    @abstractmethod
    def model_id(self) -> str:
        """Return the model identifier for this backend."""
        pass
    
    @abstractmethod
    def default_dim(self) -> Optional[int]:
        """
        Return the default dimension for this model, if known.
        Returns None if dimension must be detected from first embedding.
        """
        pass
    
    @abstractmethod
    def supports_dual_encoder(self) -> bool:
        """Return True if this backend supports different encodings for queries vs passages."""
        pass
    
    def normalize_vectors(self, vectors: List[List[float]]) -> List[List[float]]:
        """L2-normalize vectors to unit length."""
        normalized = []
        for vector in vectors:
            vec_array = np.array(vector, dtype=np.float32)
            norm = np.linalg.norm(vec_array)
            if norm > 0:
                normalized_vec = (vec_array / norm).tolist()
            else:
                # Handle zero vectors
                normalized_vec = vec_array.tolist()
                logger.warning("Encountered zero vector during normalization")
            normalized.append(normalized_vec)
        return normalized
    
    def validate_texts(self, texts: Iterable[str]) -> List[str]:
        """Validate and prepare texts for embedding."""
        text_list = list(texts)
        if not text_list:
            raise ValueError("No texts provided for embedding")
        
        # Filter out empty texts
        valid_texts = [text.strip() for text in text_list if text and text.strip()]
        if not valid_texts:
            raise ValueError("All provided texts are empty")
        
        return valid_texts
    
    def batch_texts(self, texts: List[str], batch_size: int) -> List[List[str]]:
        """Split texts into batches for processing."""
        if batch_size <= 0:
            return [texts]
        
        batches = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batches.append(batch)
        return batches


class EmbeddingError(Exception):
    """Base exception for embedding operations."""
    pass


class EmbeddingConfigError(EmbeddingError):
    """Configuration error in embedding backend."""
    pass


class EmbeddingAPIError(EmbeddingError):
    """API error from external embedding service."""
    pass


class EmbeddingModelError(EmbeddingError):
    """Model loading or inference error."""
    pass
