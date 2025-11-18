"""
Optimized mixins for API views.
Mixin های بهینه‌شده برای API
"""

from django.core.cache import cache
from django.db.models import Prefetch, Count, Q, F
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_headers
from rest_framework.response import Response
from rest_framework import status
import hashlib
import json


class OptimizedQuerysetMixin:
    """
    Mixin برای بهینه‌سازی QuerySet ها
    """
    
    # Define prefetch/select related fields per model
    optimization_config = {
        'LegalUnit': {
            'select_related': ['work', 'expr', 'manifestation', 'parent'],
            'prefetch_related': ['files', 'chunks', 'vocabulary_terms'],
            'annotations': {
                'chunk_count': Count('chunks'),
                'file_count': Count('files'),
            }
        },
        'Chunk': {
            'select_related': ['unit', 'expr', 'qaentry'],
            'prefetch_related': ['sync_logs', 'embeddings'],
            'only': ['id', 'chunk_text', 'token_count', 'hash', 'node_id'],
        },
        'InstrumentWork': {
            'select_related': ['organization'],
            'prefetch_related': ['expressions', 'units'],
            'annotations': {
                'expression_count': Count('expressions'),
                'unit_count': Count('units'),
            }
        },
        'QAEntry': {
            'select_related': ['created_by', 'approved_by', 'source_work', 'source_unit'],
            'prefetch_related': ['tags'],
        }
    }
    
    def get_optimized_queryset(self):
        """
        بازگرداندن QuerySet بهینه‌شده
        """
        queryset = super().get_queryset()
        
        # Get model name
        model_name = queryset.model.__name__
        
        # Apply optimizations if configured
        if model_name in self.optimization_config:
            config = self.optimization_config[model_name]
            
            # Apply select_related
            if 'select_related' in config:
                queryset = queryset.select_related(*config['select_related'])
            
            # Apply prefetch_related
            if 'prefetch_related' in config:
                queryset = queryset.prefetch_related(*config['prefetch_related'])
            
            # Apply only() for field limiting
            if 'only' in config:
                queryset = queryset.only(*config['only'])
            
            # Apply annotations
            if 'annotations' in config:
                queryset = queryset.annotate(**config['annotations'])
        
        return queryset
    
    def get_queryset(self):
        """Override to use optimized queryset"""
        return self.get_optimized_queryset()


class CachedResponseMixin:
    """
    Mixin برای cache کردن response های API
    """
    
    cache_timeout = 300  # 5 minutes default
    cache_key_prefix = None
    vary_on_user = True
    
    def get_cache_key(self, request, *args, **kwargs):
        """Generate unique cache key for this request"""
        
        # Base key components
        key_parts = [
            self.cache_key_prefix or self.__class__.__name__,
            request.method,
            request.path,
        ]
        
        # Add user ID if varying on user
        if self.vary_on_user and request.user.is_authenticated:
            key_parts.append(f"user_{request.user.id}")
        
        # Add query parameters
        if request.GET:
            params = sorted(request.GET.items())
            param_str = '&'.join([f"{k}={v}" for k, v in params])
            key_parts.append(param_str)
        
        # Add view kwargs
        if kwargs:
            kwargs_str = json.dumps(kwargs, sort_keys=True)
            key_parts.append(kwargs_str)
        
        # Generate key
        key_string = ':'.join(key_parts)
        
        # Use hash if key is too long
        if len(key_string) > 200:
            key_hash = hashlib.md5(key_string.encode()).hexdigest()
            return f"api_cache:{key_hash}"
        
        return f"api_cache:{key_string}"
    
    def dispatch(self, request, *args, **kwargs):
        """Check cache before processing request"""
        
        # Only cache GET requests
        if request.method != 'GET':
            return super().dispatch(request, *args, **kwargs)
        
        # Generate cache key
        cache_key = self.get_cache_key(request, *args, **kwargs)
        
        # Try to get from cache
        cached_response = cache.get(cache_key)
        if cached_response is not None:
            # Add cache hit header
            response = Response(cached_response)
            response['X-Cache'] = 'HIT'
            return response
        
        # Process request normally
        response = super().dispatch(request, *args, **kwargs)
        
        # Cache successful responses
        if response.status_code == 200:
            cache.set(cache_key, response.data, self.cache_timeout)
            response['X-Cache'] = 'MISS'
        
        return response
    
    def invalidate_cache(self, request=None):
        """Invalidate cache for this view"""
        
        if request:
            # Invalidate specific request
            cache_key = self.get_cache_key(request)
            cache.delete(cache_key)
        else:
            # Invalidate all cache for this view
            pattern = f"api_cache:{self.cache_key_prefix or self.__class__.__name__}*"
            self._delete_pattern(pattern)
    
    def _delete_pattern(self, pattern):
        """Delete all keys matching pattern"""
        try:
            from django_redis import get_redis_connection
            redis_conn = get_redis_connection("default")
            keys = redis_conn.keys(pattern)
            if keys:
                redis_conn.delete(*keys)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to delete cache pattern {pattern}: {e}")


