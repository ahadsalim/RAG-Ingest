"""
Signal handlers for document models.
سیگنال‌های مدیریت حذف و به‌روزرسانی

DEPRECATED: این فایل منسوخ شده و به signals_unified.py منتقل شده است.
این فایل فقط برای backward compatibility نگه داشته شده.
"""

# Re-export everything from unified signals for backward compatibility
from .signals_unified import (
    handle_legalunit_pre_delete,
    delete_legal_unit_chunks,
    handle_chunk_pre_delete,
    handle_chunk_post_delete,
    handle_fileasset_pre_delete,
    SafeDeletionMixin,
    cleanup_orphaned_synclogs,
)

import warnings
warnings.warn(
    "signals.py is deprecated. Use signals_unified.py instead.",
    DeprecationWarning,
    stacklevel=2
)

import logging
logger = logging.getLogger(__name__)

# همه توابع و کلاس‌ها از signals_unified.py re-export می‌شوند
# کد قدیمی برای جلوگیری از ثبت signal های تکراری حذف شده
