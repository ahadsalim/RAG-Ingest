"""
Payload builder for Core sync with Summary metadata model.
"""
import hashlib
import json
from typing import Dict, Any, Optional
from django.utils import timezone

from ingest.apps.embeddings.models import Embedding
from ingest.apps.documents.models import Chunk, QAEntry, TextEntry


def build_summary_payload(embedding: Embedding) -> Optional[Dict[str, Any]]:
    """
    ساخت payload کامل با مدل Summary.
    
    Args:
        embedding: Embedding instance
        
    Returns:
        Dictionary با ساختار مدل Summary یا None در صورت خطا
    """
    try:
        source_obj = embedding.content_object
        
        if isinstance(source_obj, Chunk):
            return _build_chunk_payload(embedding, source_obj)
        elif isinstance(source_obj, QAEntry):
            return _build_qa_payload(embedding, source_obj)
        elif isinstance(source_obj, TextEntry):
            return _build_text_entry_payload(embedding, source_obj)
        else:
            return None
            
    except Exception as e:
        print(f"Error building payload for embedding {embedding.id}: {e}")
        return None


def _build_chunk_payload(embedding: Embedding, chunk: Chunk) -> Dict[str, Any]:
    """ساخت payload برای Chunk (از LegalUnit، QAEntry یا TextEntry)."""
    
    # Determine source type
    unit = chunk.unit
    qaentry = chunk.qaentry
    textentry = chunk.textentry
    
    # Handle QAEntry chunks
    if qaentry:
        return _build_qaentry_chunk_payload(embedding, chunk, qaentry)
    
    # Handle TextEntry chunks
    if textentry:
        return _build_textentry_chunk_payload(embedding, chunk, textentry)
    
    # Handle LegalUnit chunks (original behavior)
    if not unit:
        raise ValueError(f"Chunk {chunk.id} has no associated unit, qaentry, or textentry")
    
    expr = chunk.expr
    work = expr.work if expr else None
    manifestation = unit.manifestation if unit else None
    
    # Convert vector
    if hasattr(embedding.vector, 'tolist'):
        vector = embedding.vector.tolist()
    elif isinstance(embedding.vector, str):
        import numpy as np
        vector = np.fromstring(embedding.vector.strip('[]'), sep=',').tolist()
    else:
        vector = list(embedding.vector)
    
    # Ensure document_id is always set
    if work:
        document_id = str(work.id)
    elif unit:
        document_id = str(unit.id)
    else:
        raise ValueError(f"Cannot determine document_id for chunk {chunk.id}")
    
    # Get chunk index (شماره chunk در سند)
    chunk_index = None
    if hasattr(chunk, 'chunk_index'):
        chunk_index = chunk.chunk_index
    elif hasattr(chunk, 'position'):
        chunk_index = chunk.position
    
    # Determine document_type
    document_type = None
    if work:
        document_type = work.doc_type if hasattr(work, 'doc_type') else 'LAW'
    
    # Build tags list
    tags = []
    if hasattr(unit, 'vocabulary_terms'):
        try:
            tags = [term.term for term in unit.vocabulary_terms.all()]
        except:
            pass
    
    # Build payload according to new Core API structure
    payload = {
        # ====== فیلدهای سطح بالا (مطابق API جدید Core) ======
        'id': str(embedding.id),
        'vector': vector,
        'text': embedding.text_content or '',
        'document_id': document_id,
        
        # فیلدهای جدید اختیاری
        'document_type': document_type,
        'chunk_index': chunk_index,
        'language': expr.language.code if expr and expr.language else 'fa',
        'source': 'ingest',
        'created_at': chunk.created_at.isoformat(),
        
        # ====== metadata (تمام اطلاعات تکمیلی) ======
        'metadata': {
            # IDs
            'chunk_id': str(chunk.id),
            'unit_id': str(unit.id),
            'work_id': str(work.id) if work else None,
            'expression_id': str(expr.id) if expr else None,
            'manifestation_id': str(manifestation.id) if manifestation else None,
            
            # Content & Structure
            'path_label': unit.path_label or '',
            'unit_type': unit.unit_type if hasattr(unit, 'unit_type') else '',
            'unit_number': unit.number if hasattr(unit, 'number') else '',
            
            # Document Info
            'work_title': work.title_official if work else '',
            'urn_lex': work.urn_lex if work else '',
            'consolidation_level': expr.consolidation_level if expr else '',
            'expression_date': expr.expression_date.isoformat() if expr and expr.expression_date else None,
            
            # Publication
            'publication_date': manifestation.publication_date.isoformat() if manifestation and manifestation.publication_date else None,
            'official_gazette': manifestation.official_gazette_name if manifestation else '',
            'gazette_issue_no': manifestation.gazette_issue_no if manifestation else '',
            'source_url': manifestation.source_url if manifestation else '',
            
            # Legal Info
            'jurisdiction': work.jurisdiction.name if work and work.jurisdiction else '',
            'authority': work.authority.name if work and work.authority else '',
            
            # Validity
            'valid_from': unit.valid_from.isoformat() if unit.valid_from else None,
            'valid_to': unit.valid_to.isoformat() if unit.valid_to else None,
            'is_active': unit.is_active if hasattr(unit, 'is_active') else True,
            'in_force_from': manifestation.in_force_from.isoformat() if manifestation and manifestation.in_force_from else None,
            'in_force_to': manifestation.in_force_to.isoformat() if manifestation and manifestation.in_force_to else None,
            'repeal_status': manifestation.repeal_status if manifestation and hasattr(manifestation, 'repeal_status') else 'in_force',
            
            # Technical
            'token_count': chunk.token_count if hasattr(chunk, 'token_count') else 0,
            'overlap_prev': chunk.overlap_prev if hasattr(chunk, 'overlap_prev') else 0,
            'chunk_hash': chunk.hash if hasattr(chunk, 'hash') else '',
            
            # Embedding Metadata
            'embedding_model': embedding.model_id or embedding.model_name,
            'embedding_dimension': embedding.dim,
            'embedding_created_at': embedding.created_at.isoformat(),
            
            # Tags
            'tags': tags,
            
            # System
            'content_type': 'chunk',
            'updated_at': chunk.updated_at.isoformat(),
        }
    }
    
    return payload


