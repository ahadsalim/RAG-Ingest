"""Celery tasks for document processing."""
from celery import shared_task
from celery.utils.log import get_task_logger

from .chunking import ChunkProcessingService

logger = get_task_logger(__name__)

# Initialize the service
chunk_processor = ChunkProcessingService()


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_legal_unit_chunks(self, unit_id):
    """Celery task to process a legal unit into chunks.
    
    Args:
        unit_id: ID of the legal unit to process
        
    Returns:
        Dict containing processing results
    """
    try:
        logger.info(f"Processing chunks for legal unit: {unit_id}")
        result = chunk_processor.process_legal_unit(unit_id)
        return {
            'task': 'process_legal_unit_chunks',
            'unit_id': str(unit_id),
            'result': result
        }
    except Exception as exc:
        logger.error(f"Error processing legal unit {unit_id}: {str(exc)}", exc_info=True)
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=60 * self.request.retries)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_document_chunks(self, document_id):
    """Celery task to process a document's legal units into chunks.
    
    Args:
        document_id: ID of the document to process
        
    Returns:
        Dict containing processing results
    """
    try:
        logger.info(f"Processing chunks for document: {document_id}")
        result = chunk_processor.process_document(document_id)
        return {
            'task': 'process_document_chunks',
            'document_id': str(document_id),
            'result': result
        }
    except Exception as exc:
        logger.error(f"Error processing document {document_id}: {str(exc)}", exc_info=True)
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=60 * self.request.retries)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_qa_entry_chunks(self, qaentry_id):
    """Celery task to process a QAEntry into chunks.
    
    Args:
        qaentry_id: ID of the QAEntry to process
        
    Returns:
        Dict containing processing results
    """
    try:
        logger.info(f"Processing chunks for QAEntry: {qaentry_id}")
        result = chunk_processor.process_qaentry(qaentry_id)
        return {
            'task': 'process_qa_entry_chunks',
            'qaentry_id': str(qaentry_id),
            'result': result
        }
    except Exception as exc:
        logger.error(f"Error processing QAEntry {qaentry_id}: {str(exc)}", exc_info=True)
        raise self.retry(exc=exc, countdown=60 * self.request.retries)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_text_entry_chunks(self, textentry_id):
    """Celery task to process a TextEntry into chunks.
    
    Args:
        textentry_id: ID of the TextEntry to process
        
    Returns:
        Dict containing processing results
    """
    try:
        logger.info(f"Processing chunks for TextEntry: {textentry_id}")
        result = chunk_processor.process_textentry(textentry_id)
        return {
            'task': 'process_text_entry_chunks',
            'textentry_id': str(textentry_id),
            'result': result
        }
    except Exception as exc:
        logger.error(f"Error processing TextEntry {textentry_id}: {str(exc)}", exc_info=True)
        raise self.retry(exc=exc, countdown=60 * self.request.retries)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def batch_process_units(self, unit_ids):
    """Process multiple legal units in a batch.
    
    Args:
        unit_ids: List of legal unit IDs to process
        
    Returns:
        Dict mapping unit IDs to processing results
    """
    try:
        logger.info(f"Batch processing {len(unit_ids)} legal units")
        results = {}
        for unit_id in unit_ids:
            try:
                result = process_legal_unit_chunks(unit_id)
                results[str(unit_id)] = {
                    'success': True,
                    'result': result
                }
            except Exception as e:
                logger.error(f"Error in batch processing unit {unit_id}: {str(e)}")
                results[str(unit_id)] = {
                    'success': False,
                    'error': str(e)
                }
        
        # Check if all were successful
        all_success = all(r['success'] for r in results.values())
        if not all_success and self.request.retries < self.max_retries:
            # Retry failed units
            failed_units = [uid for uid, r in results.items() if not r['success']]
            logger.warning(f"Retrying {len(failed_units)} failed units")
            return self.retry(
                args=[failed_units],
                countdown=60 * (self.request.retries + 1)
            )
            
        return {
            'task': 'batch_process_units',
            'total_units': len(unit_ids),
            'successful': sum(1 for r in results.values() if r['success']),
            'failed': sum(1 for r in results.values() if not r['success']),
            'results': results
        }
    except Exception as exc:
        logger.error(f"Error in batch processing: {str(exc)}", exc_info=True)
        raise self.retry(exc=exc, countdown=60 * self.request.retries)
