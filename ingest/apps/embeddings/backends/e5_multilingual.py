"""
E5 Multilingual embedding backend using intfloat/multilingual-e5-large model.
"""
import os
import logging
from typing import List, Optional
import torch

from .base import EmbeddingBackend, EmbeddingResult, EmbeddingModelError, EmbeddingConfigError

logger = logging.getLogger(__name__)


class E5Multilingual(EmbeddingBackend):
    """
    E5 Multilingual embedding backend using intfloat/multilingual-e5-large.
    
    This model supports multiple languages including Persian and provides
    high-quality embeddings for semantic search and RAG applications.
    """
    
    def __init__(self):
        self.model_name = os.getenv('EMBEDDING_E5_MODEL_NAME', 'intfloat/multilingual-e5-large')
        self.batch_size = int(os.getenv('EMBEDDING_BATCH_SIZE', '16'))
        self.device = os.getenv('EMBEDDING_DEVICE', 'cuda' if torch.cuda.is_available() else 'cpu')
        self.max_seq_length = int(os.getenv('EMBEDDING_MAX_SEQ_LENGTH', '512'))
        self.model_cache_dir = os.getenv('EMBEDDING_MODEL_CACHE_DIR', '/app/models')
        
        # Local model paths (support both manual and Hugging Face snapshot naming)
        default_dirname = self.model_name.split('/')[-1]
        snapshot_dirname = self.model_name.replace('/', '__')
        self.local_model_paths = [
            os.path.join(self.model_cache_dir, default_dirname),
            os.path.join(self.model_cache_dir, snapshot_dirname),
        ]
        
        # Lazy loading
        self._model = None
        self._tokenizer = None
        self._cached_dim = None
        
        logger.info(f"Initialized E5 Multilingual backend: {self.model_name}, device: {self.device}")
        logger.info(f"Local model path: {self.local_model_path}")
    
    def _load_model(self):
        """Lazy load the E5 multilingual model."""
        if self._model is not None:
            return
        
        try:
            from sentence_transformers import SentenceTransformer
            
            # Check if local model exists first
            model_path = None
            for candidate in self.local_model_paths:
                if os.path.isdir(candidate):
                    logger.info(f"Loading local E5 model from: {candidate}")
                    model_path = candidate
                    break
            
            if model_path is None:
                logger.info(f"Local model not found, downloading E5 model: {self.model_name}")
                # Create cache directory if it doesn't exist
                os.makedirs(self.model_cache_dir, exist_ok=True)
                model_path = self.model_name
                cache_folder = self.model_cache_dir
            else:
                cache_folder = None
            
            # Load model
            self._model = SentenceTransformer(
                model_path,
                device=self.device,
                cache_folder=cache_folder
            )
            
            # Set max sequence length
            if hasattr(self._model, 'max_seq_length'):
                self._model.max_seq_length = self.max_seq_length
            
            # Cache dimension
            self._cached_dim = self._model.get_sentence_embedding_dimension()
            logger.info(f"E5 model loaded successfully, dimension: {self._cached_dim}")
            
        except ImportError as e:
            raise EmbeddingConfigError(
                "sentence-transformers library not installed. "
                "Please install ML dependencies: pip install -r requirements/requirements-ml.txt"
            ) from e
        except Exception as e:
            logger.error(f"Failed to load E5 model: {e}")
            raise EmbeddingModelError(f"Model loading failed: {e}") from e
    
    def _prepare_text(self, text: str, task_type: str = "passage") -> str:
        """
        Prepare text for E5 model with task-specific instructions.
        
        E5 models use instruction prefixes for better performance:
        - "query: " for search queries
        - "passage: " for documents/passages
        """
        if not text:
            return ""
        
        # Normalize text using our text processing utility
        try:
            from ingest.core.text_processing import prepare_for_embedding
            normalized_text = prepare_for_embedding(text)
        except ImportError:
            # Fallback if text processing not available
            normalized_text = text.strip()
        
        # Add E5 instruction prefix
        if task_type == "query":
            return f"query: {normalized_text}"
        else:
            return f"passage: {normalized_text}"
    
    def embed(self, texts: List[str], task: Optional[str] = None, **kwargs) -> EmbeddingResult:
        """
        Generate embeddings for a list of texts.
        
        Args:
            texts: List of texts to embed
            task: Task type - "retrieval.query" or "retrieval.passage" or None
            **kwargs: Additional arguments
            
        Returns:
            EmbeddingResult with vectors and metadata
        """
        if not texts:
            return EmbeddingResult(vectors=[], dim=self.default_dim())
        
        # Load model if not already loaded
        self._load_model()
        
        try:
            # Determine task type for E5 instructions
            if task == "retrieval.query":
                task_type = "query"
            else:
                task_type = "passage"
            
            # Prepare texts with E5 instructions
            prepared_texts = [self._prepare_text(text, task_type) for text in texts]
            
            # Generate embeddings in batches
            all_embeddings = []
            for i in range(0, len(prepared_texts), self.batch_size):
                batch_texts = prepared_texts[i:i + self.batch_size]
                
                logger.debug(f"Processing batch {i//self.batch_size + 1}/{(len(prepared_texts)-1)//self.batch_size + 1}")
                
                # Generate embeddings for batch
                batch_embeddings = self._model.encode(
                    batch_texts,
                    convert_to_tensor=False,
                    normalize_embeddings=True,  # L2 normalize for cosine similarity
                    show_progress_bar=False
                )
                
                # Convert to list of lists
                if hasattr(batch_embeddings, 'tolist'):
                    batch_embeddings = batch_embeddings.tolist()
                
                all_embeddings.extend(batch_embeddings)
            
            logger.info(f"Generated {len(all_embeddings)} embeddings using E5 model")
            
            return EmbeddingResult(
                vectors=all_embeddings,
                dim=self._cached_dim,
                model_id=self.model_id()
            )
            
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            raise EmbeddingModelError(f"Failed to generate embeddings: {e}") from e
    
    def model_id(self) -> str:
        """Return model identifier."""
        # Return the full model name (e.g., intfloat/multilingual-e5-base)
        return self.model_name
    
    def model_version(self) -> Optional[str]:
        """Return model version if available."""
        return "1.0"  # E5 model version
    
    def default_dim(self) -> int:
        """Return default embedding dimension."""
        if self._cached_dim is not None:
            return self._cached_dim
        
        # Default dimension for multilingual-e5-large
        return 1024
    
    def supports_dual_encoder(self) -> bool:
        """E5 models support dual encoder with instruction prefixes."""
        return True
    
    def health_check(self) -> dict:
        """Check backend health and model availability."""
        try:
            # Try to load model
            self._load_model()
            
            # Test embedding generation
            test_result = self.embed(["test text"], task="retrieval.passage")
            
            return {
                "status": "healthy",
                "model_loaded": True,
                "model_name": self.model_name,
                "device": self.device,
                "dimension": self._cached_dim,
                "test_embedding_shape": len(test_result.vectors[0]) if test_result.vectors else 0
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "model_loaded": False
            }
    
    @property
    def model_path(self) -> str:
        """Return local model cache path."""
        return os.path.join(self.model_cache_dir, self.model_name.replace('/', '_'))
    
    @property
    def local_model_path(self) -> str:
        """Alias for model_path for compatibility."""
        return self.local_model_paths[0] if self.local_model_paths else self.model_path
