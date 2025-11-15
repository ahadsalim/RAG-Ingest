"""
Periodic tasks for embedding management.
Run via Celery Beat for scheduled processing.
"""
import logging
from celery import shared_task
from django.contrib.contenttypes.models import ContentType
from django.conf import settings

logger = logging.getLogger(__name__)


@shared_task(name='embeddings.check_missing_embeddings')
def check_and_generate_missing_embeddings():
    """
    Periodic task to check for chunks and QA entries without embeddings.
    Runs every hour to ensure all content is embedded.
    """
    from ingest.apps.documents.models import Chunk, QAEntry
    from ingest.apps.embeddings.models import Embedding
    from .tasks import batch_generate_embeddings_for_queryset
    
    logger.info("🔍 Starting periodic check for missing embeddings...")
    
    total_queued = 0
    
    # Check chunks without embeddings
    chunk_ct = ContentType.objects.get_for_model(Chunk)
    chunks_without_embedding = Chunk.objects.exclude(
        id__in=Embedding.objects.filter(
            content_type=chunk_ct,
            model_id__contains=settings.EMBEDDING_E5_MODEL_NAME.split('/')[-1]
        ).values_list('object_id', flat=True)
    )
    
    chunk_count = chunks_without_embedding.count()
    if chunk_count > 0:
        logger.info(f"📄 Found {chunk_count} chunks without embeddings")
        chunk_ids = list(chunks_without_embedding.values_list('id', flat=True))
        
        # Process in batches
        batch_size = 100
        for i in range(0, len(chunk_ids), batch_size):
            batch = chunk_ids[i:i + batch_size]
            batch_generate_embeddings_for_queryset.delay(
                queryset_ids=batch,
                model_class_name='Chunk',
                model_name=settings.EMBEDDING_E5_MODEL_NAME,
                batch_size=50
            )
            total_queued += len(batch)
    
    # Check QA entries without embeddings
    qa_ct = ContentType.objects.get_for_model(QAEntry)
    qa_without_embedding = QAEntry.objects.filter(status='approved').exclude(
        id__in=Embedding.objects.filter(
            content_type=qa_ct,
            model_id__contains=settings.EMBEDDING_E5_MODEL_NAME.split('/')[-1]
        ).values_list('object_id', flat=True)
    )
    
    qa_count = qa_without_embedding.count()
    if qa_count > 0:
        logger.info(f"❓ Found {qa_count} QA entries without embeddings")
        qa_ids = list(qa_without_embedding.values_list('id', flat=True))
        
        # Process in batches
        for i in range(0, len(qa_ids), batch_size):
            batch = qa_ids[i:i + batch_size]
            batch_generate_embeddings_for_queryset.delay(
                queryset_ids=batch,
                model_class_name='QAEntry',
                model_name=settings.EMBEDDING_E5_MODEL_NAME,
                batch_size=50
            )
            total_queued += len(batch)
    
    if total_queued > 0:
        logger.info(f"✅ Queued {total_queued} items for embedding generation")
    else:
        logger.info("✅ All content is already embedded")
    
    return {
        'chunks_missing': chunk_count,
        'qa_missing': qa_count,
        'total_queued': total_queued
    }


@shared_task(name='embeddings.cleanup_orphaned_embeddings')
def cleanup_orphaned_embeddings():
    """
    Periodic task to remove embeddings for deleted chunks/QA entries.
    Runs daily to keep database clean.
    """
    from ingest.apps.documents.models import Chunk, QAEntry
    from ingest.apps.embeddings.models import Embedding
    
    logger.info("🧹 Starting cleanup of orphaned embeddings...")
    
    # Get all chunk IDs
    valid_chunk_ids = set(str(id) for id in Chunk.objects.values_list('id', flat=True))
    chunk_ct = ContentType.objects.get_for_model(Chunk)
    
    # Find orphaned chunk embeddings
    orphaned_chunk_embeddings = Embedding.objects.filter(
        content_type=chunk_ct
    ).exclude(object_id__in=valid_chunk_ids)
    
    orphaned_chunks_count = orphaned_chunk_embeddings.count()
    if orphaned_chunks_count > 0:
        logger.info(f"🗑️  Deleting {orphaned_chunks_count} orphaned chunk embeddings")
        orphaned_chunk_embeddings.delete()
    
    # Get all QA IDs
    valid_qa_ids = set(str(id) for id in QAEntry.objects.values_list('id', flat=True))
    qa_ct = ContentType.objects.get_for_model(QAEntry)
    
    # Find orphaned QA embeddings
    orphaned_qa_embeddings = Embedding.objects.filter(
        content_type=qa_ct
    ).exclude(object_id__in=valid_qa_ids)
    
    orphaned_qa_count = orphaned_qa_embeddings.count()
    if orphaned_qa_count > 0:
        logger.info(f"🗑️  Deleting {orphaned_qa_count} orphaned QA embeddings")
        orphaned_qa_embeddings.delete()
    
    total_cleaned = orphaned_chunks_count + orphaned_qa_count
    if total_cleaned == 0:
        logger.info("✅ No orphaned embeddings found")
    else:
        logger.info(f"✅ Cleaned up {total_cleaned} orphaned embeddings")
    
    return {
        'orphaned_chunks': orphaned_chunks_count,
        'orphaned_qa': orphaned_qa_count,
        'total_cleaned': total_cleaned
    }