class PaginationOptimizationMixin:
    """
    Mixin برای بهینه‌سازی pagination
    """
    
    def paginate_queryset(self, queryset):
        """Override to optimize pagination queries"""
        
        # Use cursor pagination for large datasets
        if queryset.model.__name__ in ['Chunk', 'Embedding']:
            from rest_framework.pagination import CursorPagination
            
            class OptimizedCursorPagination(CursorPagination):
                page_size = 50
                ordering = '-created_at'
            
            self.pagination_class = OptimizedCursorPagination
        
        # Cache count for regular pagination
        else:
            # Generate count cache key
            count_cache_key = f"qs_count:{queryset.query}"
            count = cache.get(count_cache_key)
            
            if count is None:
                # Use approximate count for large tables
                if queryset.model.__name__ in ['LegalUnit', 'InstrumentWork']:
                    count = self._get_approximate_count(queryset)
                else:
                    count = queryset.count()
                
                # Cache for 5 minutes
                cache.set(count_cache_key, count, 300)
            
            # Monkey patch count method
            original_count = queryset.count
            queryset.count = lambda: count
        
        return super().paginate_queryset(queryset)
    
    def _get_approximate_count(self, queryset):
        """Get approximate count for large tables"""
        from django.db import connection
        
        table_name = queryset.model._meta.db_table
        
        with connection.cursor() as cursor:
            # Use PostgreSQL's estimate
            cursor.execute(
                f"SELECT reltuples::BIGINT FROM pg_class WHERE relname = %s;",
                [table_name]
            )
            result = cursor.fetchone()
            
            if result and result[0] > 0:
                return int(result[0])
        
        # Fall back to actual count
        return queryset.count()


class BulkOperationMixin:
    """
    Mixin برای عملیات bulk
    """
    
    def perform_bulk_create(self, serializer):
        """Optimized bulk create"""
        
        # Use bulk_create for better performance
        instances = []
        for item in serializer.validated_data:
            instances.append(serializer.Meta.model(**item))
        
        # Bulk create with batch size
        created = serializer.Meta.model.objects.bulk_create(
            instances,
            batch_size=100,
            ignore_conflicts=False
        )
        
        return created
    
    def perform_bulk_update(self, serializer, instances):
        """Optimized bulk update"""
        
        # Prepare bulk update
        fields_to_update = []
        for field in serializer.fields:
            if field != 'id':
                fields_to_update.append(field)
        
        # Bulk update
        updated = serializer.Meta.model.objects.bulk_update(
            instances,
            fields_to_update,
            batch_size=100
        )
        
        return updated


class EfficientSerializerMixin:
    """
    Mixin برای بهینه‌سازی Serializer
    """
    
    def get_serializer_class(self):
        """Return optimized serializer based on action"""
        
        # Use different serializers for list vs detail
        if self.action == 'list':
            # Return a lighter serializer for list views
            return self._get_list_serializer_class()
        
        return super().get_serializer_class()
    
    def _get_list_serializer_class(self):
        """Generate a lighter serializer for list views"""
        
        base_serializer = super().get_serializer_class()
        
        # Create a new serializer with fewer fields
        class ListSerializer(base_serializer):
            class Meta(base_serializer.Meta):
                # Exclude heavy fields in list view
                exclude_fields = getattr(
                    base_serializer.Meta,
                    'list_exclude_fields',
                    ['content', 'chunk_text', 'embedding']
                )
                
                if hasattr(base_serializer.Meta, 'fields'):
                    fields = [
                        f for f in base_serializer.Meta.fields
                        if f not in exclude_fields
                    ]
                else:
                    exclude = exclude_fields
        
        return ListSerializer
    
    def get_serializer(self, *args, **kwargs):
        """Optimize serializer fields based on request"""
        
        # Check if specific fields are requested
        if self.request:
            requested_fields = self.request.query_params.get('fields')
            if requested_fields:
                kwargs['fields'] = requested_fields.split(',')
        
        return super().get_serializer(*args, **kwargs)


class ThrottledViewMixin:
    """
    Mixin برای محدودیت rate
    """
    
    def get_throttles(self):
        """Dynamic throttling based on user type"""
        
        from rest_framework.throttling import UserRateThrottle, AnonRateThrottle
        
        class StrictAnonThrottle(AnonRateThrottle):
            rate = '10/hour'
        
        class NormalUserThrottle(UserRateThrottle):
            rate = '100/hour'
        
        class PremiumUserThrottle(UserRateThrottle):
            rate = '1000/hour'
        
        if self.request and self.request.user:
            if not self.request.user.is_authenticated:
                return [StrictAnonThrottle()]
            elif self.request.user.is_staff:
                return []  # No throttling for staff
            elif getattr(self.request.user, 'is_premium', False):
                return [PremiumUserThrottle()]
            else:
                return [NormalUserThrottle()]
        
        return super().get_throttles()


# Combined optimization mixin
class FullyOptimizedViewMixin(
    OptimizedQuerysetMixin,
    CachedResponseMixin,
    PaginationOptimizationMixin,
    EfficientSerializerMixin,
    ThrottledViewMixin
):
    """
    ترکیب همه بهینه‌سازی‌ها در یک Mixin
    """
    pass


# Export mixins
__all__ = [
    'OptimizedQuerysetMixin',
    'CachedResponseMixin',
    'PaginationOptimizationMixin',
    'BulkOperationMixin',
    'EfficientSerializerMixin',
    'ThrottledViewMixin',
    'FullyOptimizedViewMixin',
]
