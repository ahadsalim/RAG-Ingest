import uuid
from typing import List, Optional, Tuple, Any, Dict
from django.db import models, connection
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.conf import settings
from django.db.models import QuerySet, F, FloatField, ExpressionWrapper
from django.db.models.functions import Power, Sqrt
from pgvector.django import VectorField, L2Distance, CosineDistance
from simple_history.models import HistoricalRecords
import numpy as np

from ingest.apps.masterdata.models import BaseModel

# Import SyncLog models
from .models_synclog import SyncLog, SyncStats


class EmbeddingManager(models.Manager):
    """Custom manager for Embedding model with vector search methods."""
    
    def cosine_search_v2(
        self,
        query_vector: List[float],
        model_id: str,
        dimension: int,
        limit: int = 10,
        similarity_threshold: Optional[float] = None,
        **filters
    ) -> QuerySet:
        """
        Perform cosine similarity search with versioned model support.
        
        Args:
            query_vector: The query embedding vector
            model_id: Filter by embedding model ID (e.g., 'hakim-v1', 'sbert-MatinaSRoberta')
            dimension: Filter by vector dimension
            limit: Maximum number of results to return
            similarity_threshold: Minimum similarity score (0-1)
            **filters: Additional filter conditions
            
        Returns:
            QuerySet of matching Embedding objects with similarity score
        """
        query_vector = np.array(query_vector, dtype=np.float32)
        query_norm = np.linalg.norm(query_vector)
        
        if query_norm == 0:
            raise ValueError("Query vector cannot be a zero vector")
            
        # Normalize the query vector
        query_vector = (query_vector / query_norm).tolist()
        
        # Base queryset with filters
        qs = self.get_queryset().filter(
            model_id=model_id,
            dim=dimension,
            **filters
        )
        
        # Calculate cosine similarity using vector operations
        qs = qs.annotate(
            similarity=1 - CosineDistance('vector', query_vector)
        )
        
        if similarity_threshold is not None:
            qs = qs.filter(similarity__gte=similarity_threshold)
            
        return qs.order_by('-similarity')[:limit]

    def cosine_search(
        self,
        query_vector: List[float],
        model_name: str = 'distiluse-base-multilingual-cased-v2',
        dimension: int = 512,
        limit: int = 10,
        similarity_threshold: Optional[float] = None,
        **filters
    ) -> QuerySet:
        """
        Perform cosine similarity search with proper L2 normalization.
        
        Args:
            query_vector: The query embedding vector
            model_name: Filter by embedding model name
            dimension: Filter by vector dimension
            limit: Maximum number of results to return
            similarity_threshold: Minimum similarity score (0-1)
            **filters: Additional filter conditions
            
        Returns:
            QuerySet of matching Embedding objects with similarity score
        """
        query_vector = np.array(query_vector, dtype=np.float32)
        query_norm = np.linalg.norm(query_vector)
        
        if query_norm == 0:
            raise ValueError("Query vector cannot be a zero vector")
            
        # Normalize the query vector
        query_vector = (query_vector / query_norm).tolist()
        
        # Base queryset with filters
        qs = self.get_queryset().filter(
            model_name=model_name,
            dim=dimension,
            **filters
        )
        
        # Calculate cosine similarity using vector operations
        # cosine_sim = (A.B) / (|A|*|B|)
        # Since we normalized the query vector, this simplifies to:
        # cosine_sim = (A/|A|).(B/|B|) = (A.B) / (|A|*|B|)
        # Where |A| = 1 (normalized query vector)
        qs = qs.annotate(
            similarity=1 - CosineDistance('vector', query_vector)
        )
        
        if similarity_threshold is not None:
            qs = qs.filter(similarity__gte=similarity_threshold)
            
        return qs.order_by('-similarity')[:limit]
    
    def create_embedding(
        self,
        content_object: models.Model,
        text_content: str,
        vector: List[float],
        model_name: str = 'distiluse-base-multilingual-cased-v2',
        **kwargs
    ) -> 'Embedding':
        """
        Create a new embedding with proper validation.
        
        Args:
            content_object: The object this embedding represents
            text_content: The original text content
            vector: The embedding vector
            model_name: Name of the embedding model used
            **kwargs: Additional fields for the Embedding model
            
        Returns:
            The created Embedding instance
        """
        vector = np.array(vector, dtype=np.float32)
        dimension = len(vector)
        
        return self.create(
            content_object=content_object,
            text_content=text_content,
            vector=vector.tolist(),
            model_name=model_name,
            dim=dimension,
            **kwargs
        )


