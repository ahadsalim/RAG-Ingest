"""
Performance optimizations for the Ingest application.
بهینه‌سازی عملکرد برای برنامه Ingest
"""

from django.core.cache import cache
from django.db.models import Prefetch, Count, Q, F
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.contrib.postgres.aggregates import ArrayAgg
from functools import wraps
import hashlib
import json
from typing import Any, Optional
import time
import logging

logger = logging.getLogger(__name__)


class QueryOptimizer:
    """کلاس برای بهینه‌سازی Query های دیتابیس"""
    
    @staticmethod
    def optimize_legalunit_queryset(queryset):
        """بهینه‌سازی QuerySet برای LegalUnit با کاهش N+1 queries"""
        return queryset.select_related(
            'work',
            'work__organization',
            'expr',
            'expr__work',
            'manifestation',
            'parent',
            'parent__work'
        ).prefetch_related(
            'files',
            'children',
            'changes',
            'chunks',
            'vocabulary_terms',
            Prefetch(
                'chunks__sync_logs',
                queryset=SyncLog.objects.select_related('chunk').only(
                    'id', 'node_id', 'status', 'synced_at', 'chunk_id'
                )
            )
        ).annotate(
            chunk_count=Count('chunks'),
            file_count=Count('files'),
            child_count=Count('children')
        )
    
    @staticmethod
    def optimize_chunk_queryset(queryset):
        """بهینه‌سازی QuerySet برای Chunk"""
        return queryset.select_related(
            'expr',
            'expr__work',
            'unit',
            'unit__work',
            'qaentry'
        ).prefetch_related(
            'sync_logs',
            'embeddings'
        ).only(
            'id', 'chunk_text', 'token_count', 'hash', 'node_id',
            'expr_id', 'unit_id', 'qaentry_id', 'created_at'
        )
    
    @staticmethod
    def optimize_admin_queryset(queryset, model_name):
        """بهینه‌سازی QuerySet برای Admin Panel"""
        optimizations = {
            'LegalUnit': QueryOptimizer.optimize_legalunit_queryset,
            'Chunk': QueryOptimizer.optimize_chunk_queryset,
            'InstrumentWork': lambda qs: qs.prefetch_related(
                'expressions', 'units', 'organization'
            ).annotate(
                expression_count=Count('expressions'),
                unit_count=Count('units')
            ),
            'InstrumentExpression': lambda qs: qs.select_related(
                'work', 'work__organization'
            ).prefetch_related('chunks', 'units').annotate(
                chunk_count=Count('chunks'),
                unit_count=Count('units')
            ),
        }
        
        optimizer = optimizations.get(model_name)
        if optimizer:
            return optimizer(queryset)
        return queryset


class CacheStrategy:
    """استراتژی‌های مختلف برای Caching"""
    
    CACHE_DURATIONS = {
        'short': 60,          # 1 minute
        'medium': 300,        # 5 minutes
        'long': 3600,         # 1 hour
        'daily': 86400,       # 1 day
        'weekly': 604800,     # 1 week
    }
    
    @staticmethod
    def cache_key_generator(prefix: str, *args, **kwargs) -> str:
        """تولید کلید یکتا برای cache"""
        key_parts = [prefix]
        key_parts.extend(str(arg) for arg in args)
        key_parts.extend(f"{k}:{v}" for k, v in sorted(kwargs.items()))
        
        key_string = ":".join(key_parts)
        if len(key_string) > 200:  # Redis key limit
            # Use hash for long keys
            hash_digest = hashlib.md5(key_string.encode()).hexdigest()
            return f"{prefix}:hash:{hash_digest}"
        
        return key_string
    
    @classmethod
    def cache_result(cls, duration='medium', key_prefix=None):
        """Decorator برای cache کردن نتیجه متدها"""
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                # Generate cache key
                prefix = key_prefix or f"{func.__module__}.{func.__name__}"
                cache_key = cls.cache_key_generator(prefix, *args, **kwargs)
                
                # Try to get from cache
                result = cache.get(cache_key)
                if result is not None:
                    logger.debug(f"Cache hit for {cache_key}")
                    return result
                
                # Execute function and cache result
                result = func(*args, **kwargs)
                timeout = cls.CACHE_DURATIONS.get(duration, cls.CACHE_DURATIONS['medium'])
                cache.set(cache_key, result, timeout)
                logger.debug(f"Cached {cache_key} for {timeout} seconds")
                
                return result
            return wrapper
        return decorator
    
    @staticmethod
    def invalidate_pattern(pattern: str):
        """حذف همه cache key هایی که با pattern شروع می‌شوند"""
        # Note: این متد نیاز به Redis backend دارد
        try:
            from django_redis import get_redis_connection
            redis_conn = get_redis_connection("default")
            keys = redis_conn.keys(f"ingest:{pattern}*")
            if keys:
                redis_conn.delete(*keys)
                logger.info(f"Invalidated {len(keys)} cache keys matching pattern: {pattern}")
        except Exception as e:
            logger.error(f"Failed to invalidate cache pattern {pattern}: {e}")


