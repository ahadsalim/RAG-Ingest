"""
Payload builder for Core sync with Summary metadata model.
"""
import hashlib
import json
from typing import Dict, Any, Optional
from django.utils import timezone

from ingest.apps.embeddings.models import Embedding
from ingest.apps.documents.models import Chunk, QAEntry


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
        else:
            return None
            
    except Exception as e:
        print(f"Error building payload for embedding {embedding.id}: {e}")
        return None


def _build_chunk_payload(embedding: Embedding, chunk: Chunk) -> Dict[str, Any]:
    """ساخت payload برای Chunk."""
    
    unit = chunk.unit
    if not unit:
        raise ValueError(f"Chunk {chunk.id} has no associated unit")
    
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


def _build_qa_payload(embedding: Embedding, qa_entry: QAEntry) -> Dict[str, Any]:
    """ساخت payload برای QA Entry."""
    
    # Convert vector
    if hasattr(embedding.vector, 'tolist'):
        vector = embedding.vector.tolist()
    else:
        vector = list(embedding.vector)
    
    source_unit = qa_entry.source_unit
    source_work = qa_entry.source_work
    
    # Ensure document_id is always set
    if source_work:
        document_id = str(source_work.id)
    elif source_unit:
        document_id = str(source_unit.id)
    else:
        document_id = str(qa_entry.id)
    
    # Determine document_type for QA
    document_type = 'QA'
    if source_work and hasattr(source_work, 'doc_type'):
        document_type = f"QA_{source_work.doc_type}"
    
    # Build payload according to new Core API structure
    payload = {
        # ====== فیلدهای سطح بالا (مطابق API جدید Core) ======
        'id': str(embedding.id),
        'vector': vector,
        'text': f"Q: {qa_entry.question}\nA: {qa_entry.answer}",
        'document_id': document_id,
        
        # فیلدهای جدید اختیاری
        'document_type': document_type,
        'chunk_index': None,  # QA entries don't have chunk index
        'language': 'fa',
        'source': 'ingest',
        'created_at': qa_entry.created_at.isoformat(),
        
        # ====== metadata (تمام اطلاعات تکمیلی) ======
        'metadata': {
            # IDs
            'qa_entry_id': str(qa_entry.id),
            'unit_id': str(source_unit.id) if source_unit else None,
            'work_id': str(source_work.id) if source_work else None,
            
            # Content
            'question': qa_entry.question,
            'answer': qa_entry.answer,
            'canonical_question': qa_entry.canonical_question or '',
            
            # Document Info
            'work_title': source_work.title_official if source_work else '',
            
            # Legal Info
            'jurisdiction': source_work.jurisdiction.name if source_work and source_work.jurisdiction else '',
            'authority': source_work.authority.name if source_work and source_work.authority else '',
            
            # Status
            'status': qa_entry.status,
            'is_active': qa_entry.is_approved,
            
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
