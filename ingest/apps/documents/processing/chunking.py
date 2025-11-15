"""Service for processing document chunks."""
import hashlib
import logging
from typing import Dict, List, Optional, Union
from uuid import UUID

from django.conf import settings
from django.db import transaction

from .base import BaseProcessingService
from django.core.exceptions import ValidationError as ProcessingError

logger = logging.getLogger(__name__)


class ChunkProcessingService(BaseProcessingService):
    """Service for processing document chunks (from LegalUnit or QAEntry)."""
    
    def __init__(self, chunk_size: int = None, chunk_overlap: int = None):
        """Initialize the chunking service.
        
        Args:
            chunk_size: Size of each chunk in tokens
            chunk_overlap: Number of tokens to overlap between chunks
        """
        # Don't call super().__init__() to avoid Prometheus label issues
        self.logger = logger
        self.chunk_size = chunk_size or getattr(settings, 'DEFAULT_CHUNK_SIZE', 1000)
        self.chunk_overlap = chunk_overlap or getattr(settings, 'DEFAULT_CHUNK_OVERLAP', 100)
    
    def process(self, item_id: str, **kwargs) -> Dict:
        """Process a single item (implements abstract method).
        
        Uses process_item internally.
        """
        item_type = kwargs.get('item_type', 'legal_unit')
        return self.process_item(item_id, item_type, **kwargs)
    
    def process_document(self, document_id: Union[str, UUID]) -> Dict:
        """Process a document and create chunks.
        
        Args:
            document_id: ID of the document to process
            
        Returns:
            Dict containing processing results
            
        Raises:
            ProcessingError: If processing fails
        """
        from ..models import Document, Chunk
        
        try:
            document = Document.objects.get(id=document_id)
        except Document.DoesNotExist:
            raise ProcessingError(f"Document {document_id} not found")
        
        # Get or create chunks for the document's legal units
        results = {}
        for unit in document.legal_units.all():
            try:
                result = self.process_legal_unit(unit.id)
                results[str(unit.id)] = result
            except Exception as e:
                logger.error(f"Error processing legal unit {unit.id}: {str(e)}", exc_info=True)
                results[str(unit.id)] = {'success': False, 'error': str(e)}
        
        return {
            'document_id': str(document_id),
            'unit_results': results,
            'success': all(r.get('success', False) for r in results.values())
        }
    
    def process_legal_unit(self, unit_id: Union[str, UUID]) -> Dict:
        """Process a legal unit and create chunks.
        
        Args:
            unit_id: ID of the legal unit to process
            
        Returns:
            Dict containing processing results
            
        Raises:
            ProcessingError: If processing fails
        """
        from ..models import LegalUnit, Chunk
        
        try:
            unit = LegalUnit.objects.get(id=unit_id)
        except LegalUnit.DoesNotExist:
            raise ProcessingError(f"Legal unit {unit_id} not found")
        
        # Delete existing chunks for this unit
        Chunk.objects.filter(unit=unit).delete()
        
        chunks = self._split_into_chunks(unit.content)
        
        # Create chunk records
        created_chunks = []
        for i, chunk_text in enumerate(chunks):
            # Generate unique hash for chunk including unit_id to avoid duplicates
            hash_input = f"{chunk_text}_{unit_id}_{i}".encode('utf-8')
            chunk_hash = hashlib.sha256(hash_input).hexdigest()
            
            chunk = Chunk.objects.create(
                expr=unit.expr,  # Can be None - that's OK
                unit=unit,
                chunk_text=chunk_text,
                token_count=len(chunk_text.split()),  # Simple tokenization
                overlap_prev=self.chunk_overlap if i > 0 else 0,
                citation_payload_json={
                    'unit_id': str(unit_id),
                    'chunk_index': i,
                    'total_chunks': len(chunks)
                },
                hash=chunk_hash
            )
            created_chunks.append(chunk.id)
        
        # Log processing result (simplified)
        logger.info(f"Created {len(created_chunks)} chunks for unit {unit_id}")
        
        return {
            'unit_id': str(unit_id),
            'chunks_created': len(created_chunks),
            'success': True
        }
    
    def _split_into_chunks(self, text: str) -> List[str]:
        """Split text into chunks with overlap, respecting sentence boundaries.
        
        Uses hazm library to split text by sentences, then groups sentences into chunks
        based on token count while respecting sentence boundaries.
        
        Args:
            text: Text to split into chunks
            
        Returns:
            List of text chunks
        """
        if not text:
            return []
        
        try:
            # Try to use hazm for sentence splitting
            from hazm import sent_tokenize, word_tokenize
            
            # Split text into sentences
            sentences = sent_tokenize(text)
            if not sentences:
                return []
            
            chunks = []
            current_chunk = []
            current_token_count = 0
            
            for sentence in sentences:
                # Count tokens in the sentence
                sentence_tokens = word_tokenize(sentence)
                sentence_token_count = len(sentence_tokens)
                
                # Check if adding this sentence would exceed chunk_size
                if current_token_count + sentence_token_count > self.chunk_size and current_chunk:
                    # Save current chunk
                    chunks.append(' '.join(current_chunk))
                    
                    # Start new chunk with overlap
                    # Keep last few sentences for overlap
                    overlap_tokens = 0
                    overlap_sentences = []
                    for prev_sentence in reversed(current_chunk):
                        prev_tokens = word_tokenize(prev_sentence)
                        if overlap_tokens + len(prev_tokens) <= self.chunk_overlap:
                            overlap_sentences.insert(0, prev_sentence)
                            overlap_tokens += len(prev_tokens)
                        else:
                            break
                    
                    current_chunk = overlap_sentences
                    current_token_count = overlap_tokens
                
                # Add sentence to current chunk
                current_chunk.append(sentence)
                current_token_count += sentence_token_count
            
            # Add the last chunk if it's not empty
            if current_chunk:
                chunks.append(' '.join(current_chunk))
            
            return chunks
            
        except ImportError:
            logger.warning("hazm library not available, falling back to simple word-based splitting")
            # Fallback to simple word-based splitting
            words = text.split()
            chunks = []
            
            for i in range(0, len(words), self.chunk_size - self.chunk_overlap):
                chunk = ' '.join(words[i:i + self.chunk_size])
                chunks.append(chunk)
                
                if i + self.chunk_size >= len(words):
                    break
                    
            return chunks
    
    def process_qaentry(self, qaentry_id: Union[str, UUID]) -> Dict:
        """Process a QAEntry and create chunks.
        
        Args:
            qaentry_id: ID of the QAEntry to process
            
        Returns:
            Dict containing processing results
            
        Raises:
            ProcessingError: If processing fails
        """
        from ..models import QAEntry, Chunk
        
        try:
            qaentry = QAEntry.objects.get(id=qaentry_id)
        except QAEntry.DoesNotExist:
            raise ProcessingError(f"QAEntry {qaentry_id} not found")
        
        # Delete existing chunks for this QAEntry
        Chunk.objects.filter(qaentry=qaentry).delete()
        
        # ترکیب سوال و جواب
        combined_text = f"سوال: {qaentry.question}\n\nجواب: {qaentry.answer}"
        
        chunks = self._split_into_chunks(combined_text)
        
        # Create chunk records
        created_chunks = []
        for i, chunk_text in enumerate(chunks):
            # Generate unique hash for chunk
            hash_input = f"{chunk_text}_{qaentry_id}_{i}".encode('utf-8')
            chunk_hash = hashlib.sha256(hash_input).hexdigest()
            
            chunk = Chunk.objects.create(
                qaentry=qaentry,
                chunk_text=chunk_text,
                token_count=len(chunk_text.split()),
                overlap_prev=self.chunk_overlap if i > 0 else 0,
                citation_payload_json={
                    'qaentry_id': str(qaentry_id),
                    'question': qaentry.question[:100],
                    'chunk_index': i
                },
                hash=chunk_hash
            )
            created_chunks.append(chunk)
        
        logger.info(f"Created {len(created_chunks)} chunks for QAEntry {qaentry_id}")
        
        return {
            'success': True,
            'qaentry_id': str(qaentry_id),
            'chunks_created': len(created_chunks),
            'chunk_ids': [str(c.id) for c in created_chunks]
        }
    
    def process_item(self, item_id: Union[str, UUID], item_type: str, **kwargs) -> Dict:
        """Process an item based on its type.
        
        Args:
            item_id: ID of the item to process
            item_type: Type of item ('document', 'legal_unit', or 'qaentry')
            **kwargs: Additional arguments for processing
            
        Returns:
            Dict containing processing results
            
        Raises:
            ValueError: If item_type is invalid
        """
        if item_type == 'document':
            return self.process_document(item_id, **kwargs)
        elif item_type == 'legal_unit':
            return self.process_legal_unit(item_id, **kwargs)
        elif item_type == 'qaentry':
            return self.process_qaentry(item_id, **kwargs)
        else:
            raise ValueError(f"Invalid item_type: {item_type}. Must be 'document', 'legal_unit', or 'qaentry'.")


# Singleton instance
_chunk_processing_service = None


def get_chunk_processing_service() -> ChunkProcessingService:
    """Get or create a singleton instance of ChunkProcessingService.
    
    Returns:
        ChunkProcessingService: The singleton service instance
    """
    global _chunk_processing_service
    if _chunk_processing_service is None:
        _chunk_processing_service = ChunkProcessingService()
    return _chunk_processing_service