class DatabaseOptimizations:
    """بهینه‌سازی‌های مربوط به دیتابیس"""
    
    @staticmethod
    def add_missing_indexes():
        """SQL برای اضافه کردن Index های مفید که ممکن است وجود نداشته باشند"""
        indexes = [
            # Index for frequent lookups
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_legalunit_work_type ON documents_legalunit(work_id, unit_type);",
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_legalunit_valid_dates ON documents_legalunit(valid_from, valid_to) WHERE valid_to IS NOT NULL;",
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_chunk_hash_expr ON documents_chunk(hash, expr_id);",
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_synclog_status_retry ON embeddings_synclog(status, retry_count) WHERE status IN ('failed', 'pending_retry');",
            
            # Composite indexes for common queries
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_chunk_unit_created ON documents_chunk(unit_id, created_at DESC);",
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_embedding_content_object ON embeddings_embedding(content_type_id, object_id);",
            
            # Partial indexes for better performance
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_legalunit_active ON documents_legalunit(work_id) WHERE valid_to IS NULL OR valid_to > CURRENT_DATE;",
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_synclog_unverified ON embeddings_synclog(synced_at) WHERE status = 'synced' AND verified_at IS NULL;",
            
            # Full text search indexes (if using PostgreSQL full text search)
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_legalunit_content_gin ON documents_legalunit USING gin(to_tsvector('simple', content));",
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_chunk_text_gin ON documents_chunk USING gin(to_tsvector('simple', chunk_text));",
        ]
        
        return indexes
    
    @staticmethod
    def optimize_database_settings():
        """تنظیمات پیشنهادی برای PostgreSQL"""
        return {
            'postgresql.conf': {
                'shared_buffers': '256MB',  # 25% of RAM
                'effective_cache_size': '1GB',  # 50-75% of RAM
                'maintenance_work_mem': '128MB',
                'work_mem': '4MB',
                'max_connections': '200',
                'random_page_cost': '1.1',  # For SSD
                'effective_io_concurrency': '200',  # For SSD
                'wal_buffers': '16MB',
                'default_statistics_target': '100',
                'checkpoint_completion_target': '0.9',
                'max_wal_size': '2GB',
                'min_wal_size': '1GB',
                
                # Query optimization
                'join_collapse_limit': '12',
                'from_collapse_limit': '12',
                
                # Parallel query execution
                'max_parallel_workers_per_gather': '2',
                'max_parallel_workers': '4',
                'parallel_setup_cost': '500',
                'parallel_tuple_cost': '0.05',
            }
        }


class PerformanceMonitor:
    """مانیتورینگ عملکرد برنامه"""
    
    @staticmethod
    def measure_query_time(func):
        """Decorator برای اندازه‌گیری زمان اجرای Query ها"""
        @wraps(func)
        def wrapper(*args, **kwargs):
            from django.db import connection
            from django.db.models import QuerySet
            
            initial_queries = len(connection.queries)
            start_time = time.time()
            
            result = func(*args, **kwargs)
            
            end_time = time.time()
            new_queries = connection.queries[initial_queries:]
            
            total_time = end_time - start_time
            query_count = len(new_queries)
            
            if query_count > 10 or total_time > 1.0:  # Log slow or complex queries
                logger.warning(
                    f"Performance issue in {func.__name__}: "
                    f"{query_count} queries in {total_time:.2f}s"
                )
                
                # Log slowest queries
                slow_queries = sorted(
                    new_queries, 
                    key=lambda q: float(q['time']), 
                    reverse=True
                )[:5]
                
                for i, query in enumerate(slow_queries, 1):
                    logger.debug(
                        f"Query {i}: {query['time']}s - {query['sql'][:200]}"
                    )
            
            return result
        return wrapper
    
    @staticmethod
    def get_performance_metrics():
        """دریافت متریک‌های عملکرد فعلی"""
        from django.db import connection
        from django.core.cache import cache
        
        metrics = {
            'database': {
                'query_count': len(connection.queries),
                'total_time': sum(float(q['time']) for q in connection.queries),
            },
            'cache': {
                'hits': cache.get('cache_hits', 0),
                'misses': cache.get('cache_misses', 0),
            }
        }
        
        # Calculate hit rate
        total_requests = metrics['cache']['hits'] + metrics['cache']['misses']
        if total_requests > 0:
            metrics['cache']['hit_rate'] = metrics['cache']['hits'] / total_requests * 100
        else:
            metrics['cache']['hit_rate'] = 0
        
        return metrics


class MemoryOptimizer:
    """بهینه‌سازی مصرف حافظه"""
    
    @staticmethod
    def chunked_queryset(queryset, chunk_size=1000):
        """پردازش QuerySet به صورت chunk برای کاهش مصرف RAM"""
        start = 0
        while True:
            chunk = queryset[start:start + chunk_size]
            if not chunk:
                break
            
            for item in chunk:
                yield item
            
            start += chunk_size
            
            # Clear query cache periodically
            if start % 5000 == 0:
                from django.db import reset_queries
                reset_queries()
    
    @staticmethod
    def optimize_serializer_fields(serializer_class, request):
        """کاهش فیلدهای غیرضروری در Serializer بر اساس درخواست"""
        requested_fields = request.query_params.get('fields')
        if requested_fields:
            requested_fields = requested_fields.split(',')
            
            class OptimizedSerializer(serializer_class):
                class Meta(serializer_class.Meta):
                    fields = requested_fields
            
            return OptimizedSerializer
        
        return serializer_class


# Export utility functions
__all__ = [
    'QueryOptimizer',
    'CacheStrategy',
    'DatabaseOptimizations',
    'PerformanceMonitor',
    'MemoryOptimizer',
]
