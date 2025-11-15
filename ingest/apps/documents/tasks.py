"""
Celery tasks for document processing and chunking.
"""
import logging
from celery import shared_task
from django.db import transaction

from .models import InstrumentExpression, LegalUnit
from .processing.chunking import get_chunk_processing_service

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def process_expression_chunks(self, expression_id: str):
    """
    Process all legal units in an expression to create chunks and embeddings.
    
    Args:
        expression_id: UUID of the InstrumentExpression to process
    """
    try:
        expression = InstrumentExpression.objects.get(id=expression_id)
        logger.info(f"Starting chunk processing for expression {expression_id}")
        
        results = get_chunk_processing_service().process_expression(expression)
        
        logger.info(f"Completed chunk processing for expression {expression_id}: {results}")
        return results
        
    except InstrumentExpression.DoesNotExist:
        logger.error(f"Expression {expression_id} not found")
        raise
    except Exception as e:
        logger.error(f"Error processing expression {expression_id}: {str(e)}")
        # Retry with exponential backoff
        raise self.retry(countdown=60 * (2 ** self.request.retries), exc=e)


@shared_task(bind=True, max_retries=3)
def process_legal_unit_chunks(self, unit_id: str):
    """
    Process a single legal unit to create chunks and embeddings.
    
    Args:
        unit_id: UUID of the LegalUnit to process
    """
    try:
        unit = LegalUnit.objects.get(id=unit_id)
        logger.info(f"Starting chunk processing for legal unit {unit_id}")
        
        results = get_chunk_processing_service().process_legal_unit(unit)
        
        logger.info(f"Completed chunk processing for legal unit {unit_id}: {results}")
        return results
        
    except LegalUnit.DoesNotExist:
        logger.error(f"Legal unit {unit_id} not found")
        raise
    except Exception as e:
        logger.error(f"Error processing legal unit {unit_id}: {str(e)}")
        # Retry with exponential backoff
        raise self.retry(countdown=60 * (2 ** self.request.retries), exc=e)


@shared_task
def cleanup_duplicate_chunks():
    """
    Cleanup task to remove duplicate chunks based on hash.
    Note: Chunk model has been removed in the simplified version.
    """
    logger.info("Chunk cleanup task called but Chunk model no longer exists")
    return {'deleted_count': 0}
