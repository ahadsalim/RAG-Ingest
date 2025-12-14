"""Base classes for document processing services."""
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, Generic

from django.conf import settings
from django.db import connection, transaction
from django.db.models import QuerySet
from prometheus_client import Counter, Gauge, Histogram

# Configure logging
logger = logging.getLogger(__name__)

# Prometheus metrics
PROCESSING_TIME = Histogram(
    'document_processing_duration_seconds',
    'Time spent processing documents',
    ['service', 'status']
)
PROCESSING_COUNTER = Counter(
    'document_processing_total',
    'Total number of documents processed',
    ['service', 'status']
)
CHUNKS_CREATED = Counter(
    'document_chunks_created_total',
    'Total number of chunks created',
    ['service']
)

T = TypeVar('T')

@dataclass
class ProcessingStats:
    """Statistics for processing operations."""
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    chunks_created: int = 0
    errors: List[Dict[str, Any]] = field(default_factory=list)
    
    @property
    def duration(self) -> float:
        """Get processing duration in seconds."""
        end = self.end_time or datetime.utcnow()
        return (end - self.start_time).total_seconds()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert stats to dictionary."""
        return {
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration_seconds': self.duration,
            'chunks_created': self.chunks_created,
            'error_count': len(self.errors)
        }

class BaseProcessingService(ABC, Generic[T]):
    """Base class for processing services with monitoring and error handling."""
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.metrics = {
            'processing_time': PROCESSING_TIME.labels(service=self.__class__.__name__),
            'processing_counter': PROCESSING_COUNTER.labels(service=self.__class__.__name__),
            'chunks_created': CHUNKS_CREATED.labels(service=self.__class__.__name__)
        }
    
    @abstractmethod
    def process(self, item_id: str, **kwargs) -> Dict[str, Any]:
        """Process a single item.
        
        Args:
            item_id: ID of the item to process
            **kwargs: Additional processing options
            
        Returns:
            Dict containing processing results and metadata
        """
        pass
    
    def process_batch(self, item_ids: List[str], **kwargs) -> Dict[str, Any]:
        """Process multiple items in a batch with monitoring.
        
        Args:
            item_ids: List of item IDs to process
            **kwargs: Additional processing options
            
        Returns:
            Dict containing batch processing results and statistics
        """
        stats = ProcessingStats()
        results = {
            'total': len(item_ids),
            'success': 0,
            'failed': 0,
            'errors': [],
            'results': {},
            'stats': stats
        }
        
        for item_id in item_ids:
            try:
                with self.metrics['processing_time'].time():
                    result = self.process(item_id, **kwargs)
                    
                results['results'][item_id] = result
                
                if result.get('success'):
                    results['success'] += 1
                    self.metrics['processing_counter'].labels(status='success').inc()
                    
                    # Update chunks created metric
                    chunks = result.get('chunks_created', 0)
                    if chunks:
                        self.metrics['chunks_created'].inc(chunks)
                        stats.chunks_created += chunks
                else:
                    self._handle_processing_error(item_id, result.get('error', 'Unknown error'), results, stats)
                    
                # Log successful processing
                self.logger.info(
                    "Successfully processed item %s: %s",
                    item_id,
                    result.get('message', 'No message')
                )
            except Exception as e:
                self._handle_processing_error(item_id, str(e), results, stats)
        
        stats.end_time = datetime.utcnow()
        results['stats'] = stats.to_dict()
        
        self.logger.info(
            "Batch processing completed: %d/%d succeeded in %.2fs",
            results['success'],
            results['total'],
            stats.duration
        )
        
        return results

    def _handle_processing_error(
        self,
        item_id: str,
        error_message: str,
        results: Dict[str, Any],
        stats: ProcessingStats,
    ) -> None:
        """Record a processing error for a single item."""
        results['failed'] += 1
        results['errors'].append({'item_id': item_id, 'error': error_message})
        stats.errors.append({'item_id': item_id, 'error': error_message})

        try:
            self.metrics['processing_counter'].labels(status='failed').inc()
        except Exception:
            # Metrics should never break processing
            pass

        self.logger.error("Failed processing item %s: %s", item_id, error_message)