def _build_qaentry_chunk_payload(embedding: Embedding, chunk: Chunk, qaentry: QAEntry) -> Dict[str, Any]:
    """ساخت payload برای Chunk از QAEntry."""
    
    # Convert vector
    if hasattr(embedding.vector, 'tolist'):
        vector = embedding.vector.tolist()
    elif isinstance(embedding.vector, str):
        import numpy as np
        vector = np.fromstring(embedding.vector.strip('[]'), sep=',').tolist()
    else:
        vector = list(embedding.vector)
    
    # Get related units info
    related_units = list(qaentry.related_units.select_related(
        'manifestation__expr__work'
    ).all())
    
    # Use first related unit's work for document_id if available
    first_unit = related_units[0] if related_units else None
    first_work = None
    if first_unit and first_unit.manifestation and first_unit.manifestation.expr:
        first_work = first_unit.manifestation.expr.work
    
    document_id = str(first_work.id) if first_work else str(qaentry.id)
    
    # Get chunk index from citation_payload_json
    chunk_index = chunk.citation_payload_json.get('chunk_index', 0) if chunk.citation_payload_json else 0
    
    # Build payload
    payload = {
        'id': str(embedding.id),
        'vector': vector,
        'text': chunk.chunk_text,
        'document_id': document_id,
        'document_type': 'QA',
        'chunk_index': chunk_index,
        'language': 'fa',
        'source': 'ingest',
        'created_at': chunk.created_at.isoformat(),
        
        'metadata': {
            'chunk_id': str(chunk.id),
            'qa_entry_id': str(qaentry.id),
            'question': qaentry.question[:200] if qaentry.question else '',
            'canonical_question': qaentry.canonical_question or '',
            
            # Related units info
            'related_units': [
                {
                    'unit_id': str(u.id),
                    'path_label': u.path_label or '',
                    'unit_type': u.unit_type,
                    'number': u.number or '',
                    'work_title': u.manifestation.expr.work.title_official if u.manifestation and u.manifestation.expr and u.manifestation.expr.work else '',
                }
                for u in related_units
            ],
            
            # Embedding Metadata
            'embedding_model': embedding.model_id or embedding.model_name,
            'embedding_dimension': embedding.dim,
            'embedding_created_at': embedding.created_at.isoformat(),
            
            # Tags
            'tags': [tag.term for tag in qaentry.tags.all()],
            
            # System
            'content_type': 'qa_chunk',
            'updated_at': chunk.updated_at.isoformat(),
        }
    }
    
    return payload


