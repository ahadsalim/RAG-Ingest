"""
Complete signal handlers for automatic chunking and embedding.
Handles: LegalUnit and QAEntry creation, updates, and deletions.

DEPRECATED: این فایل منسوخ شده و به signals_unified.py منتقل شده است.
این فایل فقط برای backward compatibility نگه داشته شده.
"""

# Re-export everything from unified signals for backward compatibility
from .signals_unified import (
    track_legal_unit_changes,
    process_legal_unit_on_save,
    delete_legal_unit_chunks,
    track_qa_entry_changes,
    process_qa_entry_on_save,
    delete_qa_entry_embeddings,
    generate_embedding_on_chunk_created,
)

import logging
logger = logging.getLogger(__name__)

# همه توابع از signals_unified.py re-export می‌شوند
# کد قدیمی برای جلوگیری از ثبت signal های تکراری حذف شده
