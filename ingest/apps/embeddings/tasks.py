import numpy as np
import logging
from celery import shared_task
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from typing import List, Dict, Any, Optional, Union
from django.db.models import Model
from django.db import transaction

from .models import Embedding
from ingest.apps.documents.models import LegalUnit, Chunk, QAEntry

logger = logging.getLogger(__name__)


def get_text_content(content_object: Model) -> str:
    """Extract text content from different types of content objects."""
    if isinstance(content_object, LegalUnit):
        return f"{content_object.path_label or ''} {content_object.content or ''}"
    elif isinstance(content_object, Chunk):
        return content_object.chunk_text or ""
    elif isinstance(content_object, QAEntry):
        return f"{content_object.question or ''} {content_object.answer or ''}"
    return str(content_object)


@shared_task(bind=True)
def batch_generate_embeddings_for_queryset(self, queryset_ids: List[str], model_class_name: str, model_name: str = "intfloat/multilingual-e5-large", batch_size: int = 10) -> Dict[str, Any]:
    """
    Generate embeddings for a queryset of objects in batches.
    Returns a dictionary with statistics about the operation.
    """
    import time
    from datetime import datetime
    from sentence_transformers import SentenceTransformer
    
    # Start timing
    start_time = time.time()
    start_datetime = datetime.now()
    
    logger.info(
        "Embedding task started: task_id=%s model=%s class=%s items=%s batch_size=%s",
        getattr(self.request, 'id', None),
        model_name,
        model_class_name,
        len(queryset_ids),
        batch_size,
    )
    
    # Get the model class
    try:
        if model_class_name == 'Chunk':
            model_class = Chunk
        elif model_class_name == 'QAEntry':
            model_class = QAEntry
        else:
            raise ValueError(f"Unsupported model class: {model_class_name}")
    except Exception as e:
        return {
            'success': False,
            'error': f"Failed to get model class: {str(e)}",
            'processed': 0,
            'created': 0,
            'updated': 0,
            'errors': 0
        }
    
    # Use the model name directly with cache folder
    # SentenceTransformer will use the cached models in /app/models/
    try:
        model = SentenceTransformer(model_name, cache_folder='/app/models')
    except Exception as e:
        return {
            'success': False,
            'error': f"Failed to load model {model_name}: {str(e)}",
            'processed': 0,
            'created': 0,
            'updated': 0,
            'errors': 0
        }
    
    
    # Get queryset from IDs
    queryset = model_class.objects.filter(id__in=queryset_ids)
    content_type = ContentType.objects.get_for_model(model_class)
    total = queryset.count()
    processed = 0
    created = 0
    updated = 0
    errors = 0
    
    for i in range(0, total, batch_size):
        batch = list(queryset[i:i + batch_size])
        texts = [get_text_content(obj) for obj in batch]
        
        try:
            # Generate embeddings in one batch
            vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
            
            with transaction.atomic():
                for obj, text, vector in zip(batch, texts, vectors):
                    try:
                        embedding, created_flag = Embedding.objects.update_or_create(
                            content_type=content_type,
                            object_id=obj.id,
                            model_id=model_name,
                            defaults={
                                'vector': vector.tolist(),
                                'text_content': text,
                                'dim': len(vector),
                            }
                        )
                        
                        if created_flag:
                            created += 1
                        else:
                            updated += 1
                            
                    except Exception as e:
                        errors += 1
                        logger.exception("Error processing %s %s", content_type, obj.id)
                    
                    processed += 1
                    
        except Exception as e:
            errors += len(batch)
            logger.exception("Batch error")
            continue
    
    # End timing and logging
    end_time = time.time()
    end_datetime = datetime.now()
    total_duration = end_time - start_time
    
    logger.info(
        "Embedding task completed: task_id=%s end_time=%s duration=%.2fs processed=%s/%s created=%s updated=%s errors=%s",
        getattr(self.request, 'id', None),
        end_datetime.strftime('%Y-%m-%d %H:%M:%S'),
        total_duration,
        processed,
        total,
        created,
        updated,
        errors,
    )
    logger.debug(
        "Average per Item: %.3f seconds",
        total_duration/processed if processed > 0 else 0,
    )
    logger.debug(
        "Items per Second: %.2f",
        processed/total_duration if total_duration > 0 else 0
    )
    
    return {
        'success': True,
        'processed': processed,
        'created': created,
        'updated': updated,
        'errors': errors,
        'duration': total_duration,
        'avg_per_item': total_duration/processed if processed > 0 else 0,
        'items_per_second': processed/total_duration if total_duration > 0 else 0
    }


