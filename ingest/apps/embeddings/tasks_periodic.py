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


@shared_task(name='system.cleanup_old_logs')
def cleanup_old_logs(retention_days=30):
    """
    Periodic task to cleanup old log entries and historical records.
    Keeps only logs from the last 30 days by default.
    Runs daily to keep database clean.
    """
    from django.utils import timezone
    from datetime import timedelta
    from ingest.apps.accounts.models import LoginEvent, UserActivityLog
    from ingest.apps.documents.models import IngestLog, Chunk, LegalUnit
    from ingest.apps.embeddings.models import SyncLog, Embedding
    
    cutoff_date = timezone.now() - timedelta(days=retention_days)
    logger.info(f"🧹 Starting cleanup of logs older than {retention_days} days (before {cutoff_date.date()})")
    
    total_deleted = 0
    
    # Cleanup LoginEvent
    login_count = LoginEvent.objects.filter(timestamp__lt=cutoff_date).count()
    if login_count > 0:
        LoginEvent.objects.filter(timestamp__lt=cutoff_date).delete()
        logger.info(f"🗑️  Deleted {login_count} old login events")
        total_deleted += login_count
    
    # Cleanup UserActivityLog
    activity_count = UserActivityLog.objects.filter(timestamp__lt=cutoff_date).count()
    if activity_count > 0:
        UserActivityLog.objects.filter(timestamp__lt=cutoff_date).delete()
        logger.info(f"🗑️  Deleted {activity_count} old user activity logs")
        total_deleted += activity_count
    
    # Cleanup IngestLog
    ingest_count = IngestLog.objects.filter(created_at__lt=cutoff_date).count()
    if ingest_count > 0:
        IngestLog.objects.filter(created_at__lt=cutoff_date).delete()
        logger.info(f"🗑️  Deleted {ingest_count} old ingest logs")
        total_deleted += ingest_count
    
    # Cleanup SyncLog (only synced/verified entries older than retention period)
    sync_count = SyncLog.objects.filter(
        created_at__lt=cutoff_date,
        status__in=['synced', 'verified']
    ).count()
    if sync_count > 0:
        SyncLog.objects.filter(
            created_at__lt=cutoff_date,
            status__in=['synced', 'verified']
        ).delete()
        logger.info(f"🗑️  Deleted {sync_count} old sync logs")
        total_deleted += sync_count
    
    # Cleanup Historical records (django-simple-history)
    historical_deleted = 0
    
    # Historical Embedding
    hist_embedding_count = Embedding.history.filter(history_date__lt=cutoff_date).count()
    if hist_embedding_count > 0:
        Embedding.history.filter(history_date__lt=cutoff_date).delete()
        logger.info(f"🗑️  Deleted {hist_embedding_count} old historical embeddings")
        historical_deleted += hist_embedding_count
    
    # Historical Chunk
    hist_chunk_count = Chunk.history.filter(history_date__lt=cutoff_date).count()
    if hist_chunk_count > 0:
        Chunk.history.filter(history_date__lt=cutoff_date).delete()
        logger.info(f"🗑️  Deleted {hist_chunk_count} old historical chunks")
        historical_deleted += hist_chunk_count
    
    # Historical LegalUnit
    hist_legalunit_count = LegalUnit.history.filter(history_date__lt=cutoff_date).count()
    if hist_legalunit_count > 0:
        LegalUnit.history.filter(history_date__lt=cutoff_date).delete()
        logger.info(f"🗑️  Deleted {hist_legalunit_count} old historical legal units")
        historical_deleted += hist_legalunit_count
    
    total_deleted += historical_deleted
    
    if total_deleted == 0:
        logger.info("✅ No old logs to cleanup")
    else:
        logger.info(f"✅ Total cleaned up: {total_deleted} log entries")
    
    return {
        'login_events': login_count,
        'activity_logs': activity_count,
        'ingest_logs': ingest_count,
        'sync_logs': sync_count,
        'historical_embeddings': hist_embedding_count,
        'historical_chunks': hist_chunk_count,
        'historical_legalunits': hist_legalunit_count,
        'total_deleted': total_deleted,
        'retention_days': retention_days
    }
