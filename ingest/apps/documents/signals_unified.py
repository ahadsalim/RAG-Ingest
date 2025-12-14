"""
Unified signal handlers for document models.
یکپارچه‌سازی تمام سیگنال‌های مدل‌های documents

این فایل ترکیب signals.py و signals_complete.py است:
- مدیریت حذف و پاکسازی (SyncLog, Embedding, Core, Files)
- Auto-chunking و auto-embedding
- تشخیص تغییرات محتوا
"""
import logging
from django.db.models.signals import pre_delete, post_delete, pre_save, post_save
from django.dispatch import receiver
from django.db import transaction

logger = logging.getLogger(__name__)


# ============================================================================
# LEGAL UNIT SIGNALS
# ============================================================================

@receiver(pre_save, sender='documents.LegalUnit')
def track_legal_unit_changes(sender, instance, **kwargs):
    """
    Track content changes in LegalUnit before save.
    ردیابی تغییرات محتوای LegalUnit قبل از ذخیره
    """
    if instance.pk:  # Existing instance
        try:
            from .models import LegalUnit
            old_instance = LegalUnit.objects.get(pk=instance.pk)
            
            # Normalize the new content to compare with stored normalized content
            if instance.content:
                from ingest.core.text_processing import prepare_for_embedding
                normalized_new_content = prepare_for_embedding(instance.content)
            else:
                normalized_new_content = ""
            
            # Compare normalized versions
            instance._content_changed = old_instance.content != normalized_new_content
            logger.debug(f"LegalUnit {instance.id}: content_changed={instance._content_changed}")
        except Exception:
            instance._content_changed = True  # Treat as new if not found
    else:
        instance._content_changed = True  # New instance


@receiver(post_save, sender='documents.LegalUnit')
def process_legal_unit_on_save(sender, instance, created, **kwargs):
    """
    Process legal unit chunks when created or content changed.
    پردازش خودکار chunk ها هنگام ایجاد یا تغییر محتوا
    """
    from .models import Chunk
    
    # Check if unit has chunks
    has_chunks = Chunk.objects.filter(unit_id=instance.id).exists()
    
    should_process = created or getattr(instance, '_content_changed', False) or not has_chunks
    
    if should_process:
        reasons = []
        if created:
            reasons.append("created")
        if getattr(instance, '_content_changed', False):
            reasons.append("content_changed")
        if not has_chunks:
            reasons.append("no_chunks")
        
        logger.info(f"Enqueuing chunk processing for LegalUnit {instance.id} ({', '.join(reasons)})")
        
        from .processing.tasks import process_legal_unit_chunks
        process_legal_unit_chunks.delay(str(instance.id))


@receiver(pre_delete, sender='documents.LegalUnit')
def handle_legalunit_pre_delete(sender, instance, **kwargs):
    """
    قبل از حذف LegalUnit:
    1. حذف SyncLog های مرتبط با chunks
    2. پاکسازی فایل‌های مرتبط
    """
    try:
        from ingest.apps.embeddings.models_synclog import SyncLog
        
        # Get all chunks related to this legal unit
        chunk_ids = list(instance.chunks.values_list('id', flat=True))
        
        if chunk_ids:
            # Delete all SyncLogs related to these chunks
            deleted_count = SyncLog.objects.filter(chunk_id__in=chunk_ids).delete()[0]
            
            if deleted_count > 0:
                logger.info(f"Deleted {deleted_count} SyncLog entries for LegalUnit {instance.id}")
        
        # Handle file cleanup
        for file_asset in instance.files.all():
            try:
                if file_asset.file:
                    file_asset.file.delete(save=False)
            except Exception as e:
                logger.error(f"Error deleting file for FileAsset {file_asset.id}: {e}")
                
    except Exception as e:
        logger.error(f"Error in pre_delete handler for LegalUnit {instance.id}: {e}")
        # Don't prevent deletion even if cleanup fails


@receiver(post_delete, sender='documents.LegalUnit')
def delete_legal_unit_chunks(sender, instance, **kwargs):
    """
    Delete all chunks when LegalUnit is deleted.
    Chunks will cascade delete embeddings due to GenericRelation.
    """
    from .models import Chunk
    
    logger.info(f"Deleting chunks for deleted LegalUnit {instance.id}")
    Chunk.objects.filter(unit_id=instance.id).delete()


# ============================================================================
# CHUNK SIGNALS
# ============================================================================

