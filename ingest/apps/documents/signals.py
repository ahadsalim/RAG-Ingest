"""
Signal handlers for document models.
سیگنال‌های مدیریت حذف و به‌روزرسانی
"""

from django.db.models.signals import pre_delete, post_delete, pre_save, post_save
from django.dispatch import receiver
from django.db import transaction
import logging

logger = logging.getLogger(__name__)


# Use string reference to avoid circular import
@receiver(pre_delete, sender='documents.LegalUnit')
def handle_legalunit_pre_delete(sender, instance, **kwargs):
    """
    قبل از حذف LegalUnit، ابتدا SyncLog های مرتبط را پاکسازی می‌کنیم.
    این مشکل cascade deletion را حل می‌کند.
    """
    try:
        # Import here to avoid circular import
        from ingest.apps.embeddings.models_synclog import SyncLog
        
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


@receiver(pre_delete, sender='documents.Chunk')
def handle_chunk_pre_delete(sender, instance, **kwargs):
    """
    قبل از حذف Chunk، Embedding مرتبط را حذف می‌کنیم و درخواست حذف به Core می‌فرستیم.
    """
    try:
        from ingest.apps.embeddings.models import Embedding
        from ingest.apps.embeddings.models_synclog import SyncLog, DeletionLog
        from django.contrib.contenttypes.models import ContentType
        import requests
        
        # پیدا کردن embedding مرتبط
        chunk_ct = ContentType.objects.get_for_model(sender)
        embeddings = Embedding.objects.filter(
            content_type=chunk_ct,
            object_id=instance.id
        )
        
        for embedding in embeddings:
            # ذخیره اطلاعات برای حذف از Core
            node_id = None
            synced_to_core = embedding.synced_to_core
            
            # اگر به Core sync شده، node_id را پیدا کن
            if synced_to_core:
                sync_log = SyncLog.objects.filter(
                    chunk_id=instance.id
                ).order_by('-synced_at').first()
                
                if sync_log:
                    node_id = sync_log.node_id
            
            # ایجاد DeletionLog برای پیگیری حذف
            deletion_log = DeletionLog.objects.create(
                chunk_id=str(instance.id),
                embedding_id=str(embedding.id),
                node_id=node_id,
                deletion_status='pending' if node_id else 'local_only',
                chunk_metadata={
                    'unit_id': str(instance.unit_id) if instance.unit_id else None,
                    'expr_id': str(instance.expr_id) if instance.expr_id else None,
                    'token_count': instance.token_count,
                }
            )
            
            # اگر به Core sync شده، تلاش برای حذف از Core
            if node_id:
                try:
                    from ingest.apps.embeddings.models import CoreConfig
                    config = CoreConfig.get_config()
                    
                    if config and config.core_api_url:
                        headers = {'Content-Type': 'application/json'}
                        if config.core_api_key:
                            headers['X-API-Key'] = config.core_api_key
                        
                        url = f"{config.core_api_url}/api/v1/sync/node/{node_id}"
                        response = requests.delete(url, headers=headers, timeout=10)
                        
                        if response.status_code in [200, 204]:
                            deletion_log.deletion_status = 'success'
                            deletion_log.deleted_from_core_at = transaction.now()
                            deletion_log.save()
                            logger.info(f"Successfully deleted node {node_id} from Core")
                        else:
                            deletion_log.deletion_status = 'failed'
                            deletion_log.error_message = f"HTTP {response.status_code}: {response.text[:500]}"
                            deletion_log.retry_count = 0
                            deletion_log.save()
                            logger.warning(
                                f"Failed to delete node {node_id} from Core: "
                                f"{response.status_code}"
                            )
                
                except Exception as e:
                    deletion_log.deletion_status = 'failed'
                    deletion_log.error_message = str(e)[:500]
                    deletion_log.retry_count = 0
                    deletion_log.save()
                    logger.error(f"Error deleting node {node_id} from Core: {e}")
            
            # حذف embedding از Ingest
            embedding.delete()
            logger.info(f"Deleted embedding {embedding.id} for chunk {instance.id}")
        
        # حذف SyncLog های مرتبط
        SyncLog.objects.filter(chunk_id=instance.id).delete()
        
    except Exception as e:
        logger.error(f"Error in pre_delete handler for Chunk {instance.id}: {e}")
        # Don't prevent deletion even if cleanup fails


@receiver(post_delete, sender='documents.Chunk')
def handle_chunk_post_delete(sender, instance, **kwargs):
    """
    بعد از حذف Chunk، اطلاعات مرتبط را لاگ می‌کنیم.
    """
    logger.info(
        f"Chunk {instance.id} deleted. "
        f"Unit: {instance.unit_id}, Expression: {instance.expr_id}"
    )


@receiver(pre_delete, sender='documents.FileAsset')
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
    from ingest.apps.embeddings.models_synclog import SyncLog
    
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