class Embedding(BaseModel):
    """
    Store vector embeddings for content with pgvector.
    
    Optimized for semantic search with pgvector's IVFFLAT and HNSW indexes.
    Uses cosine similarity for semantic search queries.
    """
    
    # Generic foreign key to any model
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.UUIDField()
    content_object = GenericForeignKey('content_type', 'object_id')
    
    # Embedding data
    model_name = models.CharField(
        max_length=100, 
        verbose_name='نام مدل',
        default='distiluse-base-multilingual-cased-v2',
        help_text='Legacy model name field'
    )
    
    # New versioned embedding fields
    model_id = models.CharField(
        max_length=200,
        verbose_name='شناسه مدل',
        help_text='Unique identifier for the embedding model (e.g., hakim-v1, sbert-MatinaSRoberta)',
        db_index=True,
    )
    
    model_version = models.CharField(
        max_length=50,
        verbose_name='نسخه مدل',
        help_text='Version string for the embedding model',
        null=True,
        blank=True,
    )
    
    vector = VectorField(
        dimensions=getattr(settings, 'EMBEDDING_DIMENSION', 512), 
        verbose_name='بردار'
    )
    
    dimension = models.PositiveIntegerField(
        default=getattr(settings, 'EMBEDDING_DIMENSION', 512), 
        verbose_name='بعد بردار (legacy)'
    )
    
    dim = models.PositiveIntegerField(
        verbose_name='بعد بردار',
        help_text='Dimension of the embedding vector',
        db_index=True,
    )
    
    # Metadata
    text_content = models.TextField(verbose_name='محتوای متنی')
    
    # Sync tracking fields
    synced_to_core = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name='همگام‌سازی با Core',
        help_text='آیا این embedding به Core ارسال شده است؟'
    )
    
    synced_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='زمان همگام‌سازی',
        help_text='آخرین زمان ارسال به Core'
    )
    
    sync_error = models.TextField(
        blank=True,
        verbose_name='خطای همگام‌سازی',
        help_text='پیام خطا در صورت شکست sync'
    )
    
    sync_retry_count = models.PositiveIntegerField(
        default=0,
        verbose_name='تعداد تلاش مجدد'
    )
    
    # Change tracking
    metadata_hash = models.CharField(
        max_length=64,
        blank=True,
        db_index=True,
        verbose_name='هش متادیتا',
        help_text='هش SHA256 از metadata برای detect کردن تغییرات'
    )
    
    last_metadata_sync = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='آخرین sync متادیتا'
    )
    
    # Timestamps and history
    history = HistoricalRecords()
    
    # Custom manager
    objects = EmbeddingManager()

    class Meta:
        verbose_name = 'بردار'
        verbose_name_plural = 'لیست بردارها'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['model_name']),  # Legacy
            models.Index(fields=['dimension']),   # Legacy
            models.Index(fields=['model_id']),
            models.Index(fields=['dim']),
            models.Index(fields=['content_type', 'object_id', 'model_id'], name='embeddings_content_model_idx'),
            models.Index(fields=['model_id', 'dim'], name='embeddings_model_dim_idx'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['content_type', 'object_id', 'model_id'],
                name='unique_embedding_per_content_model'
            ),
        ]

    def __str__(self):
        return f"{self.content_object} - {self.model_name} ({self.dim}d)"
    
    def get_similar(
        self, 
        limit: int = 10, 
        similarity_threshold: float = 0.7
    ) -> QuerySet:
        """
        Find similar embeddings to this one.
        
        Args:
            limit: Maximum number of results to return
            similarity_threshold: Minimum similarity score (0-1)
            
        Returns:
            QuerySet of similar Embedding objects with similarity scores
        """
        return self.__class__.objects.cosine_search(
            query_vector=self.vector,
            model_name=self.model_name,
            dimension=self.dim,
            limit=limit,
            similarity_threshold=similarity_threshold
        ).exclude(id=self.id)  # Exclude self
    
    def update_embedding(self, vector: List[float], text_content: str = None):
        """Update the embedding vector and optionally the text content."""
        vector = np.array(vector, dtype=np.float32)
        # Keep the original dimension in dim, but pad/truncate to the column's fixed dimension
        self.dim = len(vector)
        required_dim = self._meta.get_field('vector').dimensions or getattr(settings, 'EMBEDDING_DIMENSION', 512)
        if self.dim < required_dim:
            padded = np.zeros(required_dim, dtype=np.float32)
            padded[: self.dim] = vector
            self.vector = padded.tolist()
        else:
            # Truncate if larger than column capacity
            self.vector = vector[:required_dim].tolist()
        
        if text_content is not None:
            self.text_content = text_content
            
        self.save(update_fields=['vector', 'dim', 'text_content', 'updated_at'])

    def save(self, *args, **kwargs):
        """Ensure vector length matches pgvector column dimension by zero-padding/truncation.
        Also default `model_id` from `model_name` if not provided (legacy support).
        
        Supports multiple embedding models with different dimensions:
        - Small models (384d, 512d, 768d) → zero-padded to max dimension
        - Large models (1024d, 1536d, 3072d) → zero-padded to max dimension
        - Future models → automatically supported up to max dimension
        """
        # Default model_id when missing
        if not getattr(self, 'model_id', None):
            self.model_id = getattr(self, 'model_name', '') or ''
        
        # Get maximum supported dimension (future-proof for large models)
        required_dim = self._meta.get_field('vector').dimensions or getattr(settings, 'EMBEDDING_DIMENSION', 4096)
        
        if self.vector is not None:
            vec = np.array(self.vector, dtype=np.float32)
            original_dim = len(vec)
            
            # Keep original dimension for search optimization
            if not getattr(self, 'dim', None):
                self.dim = original_dim
            
            if original_dim < required_dim:
                # Zero-pad smaller vectors (e.g., 768d → 4096d)
                padded = np.zeros(required_dim, dtype=np.float32)
                padded[:original_dim] = vec
                self.vector = padded.tolist()
                print(f"📦 Padded {original_dim}d vector to {required_dim}d for model {self.model_id}")
            elif original_dim > required_dim:
                # Truncate if larger (should rarely happen with 4096d limit)
                self.vector = vec[:required_dim].tolist()
                print(f"⚠️  Truncated {original_dim}d vector to {required_dim}d for model {self.model_id}")
            else:
                # Perfect match
                self.vector = vec.tolist()
                
        super().save(*args, **kwargs)

    @classmethod
    def batch_create_embeddings(
        cls,
        objects: List[models.Model],
        texts: List[str],
        vectors: List[List[float]],
        model_name: str = 'distiluse-base-multilingual-cased-v2',
        batch_size: int = 1000
    ) -> List['Embedding']:
        """
        Create multiple embeddings in bulk for better performance.
        
        Args:
            objects: List of model instances
            texts: List of text contents
            vectors: List of embedding vectors
            model_name: Name of the embedding model
            batch_size: Number of embeddings to create in each batch
            
        Returns:
            List of created Embedding instances
        """
        if not (len(objects) == len(texts) == len(vectors)):
            raise ValueError("objects, texts, and vectors must have the same length")
            
        embeddings = []
        for i in range(0, len(objects), batch_size):
            batch = []
            for obj, text, vector in zip(
                objects[i:i+batch_size],
                texts[i:i+batch_size],
                vectors[i:i+batch_size]
            ):
                batch.append(cls(
                    content_object=obj,
                    text_content=text,
                    vector=vector,
                    model_name=model_name,
                    dim=len(vector)
                ))
            
            created = cls.objects.bulk_create(batch, batch_size=batch_size)
            embeddings.extend(created)
            
        return embeddings


