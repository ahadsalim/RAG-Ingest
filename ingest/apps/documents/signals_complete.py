"""
Complete signal handlers for automatic chunking and embedding.
Handles: LegalUnit and QAEntry creation, updates, and deletions.
"""
import logging
from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver

from .models import LegalUnit, QAEntry, Chunk
from .processing.tasks import process_legal_unit_chunks

logger = logging.getLogger(__name__)


# ============================================================================
# LEGAL UNIT SIGNALS
# ============================================================================

@receiver(pre_save, sender=LegalUnit)
def track_legal_unit_changes(sender, instance, **kwargs):
    """Track content changes in LegalUnit before save."""
    logger.info(f"📝 pre_save signal triggered for LegalUnit {instance.id} (pk={instance.pk})")
    
    if instance.pk:  # Existing instance
        try:
            old_instance = LegalUnit.objects.get(pk=instance.pk)
            # Normalize the new content first to compare with stored normalized content
            if instance.content:
                from ingest.core.text_processing import prepare_for_embedding
                normalized_new_content = prepare_for_embedding(instance.content)
            else:
                normalized_new_content = ""
            
            # Compare normalized versions
            instance._content_changed = old_instance.content != normalized_new_content
            logger.info(f"  Existing unit, content_changed={instance._content_changed}")
        except LegalUnit.DoesNotExist:
            instance._content_changed = True  # Treat as new if not found
            logger.info(f"  Unit not found in DB, treating as new")
    else:
        instance._content_changed = True  # New instance
        logger.info(f"  New unit (no pk yet)")


@receiver(post_save, sender=LegalUnit)
def process_legal_unit_on_save(sender, instance, created, **kwargs):
    """
    Process legal unit chunks when created or content changed.
    This will automatically create chunks and queue embedding generation.
    """
    # همیشه log کن تا بفهمیم signal trigger می‌شود یا نه
    logger.info(f"🔔 post_save signal triggered for LegalUnit {instance.id} (created={created})")
    
    # چک کنیم آیا Chunk دارد یا نه
    has_chunks = Chunk.objects.filter(unit_id=instance.id).exists()
    
    should_process = created or getattr(instance, '_content_changed', False) or not has_chunks
    
    if should_process:
        reason = []
        if created:
            reason.append("created")
        if getattr(instance, '_content_changed', False):
            reason.append("content_changed")
        if not has_chunks:
            reason.append("no_chunks")
        
        logger.info(f"Enqueuing chunk processing for LegalUnit {instance.id} (reasons: {', '.join(reason)})")
        process_legal_unit_chunks.delay(str(instance.id))
    else:
        logger.info(f"⚠️  Skipping chunk processing for LegalUnit {instance.id} - already has chunks and no changes")


@receiver(post_delete, sender=LegalUnit)
def delete_legal_unit_chunks(sender, instance, **kwargs):
    """Delete all chunks and embeddings when LegalUnit is deleted."""
    logger.info(f"Deleting chunks for deleted LegalUnit {instance.id}")
    # Chunks will cascade delete embeddings due to GenericRelation
    Chunk.objects.filter(unit_id=instance.id).delete()


# ============================================================================
# QA ENTRY SIGNALS
# ============================================================================

@receiver(pre_save, sender=QAEntry)
def track_qa_entry_changes(sender, instance, **kwargs):
    """Track content changes in QAEntry before save."""
    if instance.pk:  # Existing instance
        try:
            old_instance = QAEntry.objects.get(pk=instance.pk)
            # Check if question, answer, or status changed
            question_changed = old_instance.question != instance.question
            answer_changed = old_instance.answer != instance.answer
            status_changed = old_instance.status != instance.status
            
            instance._content_changed = question_changed or answer_changed
            instance._status_changed = status_changed
        except QAEntry.DoesNotExist:
            instance._content_changed = True
            instance._status_changed = True
    else:
        instance._content_changed = True
        instance._status_changed = True


@receiver(post_save, sender=QAEntry)
def process_qa_entry_on_save(sender, instance, created, **kwargs):
    """
    Process QA entry for embedding when created or updated.
    Only processes approved QA entries.
    """
    # Only process if approved
    if instance.status != 'approved':
        logger.debug(f"Skipping QA entry {instance.id} - status is {instance.status}")
        return
    
    should_process = created or getattr(instance, '_content_changed', False)
    
    if should_process:
        logger.info(f"Enqueuing embedding for QA entry {instance.id} (created={created})")
        # Import here to avoid circular imports
        from ingest.apps.embeddings.tasks import batch_generate_embeddings_for_queryset
        from django.conf import settings
        
        # Queue embedding generation for this QA entry
        batch_generate_embeddings_for_queryset.delay(
            queryset_ids=[str(instance.id)],
            model_class_name='QAEntry',
            model_name=settings.EMBEDDING_E5_MODEL_NAME,
            batch_size=1
        )


@receiver(post_delete, sender=QAEntry)
def delete_qa_entry_embeddings(sender, instance, **kwargs):
    """Delete all embeddings when QAEntry is deleted."""
    logger.info(f"Deleting embeddings for deleted QA entry {instance.id}")
    from ingest.apps.embeddings.models import Embedding
    from django.contrib.contenttypes.models import ContentType
    
    qa_ct = ContentType.objects.get_for_model(QAEntry)
    Embedding.objects.filter(
        content_type=qa_ct,
        object_id=str(instance.id)
    ).delete()


# ============================================================================
# CHUNK SIGNALS - For automatic embedding
# ============================================================================

@receiver(post_save, sender=Chunk)
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


@receiver(post_delete, sender=Chunk)
def delete_chunk_embeddings(sender, instance, **kwargs):
    """Delete embeddings and Core node when chunk is deleted."""
    logger.info(f"Deleting embeddings for deleted Chunk {instance.id}")
    from ingest.apps.embeddings.models import Embedding
    from django.contrib.contenttypes.models import ContentType
    
    # حذف نود از Core اگر node_id دارد
    if instance.node_id:
        try:
            from ingest.core.sync.node_verifier import create_deleter_from_config
            deleter = create_deleter_from_config()
            success, error = deleter.delete_node(str(instance.node_id))
            
            if success:
                logger.info(f"Successfully deleted node {instance.node_id} from Core")
            else:
                logger.error(f"Failed to delete node {instance.node_id} from Core: {error}")
        except Exception as e:
            logger.error(f"Error deleting node {instance.node_id} from Core: {e}")
    
    # حذف embeddings محلی
    chunk_ct = ContentType.objects.get_for_model(Chunk)
    Embedding.objects.filter(
        content_type=chunk_ct,
        object_id=str(instance.id)
    ).delete()