def _build_textentry_chunk_payload(embedding: Embedding, chunk: Chunk, textentry: TextEntry) -> Dict[str, Any]:
    """ساخت payload برای Chunk از TextEntry."""
    
    # Convert vector
    if hasattr(embedding.vector, 'tolist'):
        vector = embedding.vector.tolist()
    elif isinstance(embedding.vector, str):
        import numpy as np
        vector = np.fromstring(embedding.vector.strip('[]'), sep=',').tolist()
    else:
        vector = list(embedding.vector)
    
    # Get related units info
    related_units = list(textentry.related_units.select_related(
        'manifestation__expr__work'
    ).all())
    
    # Use first related unit's work for document_id if available
    first_unit = related_units[0] if related_units else None
    first_work = None
    if first_unit and first_unit.manifestation and first_unit.manifestation.expr:
        first_work = first_unit.manifestation.expr.work
    
    document_id = str(first_work.id) if first_work else str(textentry.id)
    
    # Get chunk index from citation_payload_json
    chunk_index = chunk.citation_payload_json.get('chunk_index', 0) if chunk.citation_payload_json else 0
    
    # Build payload
    payload = {
        'id': str(embedding.id),
        'vector': vector,
        'text': chunk.chunk_text,
        'document_id': document_id,
        'document_type': 'TEXT',
        'chunk_index': chunk_index,
        'language': 'fa',
        'source': 'ingest',
        'created_at': chunk.created_at.isoformat(),
        
        'metadata': {
            'chunk_id': str(chunk.id),
            'text_entry_id': str(textentry.id),
            'title': textentry.title,
            'original_filename': textentry.original_filename or '',
            
            # Related units info
            'related_units': [
                {
                    'unit_id': str(u.id),
                    'path_label': u.path_label or '',
                    'unit_type': u.unit_type,
                    'number': u.number or '',
                    'work_title': u.manifestation.expr.work.title_official if u.manifestation and u.manifestation.expr and u.manifestation.expr.work else '',
                }
                for u in related_units
            ],
            
            # Embedding Metadata
            'embedding_model': embedding.model_id or embedding.model_name,
            'embedding_dimension': embedding.dim,
            'embedding_created_at': embedding.created_at.isoformat(),
            
            # Tags
            'tags': [tag.term for tag in textentry.vocabulary_terms.all()],
            
            # System
            'content_type': 'text_chunk',
            'updated_at': chunk.updated_at.isoformat(),
        }
    }
    
    return payload


def _build_qa_payload(embedding: Embedding, qa_entry: QAEntry) -> Dict[str, Any]:
    """ساخت payload برای QA Entry (deprecated - now uses chunks)."""
    
    # Convert vector
    if hasattr(embedding.vector, 'tolist'):
        vector = embedding.vector.tolist()
    else:
        vector = list(embedding.vector)
    
    # Get related units info
    related_units = list(qa_entry.related_units.select_related(
        'manifestation__expr__work'
    ).all())
    
    # Use first related unit's work for document_id if available
    first_unit = related_units[0] if related_units else None
    first_work = None
    if first_unit and first_unit.manifestation and first_unit.manifestation.expr:
        first_work = first_unit.manifestation.expr.work
    
    document_id = str(first_work.id) if first_work else str(qa_entry.id)
    
    # Build payload
    payload = {
        'id': str(embedding.id),
        'vector': vector,
        'text': f"Q: {qa_entry.question}\nA: {qa_entry.answer}",
        'document_id': document_id,
        'document_type': 'QA',
        'chunk_index': None,
        'language': 'fa',
        'source': 'ingest',
        'created_at': qa_entry.created_at.isoformat(),
        
        'metadata': {
            'qa_entry_id': str(qa_entry.id),
            'question': qa_entry.question,
            'answer': qa_entry.answer,
            'canonical_question': qa_entry.canonical_question or '',
            
            # Related units info
            'related_units': [
                {
                    'unit_id': str(u.id),
                    'path_label': u.path_label or '',
                    'unit_type': u.unit_type,
                    'number': u.number or '',
                    'work_title': u.manifestation.expr.work.title_official if u.manifestation and u.manifestation.expr and u.manifestation.expr.work else '',
                }
                for u in related_units
            ],
            
            # Embedding Metadata
            'embedding_model': embedding.model_id or embedding.model_name,
            'embedding_dimension': embedding.dim,
            'embedding_created_at': embedding.created_at.isoformat(),
            
            # Tags
            'tags': [tag.term for tag in qa_entry.tags.all()],
            
            # System
            'content_type': 'qa_entry',
            'updated_at': qa_entry.updated_at.isoformat(),
        }
    }
    
    return payload