def generate_stub_embedding(text: str) -> list:
    """
    Stub embedding generator that creates zero vectors.
    Replace this with actual embedding model when ready.
    """
    # For now, return zero vector of configured dimension
    dimension = settings.EMBEDDING_DIMENSION
    return [0.0] * dimension


def generate_real_embedding(text: str, model_name: str = "intfloat/multilingual-e5-large") -> list:
    """
    Real embedding generator using multilingual-e5-large model.
    """
    try:
        from sentence_transformers import SentenceTransformer
        import os
        
        cache_dir = '/app/models'
        os.makedirs(cache_dir, exist_ok=True)
        local_snapshot = os.path.join(cache_dir, model_name.replace('/', '__'))
        if os.path.isdir(local_snapshot):
            model_path = local_snapshot
            cache_folder = None
        else:
            model_path = model_name
            cache_folder = cache_dir
        
        # Load the model
        model = SentenceTransformer(model_path, cache_folder=cache_folder)
        
        # Generate embedding
        embedding = model.encode(text, normalize_embeddings=True)
        return embedding.tolist()
        
    except Exception as e:
        # Fallback to stub if model loading fails
        logger.exception("Error loading embedding model %s", model_name)
        return generate_stub_embedding(text)


def generate_single_embedding(text: str, model_name: str = None) -> Dict[str, Any]:
    """
    Generate embedding for a single text (for testing purposes).
    This is a synchronous function for immediate results.
    """
    try:
        from sentence_transformers import SentenceTransformer
        import time
        import os
        
        start_time = time.time()
        
        # Use default model if none specified
        if not model_name:
            model_name = "intfloat/multilingual-e5-large"
        
        cache_dir = '/app/models'
        os.makedirs(cache_dir, exist_ok=True)
        local_snapshot = os.path.join(cache_dir, model_name.replace('/', '__'))
        if os.path.isdir(local_snapshot):
            model_path = local_snapshot
            cache_folder = None
        else:
            model_path = model_name
            cache_folder = cache_dir
        
        # Load the model
        model = SentenceTransformer(model_path, cache_folder=cache_folder)
        
        # Generate embedding
        embedding = model.encode(text, normalize_embeddings=True)
        
        end_time = time.time()
        duration = end_time - start_time
        
        return {
            'embedding': embedding.tolist(),
            'model_name': model_name,
            'text_length': len(text),
            'duration': duration,
            'dimension': len(embedding),
            'success': True
        }
        
    except Exception as e:
        return {
            'embedding': None,
            'error': str(e),
            'success': False
        }


@shared_task
def generate_embeddings_for_new_content(model_name: str = "intfloat/multilingual-e5-large", batch_size: int = 50) -> Dict[str, Any]:
    """
    Task to generate embeddings for all content that doesn't have them yet.
    This is the main task that should be called on a schedule.
    """
    results = {}
    
    # 1. Process Chunks
    chunk_ct = ContentType.objects.get_for_model(Chunk)
    chunks_to_process = Chunk.objects.exclude(
        id__in=Embedding.objects.filter(
            content_type=chunk_ct,
            model_id=model_name,
        ).values_list('object_id', flat=True)
    )
    
    if chunks_to_process.exists():
        queryset_ids = list(chunks_to_process.values_list('id', flat=True))
        async_result = batch_generate_embeddings_for_queryset.delay(
            [str(i) for i in queryset_ids],
            'Chunk',
            model_name,
            batch_size,
        )
        results['chunks'] = {'enqueued': True, 'task_id': async_result.id, 'count': len(queryset_ids)}
    else:
        results['chunks'] = {'message': 'No chunks need processing'}
    
    # 2. Process QA Entries (only approved ones)
    qa_ct = ContentType.objects.get_for_model(QAEntry)
    qa_entries_to_process = QAEntry.objects.filter(
        status='approved'
    ).exclude(
        id__in=Embedding.objects.filter(
            content_type=qa_ct,
            model_id=model_name,
        ).values_list('object_id', flat=True)
    )
    
    if qa_entries_to_process.exists():
        queryset_ids = list(qa_entries_to_process.values_list('id', flat=True))
        async_result = batch_generate_embeddings_for_queryset.delay(
            [str(i) for i in queryset_ids],
            'QAEntry',
            model_name,
            batch_size,
        )
        results['qa_entries'] = {'enqueued': True, 'task_id': async_result.id, 'count': len(queryset_ids)}
    else:
        results['qa_entries'] = {'message': 'No QA entries need processing'}
    
    return results


