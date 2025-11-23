"""
Services for text chunking and embedding operations.
"""
import hashlib
import json
import logging
from typing import List, Dict, Any, Tuple
from django.db import transaction
from django.conf import settings

# ML dependencies will be imported lazily when needed
ML_DEPENDENCIES_AVAILABLE = None  # Will be set on first use

from .models import LegalUnit, IngestLog, InstrumentExpression
from ingest.apps.embeddings.models import Embedding
from django.contrib.contenttypes.models import ContentType
from .enums import IngestStatus

logger = logging.getLogger(__name__)


class TextChunkingService:
    """Service for chunking legal unit text into overlapping segments."""
    
    def __init__(self):
        self.tokenizer = None
        
    def _load_tokenizer(self):
        """Load tokenizer if not already loaded."""
        if hasattr(self, 'tokenizer') and self.tokenizer is not None:
            return True
            
        # Lazy import of ML dependencies
        global ML_DEPENDENCIES_AVAILABLE
        if ML_DEPENDENCIES_AVAILABLE is None:
            try:
                from transformers import AutoTokenizer
                ML_DEPENDENCIES_AVAILABLE = True
                self._AutoTokenizer = AutoTokenizer
            except ImportError:
                ML_DEPENDENCIES_AVAILABLE = False
                logger.warning("ML dependencies not available. Please install: pip install sentence-transformers transformers torch")
                return False
        elif not ML_DEPENDENCIES_AVAILABLE:
            return False
            
        try:
            self.tokenizer = self._AutoTokenizer.from_pretrained('distilbert-base-multilingual-cased')
            return True
        except Exception as e:
            logger.warning(f"Failed to load tokenizer: {str(e)}")
            return False
        
    def count_tokens(self, text: str) -> int:
        """Count tokens in text using the tokenizer."""
        if not self._load_tokenizer():
            # Fallback to word count approximation if tokenizer unavailable
            return len(text.split()) * 1.3  # Rough approximation
        tokens = self.tokenizer.encode(text, add_special_tokens=False)
        return len(tokens)
    
    def chunk_text(self, text: str, max_tokens: int = 900, min_tokens: int = 700, overlap: int = 100) -> List[Dict[str, Any]]:
        """
        Split text into overlapping chunks.
        
        Args:
            text: Input text to chunk
            max_tokens: Maximum tokens per chunk
            min_tokens: Minimum tokens per chunk
            overlap: Number of tokens to overlap between chunks
            
        Returns:
            List of dictionaries with chunk data
        """
        total_tokens = self.count_tokens(text)
        
        # If text is short enough, return as single chunk
        if total_tokens <= max_tokens:
            return [{
                'text': text,
                'token_count': int(total_tokens),
                'overlap_prev': 0,
                'index': 0
            }]
        
        chunks = []
        words = text.split()
        current_chunk_words = []
        current_tokens = 0
        
        i = 0
        while i < len(words):
            word = words[i]
            word_tokens = self.count_tokens(word)
            
            # If adding this word exceeds max_tokens, finalize current chunk
            if current_tokens + word_tokens > max_tokens and current_chunk_words:
                chunk_text = ' '.join(current_chunk_words)
                overlap_tokens = 0
                
                # Calculate overlap for next chunk
                if chunks:  # Not the first chunk
                    overlap_words = current_chunk_words[-overlap:] if len(current_chunk_words) > overlap else current_chunk_words
                    overlap_tokens = self.count_tokens(' '.join(overlap_words))
                
                chunks.append({
                    'text': chunk_text,
                    'token_count': int(current_tokens),
                    'overlap_prev': int(overlap_tokens) if len(chunks) > 0 else 0,
                    'index': len(chunks)
                })
                
                # Start next chunk with overlap
                if len(current_chunk_words) > overlap:
                    current_chunk_words = current_chunk_words[-overlap:]
                    current_tokens = self.count_tokens(' '.join(current_chunk_words))
                else:
                    current_chunk_words = []
                    current_tokens = 0
            else:
                current_chunk_words.append(word)
                current_tokens += word_tokens
                i += 1
        
        # Add final chunk if there are remaining words
        if current_chunk_words:
            chunk_text = ' '.join(current_chunk_words)
            overlap_tokens = 0
            if chunks:  # Calculate overlap for final chunk
                overlap_words = current_chunk_words[:overlap] if len(current_chunk_words) > overlap else current_chunk_words
                overlap_tokens = self.count_tokens(' '.join(overlap_words))
            
            chunks.append({
                'text': chunk_text,
                'token_count': int(current_tokens),
                'overlap_prev': int(overlap_tokens) if len(chunks) > 0 else 0,
                'index': len(chunks)
            })
        
        return chunks
    
    def create_citation_payload(self, unit: LegalUnit) -> Dict[str, Any]:
        """Create citation payload JSON for a legal unit."""
        return {
            'unit_type': unit.get_unit_type_display(),
            'num_label': unit.number or unit.label,
            'eli_fragment': unit.eli_fragment or '',
            'xml_id': unit.xml_id or ''
        }
    
    def generate_hash(self, text: str) -> str:
        """Generate SHA-256 hash for chunk text."""
        return hashlib.sha256(text.encode('utf-8')).hexdigest()