class CoreConfig(BaseModel):
    """
    تنظیمات اتصال به سیستم Core.
    این مدل Singleton است - فقط یک رکورد دارد.
    """
    
    class Meta:
        verbose_name = 'تنظیمات اتصال به سیستم مرکزی'
        verbose_name_plural = 'تنظیمات اتصال به سیستم مرکزی'
    
    # Core API connection
    core_api_url = models.URLField(
        verbose_name='آدرس API Core',
        help_text='مثال: http://localhost:7001',
        default='http://localhost:7001'
    )
    
    core_api_key = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='کلید API',
        help_text='API Key برای احراز هویت'
    )
    
    # Qdrant connection (optional - if direct connection needed)
    qdrant_host = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='آدرس Qdrant',
        default='localhost'
    )
    
    qdrant_port = models.PositiveIntegerField(
        default=7333,
        verbose_name='پورت Qdrant'
    )
    
    qdrant_api_key = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Qdrant API Key'
    )
    
    qdrant_collection = models.CharField(
        max_length=100,
        default='legal_documents',
        verbose_name='نام Collection'
    )
    
    # Sync settings
    auto_sync_enabled = models.BooleanField(
        default=True,
        verbose_name='همگام‌سازی خودکار',
        help_text='فعال‌سازی sync خودکار به Core'
    )
    
    sync_batch_size = models.PositiveIntegerField(
        default=100,
        verbose_name='تعداد رکورد در هر batch'
    )
    
    sync_interval_minutes = models.PositiveIntegerField(
        default=5,
        verbose_name='فاصله زمانی sync (دقیقه)'
    )
    
    retry_on_error = models.BooleanField(
        default=True,
        verbose_name='تلاش مجدد در صورت خطا'
    )
    
    max_retries = models.PositiveIntegerField(
        default=3,
        verbose_name='حداکثر تلاش مجدد'
    )
    
    # Change tracking
    track_metadata_changes = models.BooleanField(
        default=True,
        verbose_name='پیگیری تغییرات metadata',
        help_text='در صورت تغییر metadata، دوباره به Core ارسال شود'
    )
    
    # Status
    is_active = models.BooleanField(
        default=True,
        verbose_name='فعال'
    )
    
    last_successful_sync = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='آخرین sync موفق'
    )
    
    last_sync_error = models.TextField(
        blank=True,
        verbose_name='آخرین خطا'
    )
    
    # Statistics
    total_synced = models.PositiveIntegerField(
        default=0,
        verbose_name='تعداد کل sync شده'
    )
    
    total_errors = models.PositiveIntegerField(
        default=0,
        verbose_name='تعداد کل خطاها'
    )
    
    def __str__(self):
        return f"Core Config - {self.core_api_url}"
    
    def save(self, *args, **kwargs):
        """Ensure only one config exists (Singleton)."""
        self.pk = 1
        super().save(*args, **kwargs)
    
    @classmethod
    def get_config(cls):
        """Get the singleton config instance."""
        config, created = cls.objects.get_or_create(pk=1)
        return config
    
    def test_connection(self):
        """Test connection to Core API."""
        import requests
        try:
            response = requests.get(
                f"{self.core_api_url}/api/v1/health",
                headers={'X-API-Key': self.core_api_key} if self.core_api_key else {},
                timeout=5
            )
            return response.status_code == 200
        except Exception:
            return False