def _build_text_entry_payload(embedding: Embedding, text_entry: TextEntry) -> Dict[str, Any]:
    """ساخت payload برای TextEntry."""
    
    # Convert vector
    if hasattr(embedding.vector, 'tolist'):
        vector = embedding.vector.tolist()
    else:
        vector = list(embedding.vector)
    
    # Get related units info
    related_units = list(text_entry.related_units.select_related(
        'manifestation__expr__work'
    ).all())
    
    # Use first related unit's work for document_id if available
    first_unit = related_units[0] if related_units else None
    first_work = None
    if first_unit and first_unit.manifestation and first_unit.manifestation.expr:
        first_work = first_unit.manifestation.expr.work
    
    document_id = str(first_work.id) if first_work else str(text_entry.id)
    
    # Build payload
    payload = {
        'id': str(embedding.id),
        'vector': vector,
        'text': f"{text_entry.title}\n\n{text_entry.content}",
        'document_id': document_id,
        'document_type': 'TEXT',
        'chunk_index': None,
        'language': 'fa',
        'source': 'ingest',
        'created_at': text_entry.created_at.isoformat(),
        
        'metadata': {
            'text_entry_id': str(text_entry.id),
            'title': text_entry.title,
            'content_preview': text_entry.content[:500] if text_entry.content else '',
            'original_filename': text_entry.original_filename or '',
            
            # Related units info
            'related_units': [
                {
                    'unit_id': str(u.id),
                    'path_label': u.path_label or '',
                    'unit_type': u.unit_type,
                    'number': u.number or '',
                    'work_title': u.manifestation.expr.work.title_official if u.manifestation and u.manifestation.expr and u.manifestation.expr.work else '',
                }
                for u in related_units
            ],
            
            # Embedding Metadata
            'embedding_model': embedding.model_id or embedding.model_name,
            'embedding_dimension': embedding.dim,
            'embedding_created_at': embedding.created_at.isoformat(),
            
            # Tags
            'tags': [tag.term for tag in text_entry.vocabulary_terms.all()],
            
            # System
            'content_type': 'text_entry',
            'updated_at': text_entry.updated_at.isoformat(),
        }
    }
    
    return payload


def calculate_metadata_hash(payload: Dict[str, Any]) -> str:
    """
    محاسبه هش از metadata برای track کردن تغییرات.
    فقط فیلدهای مهم را در نظر می‌گیرد (بدون vector و timestamps).
    """
    # فیلدهایی که باید track شوند
    tracked_fields = [
        'text', 'path_label', 'unit_type', 'unit_number',
        'work_title', 'doc_type', 'language',
        'jurisdiction', 'authority',
        'valid_from', 'valid_to', 'is_active',
        'repeal_status', 'tags'
    ]
    
    # ساخت dict فقط با فیلدهای tracked
    tracked_data = {
        k: v for k, v in payload.items() 
        if k in tracked_fields
    }
    
    # محاسبه هش
    data_str = json.dumps(tracked_data, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(data_str.encode('utf-8')).hexdigest()