@receiver(post_save, sender='documents.Chunk')
def generate_embedding_on_chunk_created(sender, instance, created, **kwargs):
    """Generate embedding when a new chunk is created."""
    if created:
        logger.info(f"Enqueuing embedding for new Chunk {instance.id}")
        
        from ingest.apps.embeddings.tasks import batch_generate_embeddings_for_queryset
        from django.conf import settings
        
        batch_generate_embeddings_for_queryset.delay(
            queryset_ids=[str(instance.id)],
            model_class_name='Chunk',
            model_name=settings.EMBEDDING_E5_MODEL_NAME,
            batch_size=1
        )


@receiver(pre_delete, sender='documents.Chunk')
def handle_chunk_pre_delete(sender, instance, **kwargs):
    """
    قبل از حذف Chunk:
    1. ایجاد DeletionLog برای پیگیری
    2. تلاش برای حذف از Core (اگر sync شده)
    3. حذف Embedding و SyncLog محلی
    """
    try:
        from ingest.apps.embeddings.models import Embedding
        from ingest.apps.embeddings.models_synclog import SyncLog, DeletionLog
        from django.contrib.contenttypes.models import ContentType
        
        chunk_ct = ContentType.objects.get_for_model(sender)
        embeddings = Embedding.objects.filter(
            content_type=chunk_ct,
            object_id=instance.id
        )
        
        for embedding in embeddings:
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
            try:
                DeletionLog.objects.create(
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
            except Exception as e:
                logger.warning(f"Could not create DeletionLog: {e}")
            
            # حذف از Core اگر sync شده
            if node_id:
                _delete_from_core(node_id)
            
            # حذف embedding
            embedding.delete()
        
        # حذف SyncLog های مرتبط
        SyncLog.objects.filter(chunk_id=instance.id).delete()
        
    except Exception as e:
        logger.error(f"Error in pre_delete handler for Chunk {instance.id}: {e}")


@receiver(post_delete, sender='documents.Chunk')
def handle_chunk_post_delete(sender, instance, **kwargs):
    """
    بعد از حذف Chunk:
    - حذف از Core اگر node_id روی instance موجود است
    - لاگ اطلاعات حذف
    """
    # اگر Chunk مستقیماً node_id دارد (جدیدتر)، سعی کن از Core حذف کنی
    if hasattr(instance, 'node_id') and instance.node_id:
        _delete_from_core(str(instance.node_id))
    
    logger.info(f"Chunk {instance.id} deleted. Unit: {instance.unit_id}, Expr: {instance.expr_id}")


def _delete_from_core(node_id: str) -> bool:
    """
    Helper function برای حذف نود از Core.
    
    Args:
        node_id: شناسه نود در Core
        
    Returns:
        True اگر موفق، False در غیر این صورت
    """
    try:
        from ingest.core.sync.node_verifier import create_deleter_from_config
        deleter = create_deleter_from_config()
        success, error = deleter.delete_node(str(node_id))
        
        if success:
            logger.info(f"Successfully deleted node {node_id} from Core")
            return True
        else:
            logger.warning(f"Failed to delete node {node_id} from Core: {error}")
            return False
            
    except ImportError:
        # Fallback به روش قدیمی با requests
        try:
            from ingest.apps.embeddings.models import CoreConfig
            import requests
            
            config = CoreConfig.get_config()
            if config and config.core_api_url:
                headers = {'Content-Type': 'application/json'}
                if config.core_api_key:
                    headers['X-API-Key'] = config.core_api_key
                
                url = f"{config.core_api_url}/api/v1/sync/node/{node_id}"
                response = requests.delete(url, headers=headers, timeout=10)
                
                if response.status_code in [200, 204]:
                    logger.info(f"Successfully deleted node {node_id} from Core")
                    return True
                else:
                    logger.warning(f"Failed to delete node {node_id}: HTTP {response.status_code}")
                    return False
        except Exception as e:
            logger.error(f"Error deleting node {node_id} from Core: {e}")
            return False
    except Exception as e:
        logger.error(f"Error deleting node {node_id} from Core: {e}")
        return False


# ============================================================================
# QA ENTRY SIGNALS
# ============================================================================

@receiver(pre_save, sender='documents.QAEntry')
def track_qa_entry_changes(sender, instance, **kwargs):
    """Track content changes in QAEntry before save."""
    if instance.pk:
        try:
            from .models import QAEntry
            old_instance = QAEntry.objects.get(pk=instance.pk)
            
            question_changed = old_instance.question != instance.question
            answer_changed = old_instance.answer != instance.answer
            status_changed = old_instance.status != instance.status
            
            instance._content_changed = question_changed or answer_changed
            instance._status_changed = status_changed
        except Exception:
            instance._content_changed = True
            instance._status_changed = True
    else:
        instance._content_changed = True
        instance._status_changed = True


@receiver(post_save, sender='documents.QAEntry')
def process_qa_entry_on_save(sender, instance, created, **kwargs):
    """
    Process QA entry for embedding when created or updated.
    """
    should_process = created or getattr(instance, '_content_changed', False)
    
    if should_process:
        logger.info(f"Enqueuing embedding for QA entry {instance.id} (created={created})")
        
        from ingest.apps.embeddings.tasks import batch_generate_embeddings_for_queryset
        from django.conf import settings
        
        batch_generate_embeddings_for_queryset.delay(
            queryset_ids=[str(instance.id)],
            model_class_name='QAEntry',
            model_name=settings.EMBEDDING_E5_MODEL_NAME,
            batch_size=1
        )


@receiver(post_delete, sender='documents.QAEntry')
def delete_qa_entry_embeddings(sender, instance, **kwargs):
    """Delete all embeddings when QAEntry is deleted."""
    logger.info(f"Deleting embeddings for deleted QA entry {instance.id}")
    
    from ingest.apps.embeddings.models import Embedding
    from django.contrib.contenttypes.models import ContentType
    from .models import QAEntry
    
    qa_ct = ContentType.objects.get_for_model(QAEntry)
    Embedding.objects.filter(
        content_type=qa_ct,
        object_id=str(instance.id)
    ).delete()


# ============================================================================
# TEXT ENTRY SIGNALS
# ============================================================================

@receiver(post_save, sender='documents.TextEntry')
def process_text_entry_on_save(sender, instance, created, **kwargs):
    """
    Process TextEntry for embedding when created or updated.
    """
    should_process = created or getattr(instance, '_content_changed', False)
    
    if should_process:
        logger.info(f"Enqueuing embedding for TextEntry {instance.id} (created={created})")
        
        from ingest.apps.embeddings.tasks import batch_generate_embeddings_for_queryset
        from django.conf import settings
        
        batch_generate_embeddings_for_queryset.delay(
            queryset_ids=[str(instance.id)],
            model_class_name='TextEntry',
            model_name=settings.EMBEDDING_E5_MODEL_NAME,
            batch_size=1
        )


@receiver(post_delete, sender='documents.TextEntry')
def delete_text_entry_embeddings(sender, instance, **kwargs):
    """Delete all embeddings when TextEntry is deleted."""
    logger.info(f"Deleting embeddings for deleted TextEntry {instance.id}")
    
    from ingest.apps.embeddings.models import Embedding
    from django.contrib.contenttypes.models import ContentType
    from .models import TextEntry
    
    te_ct = ContentType.objects.get_for_model(TextEntry)
    Embedding.objects.filter(
        content_type=te_ct,
        object_id=str(instance.id)
    ).delete()


# ============================================================================
# FILE ASSET SIGNALS
# ============================================================================

@receiver(pre_delete, sender='documents.FileAsset')
def handle_fileasset_pre_delete(sender, instance, **kwargs):
    """
    قبل از حذف FileAsset، فایل فیزیکی را از Storage پاک می‌کنیم.
    """
    try:
        if instance.file:
            instance.file.delete(save=False)
            logger.info(f"Deleted file from storage for FileAsset {instance.id}")
    except Exception as e:
        logger.error(f"Error deleting file from storage for FileAsset {instance.id}: {e}")


# ============================================================================
# UTILITY CLASSES AND FUNCTIONS
# ============================================================================

class SafeDeletionMixin:
    """
    Mixin برای حذف امن مدل‌هایی که روابط پیچیده دارند.
    """
    
    def safe_delete(self):
        """حذف امن با مدیریت روابط cascade"""
        with transaction.atomic():
            self.pre_safe_delete()
            result = self.delete()
            self.post_safe_delete()
            return result
    
    def pre_safe_delete(self):
        """Override in subclasses for pre-deletion cleanup"""
        pass
    
    def post_safe_delete(self):
        """Override in subclasses for post-deletion cleanup"""
        pass


def cleanup_orphaned_synclogs() -> int:
    """
    پاکسازی SyncLog هایی که Chunk آنها حذف شده است.
    این تابع را می‌توان به صورت دوره‌ای اجرا کرد.
    
    Returns:
        تعداد رکوردهای حذف شده
    """
    from django.db.models import Q
    from ingest.apps.embeddings.models_synclog import SyncLog
    
    orphaned_logs = SyncLog.objects.filter(
        Q(chunk__isnull=True) | 
        ~Q(chunk__id__gt=0)
    )
    
    count = orphaned_logs.count()
    if count > 0:
        orphaned_logs.delete()
        logger.info(f"Cleaned up {count} orphaned SyncLog entries")
    
    return count