# ==================== Core Sync Tasks ====================

@shared_task(bind=True, max_retries=3)
def auto_sync_new_embeddings(self, batch_size=None):
    """
    Sync embeddings جدید به Core.
    این task باید هر 5 دقیقه اجرا شود.
    """
    try:
        from ingest.core.sync.sync_service import CoreSyncService
        
        service = CoreSyncService()
        result = service.sync_new_embeddings(batch_size=batch_size)
        
        logger.info(f"Auto sync result: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Error in auto_sync_new_embeddings: {e}", exc_info=True)
        raise self.retry(countdown=60 * 5, exc=e)


@shared_task(bind=True, max_retries=3)
def sync_changed_metadata(self, batch_size=None):
    """
    Sync embeddings که metadata آنها تغییر کرده است.
    این task باید هر 15 دقیقه اجرا شود.
    """
    try:
        from ingest.core.sync.sync_service import CoreSyncService
        
        service = CoreSyncService()
        result = service.sync_changed_metadata(batch_size=batch_size)
        
        logger.info(f"Metadata sync result: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Error in sync_changed_metadata: {e}", exc_info=True)
        raise self.retry(countdown=60 * 15, exc=e)


@shared_task(bind=True)
def full_sync_all_embeddings(self):
    """
    Sync تمام embeddings به Core (برای اولین بار یا reset).
    این task باید manually اجرا شود.
    """
    try:
        from ingest.core.sync.sync_service import CoreSyncService
        
        service = CoreSyncService()
        result = service.sync_all_embeddings()
        
        logger.info(f"Full sync result: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Error in full_sync_all_embeddings: {e}", exc_info=True)
        return {'status': 'error', 'error': str(e)}


@shared_task(bind=True, max_retries=3)
def cleanup_orphaned_nodes(self, batch_size=100):
    """
    پاک‌سازی نودهای orphan در Core.
    نودهایی که در Ingest حذف شده‌اند اما در Core هنوز هستند.
    این task باید هر روز یکبار اجرا شود.
    """
    try:
        from ingest.apps.embeddings.models_synclog import SyncLog
        from ingest.apps.documents.models import Chunk
        from ingest.core.sync.node_verifier import create_deleter_from_config
        
        # پیدا کردن SyncLog هایی که Chunk آنها حذف شده
        orphaned_logs = SyncLog.objects.filter(
            chunk__isnull=True
        )[:batch_size]
        
        if not orphaned_logs.exists():
            logger.info("No orphaned nodes found")
            return {'status': 'success', 'deleted': 0}
        
        deleter = create_deleter_from_config()
        deleted_count = 0
        error_count = 0
        
        for sync_log in orphaned_logs:
            try:
                success, error = deleter.delete_node(str(sync_log.node_id))
                
                if success:
                    deleted_count += 1
                    # حذف SyncLog
                    sync_log.delete()
                else:
                    error_count += 1
                    logger.error(f"Failed to delete orphaned node {sync_log.node_id}: {error}")
                    
            except Exception as e:
                error_count += 1
                logger.error(f"Error processing orphaned node {sync_log.node_id}: {e}")
        
        result = {
            'status': 'success',
            'deleted': deleted_count,
            'errors': error_count
        }
        
        logger.info(f"Cleanup orphaned nodes result: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Error in cleanup_orphaned_nodes: {e}", exc_info=True)
        raise self.retry(countdown=60 * 60, exc=e)  # Retry after 1 hour