class EmbeddingService:
    """Service for generating embeddings using sentence transformers."""
    
    def __init__(self):
        self.model_name = 'distiluse-base-multilingual-cased-v2'
        self.model = None
    
    def _load_model(self):
        """Lazy load the embedding model only when embeddings are enabled."""
        if not getattr(settings, 'EMBEDDINGS_ENABLED', True):
            logger.warning("Embeddings are disabled. Model not loaded.")
            return False
            
        if self.model is None:
            # Lazy import of ML dependencies
            global ML_DEPENDENCIES_AVAILABLE
            if ML_DEPENDENCIES_AVAILABLE is None:
                try:
                    from sentence_transformers import SentenceTransformer
                    ML_DEPENDENCIES_AVAILABLE = True
                    # Store the class reference properly
                    globals()['SentenceTransformer'] = SentenceTransformer
                except ImportError:
                    ML_DEPENDENCIES_AVAILABLE = False
                    logger.warning("ML dependencies not available. Please install: pip install sentence-transformers transformers torch")
                    return False
            elif not ML_DEPENDENCIES_AVAILABLE:
                return False
                
            try:
                # Use the globally stored class reference
                from sentence_transformers import SentenceTransformer
                self.model = SentenceTransformer(self.model_name)
                return True
            except Exception as e:
                logger.warning(f"Failed to load embedding model: {str(e)}")
                return False
        return True
    
    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding vector for text."""
        if not self._load_model():
            logger.warning("Embedding model unavailable, returning empty list")
            return []
        embedding = self.model.encode(text)
        return embedding.tolist()


class ChunkProcessingService:
    """Main service for processing legal units into chunks and embeddings."""
    
    def __init__(self):
        self.chunking_service = TextChunkingService()
        self.embedding_service = EmbeddingService()
    
    @transaction.atomic
    def process_expression(self, expression: InstrumentExpression) -> Dict[str, Any]:
        """
        Process all legal units in an expression to create chunks and embeddings.
        
        Args:
            expression: InstrumentExpression to process
            
        Returns:
            Dictionary with processing results
        """
        # Create ingest log entry
        log_entry = IngestLog.objects.create(
            operation_type='chunk_processing',
            source_system='chunking_service',
            status=IngestStatus.PROCESSING,
            metadata={'expression_id': str(expression.id)}
        )
        
        try:
            results = {
                'chunks_created': 0,
                'embeddings_created': 0,
                'units_processed': 0,
                'errors': []
            }
            
            # Get all legal units for this expression
            legal_units = LegalUnit.objects.filter(expr=expression).order_by('tree_id', 'lft')
            
            for unit in legal_units:
                try:
                    unit_result = self.process_legal_unit(unit)
                    results['chunks_created'] += unit_result['chunks_created']
                    results['embeddings_created'] += unit_result['embeddings_created']
                    results['units_processed'] += 1
                except Exception as e:
                    error_msg = f"Error processing unit {unit.id}: {str(e)}"
                    logger.error(error_msg)
                    results['errors'].append(error_msg)
            
            # Update log entry
            log_entry.status = IngestStatus.COMPLETED if not results['errors'] else IngestStatus.FAILED
            log_entry.metadata.update(results)
            log_entry.save()
            
            return results
            
        except Exception as e:
            log_entry.status = IngestStatus.FAILED
            log_entry.metadata['error'] = str(e)
            raise
    
    def process_legal_unit(self, unit: LegalUnit) -> Dict[str, Any]:
        """
        Process a single legal unit to create chunks and embeddings.
        
        Args:
            unit: LegalUnit to process
            
        Returns:
            Dictionary with processing results for this unit
        """
        from .models import Chunk
        
        results = {'chunks_created': 0, 'embeddings_created': 0, 'chunks_deleted': 0}
        
        # Skip if unit has no content
        if not unit.content or not unit.content.strip():
            return results
        
        # حذف چانک‌های قدیمی قبل از ایجاد چانک‌های جدید
        # توجه: حذف Chunk به صورت خودکار Embedding های مرتبط را هم حذف می‌کند (CASCADE)
        old_chunks_count = Chunk.objects.filter(unit=unit).count()
        if old_chunks_count > 0:
            Chunk.objects.filter(unit=unit).delete()
            results['chunks_deleted'] = old_chunks_count
        
        # Create chunks for the legal unit
        chunks = self.chunking_service.chunk_text(unit.content)
        
        for chunk_data in chunks:
            try:
                # Create chunk hash
                chunk_hash = hashlib.sha256(
                    f"{unit.id}_{chunk_data['text']}".encode('utf-8')
                ).hexdigest()
                
                # Check if chunk already exists
                if Chunk.objects.filter(unit=unit, hash=chunk_hash).exists():
                    continue
                
                # Create citation payload
                citation_payload = {
                    'unit_id': str(unit.id),
                    'unit_label': getattr(unit, 'label', '') or f"{unit.get_unit_type_display()} {unit.number}",
                    'unit_path': unit.path_label,
                    'chunk_index': chunk_data.get('index', 0)
                }
                
                # Create chunk
                chunk = Chunk.objects.create(
                    expr=unit.expr,
                    unit=unit,
                    chunk_text=chunk_data['text'],
                    token_count=chunk_data['token_count'],
                    overlap_prev=chunk_data.get('overlap_prev', 0),
                    citation_payload_json=citation_payload,
                    hash=chunk_hash
                )
                results['chunks_created'] += 1
                
                # Generate embedding for chunk
                try:
                    embedding_vector = self.embedding_service.generate_embedding(chunk_data['text'])
                    
                    if embedding_vector:
                        chunk_content_type = ContentType.objects.get_for_model(Chunk)
                        Embedding.objects.create(
                            content_type=chunk_content_type,
                            object_id=chunk.id,
                            model_name=self.embedding_service.model_name,
                            vector=embedding_vector,
                            text_content=chunk_data['text']
                        )
                        results['embeddings_created'] += 1
                        
                except Exception as e:
                    logger.error(f"Failed to create embedding for chunk {chunk.id}: {str(e)}")
                    
            except Exception as e:
                logger.error(f"Failed to create chunk for legal unit {unit.id}: {str(e)}")
        
        return results


# Service instances - lazy initialization to avoid ML dependency errors at startup
chunk_processing_service = None

def get_chunk_processing_service():
    global chunk_processing_service
    if chunk_processing_service is None:
        chunk_processing_service = ChunkProcessingService()
    return chunk_processing_service
