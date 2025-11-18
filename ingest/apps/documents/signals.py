"""
Signal handlers for document models.
سیگنال‌های مدیریت حذف و به‌روزرسانی
"""

from django.db.models.signals import pre_delete, post_delete, pre_save, post_save
from django.dispatch import receiver
from django.db import transaction
import logging

from .models import LegalUnit, Chunk, FileAsset
from ingest.apps.embeddings.models_synclog import SyncLog

logger = logging.getLogger(__name__)


@receiver(pre_delete, sender=LegalUnit)
def handle_legalunit_pre_delete(sender, instance, **kwargs):
    """
    قبل از حذف LegalUnit، ابتدا SyncLog های مرتبط را پاکسازی می‌کنیم.
    این مشکل cascade deletion را حل می‌کند.
    """
    try:
        # Get all chunks related to this legal unit
        chunk_ids = list(instance.chunks.values_list('id', flat=True))
        
        if chunk_ids:
            # Delete all SyncLogs related to these chunks
            deleted_count = SyncLog.objects.filter(chunk_id__in=chunk_ids).delete()[0]
            
            if deleted_count > 0:
                logger.info(
                    f"Deleted {deleted_count} SyncLog entries for LegalUnit {instance.id} "
                    f"before deletion"
                )
        
        # Also handle file cleanup
        for file_asset in instance.files.all():
            try:
                if file_asset.file:
                    file_asset.file.delete(save=False)
            except Exception as e:
                logger.error(f"Error deleting file for FileAsset {file_asset.id}: {e}")
                
    except Exception as e:
        logger.error(f"Error in pre_delete handler for LegalUnit {instance.id}: {e}")
        # Don't prevent deletion even if cleanup fails


@receiver(post_delete, sender=Chunk)
def handle_chunk_post_delete(sender, instance, **kwargs):
    """
    بعد از حذف Chunk، اطلاعات مرتبط را لاگ می‌کنیم.
    """
    logger.info(
        f"Chunk {instance.id} deleted. "
        f"Unit: {instance.unit_id}, Expression: {instance.expr_id}"
    )


@receiver(pre_delete, sender=FileAsset)
def handle_fileasset_pre_delete(sender, instance, **kwargs):
    """
    قبل از حذف FileAsset، فایل فیزیکی را از MinIO پاک می‌کنیم.
    """
    try:
        if instance.file:
            # Delete the actual file from storage
            instance.file.delete(save=False)
            logger.info(f"Deleted file from storage for FileAsset {instance.id}")
    except Exception as e:
        logger.error(f"Error deleting file from storage for FileAsset {instance.id}: {e}")


class SafeDeletionMixin:
    """
    Mixin برای حذف امن مدل‌هایی که روابط پیچیده دارند.
    """
    
    def safe_delete(self):
        """
        حذف امن با مدیریت روابط cascade
        """
        with transaction.atomic():
            # Override in subclasses for specific cleanup
            self.pre_safe_delete()
            
            # Perform the actual deletion
            result = self.delete()
            
            # Post-deletion cleanup
            self.post_safe_delete()
            
            return result
    
    def pre_safe_delete(self):
        """Override in subclasses for pre-deletion cleanup"""
        pass
    
    def post_safe_delete(self):
        """Override in subclasses for post-deletion cleanup"""
        pass


def cleanup_orphaned_synclogs():
    """
    پاکسازی SyncLog هایی که Chunk آنها حذف شده است.
    این تابع را می‌توان به صورت دوره‌ای اجرا کرد.
    """
    from django.db.models import Q
    
    # Find SyncLogs with no related chunk
    orphaned_logs = SyncLog.objects.filter(
        Q(chunk__isnull=True) | 
        ~Q(chunk__id__gt=0)
    )
    
    count = orphaned_logs.count()
    if count > 0:
        orphaned_logs.delete()
        logger.info(f"Cleaned up {count} orphaned SyncLog entries")
    
    return count
