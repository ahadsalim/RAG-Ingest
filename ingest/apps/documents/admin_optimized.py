"""
Optimized admin configurations for better performance.
پیکربندی بهینه‌شده Admin برای عملکرد بهتر
"""

from django.contrib import admin
from django.db.models import Count, Prefetch, Q
from django.utils.html import format_html
from django.contrib.admin.views.main import ChangeList
from django.core.paginator import Paginator
from django.core.cache import cache
from functools import wraps
import time

from .models import (
    LegalUnit, Chunk, InstrumentWork, 
    InstrumentExpression, InstrumentManifestation
)
from ingest.apps.embeddings.models_synclog import SyncLog


class CachedCountPaginator(Paginator):
    """
    Paginator که تعداد کل را cache می‌کند تا از COUNT های تکراری جلوگیری کند
    """
    
    @property
    def count(self):
        """Cache the count for 5 minutes"""
        cache_key = f"admin_paginator_count_{self.object_list.query}"
        count = cache.get(cache_key)
        
        if count is None:
            count = super().count
            cache.set(cache_key, count, 300)  # Cache for 5 minutes
        
        return count


class OptimizedChangeList(ChangeList):
    """
    ChangeList بهینه‌شده که از Paginator کش‌دار استفاده می‌کند
    """
    
    def get_paginator(self, request, queryset, per_page, orphans=0, allow_empty=True):
        return CachedCountPaginator(queryset, per_page, orphans, allow_empty)


class OptimizedModelAdmin(admin.ModelAdmin):
    """
    Base class برای Admin های بهینه‌شده
    """
    
    show_full_result_count = False  # Don't count all results
    list_per_page = 25  # Reduce default page size
    list_max_show_all = 100  # Limit "show all" to prevent memory issues
    
    def get_changelist(self, request, **kwargs):
        """Use optimized changelist with cached pagination"""
        return OptimizedChangeList
    
    def get_queryset(self, request):
        """Base optimized queryset - override in subclasses"""
        qs = super().get_queryset(request)
        # Only fetch needed fields for list view
        if request.resolver_match.view_name.endswith('_changelist'):
            qs = qs.only(*self.get_list_display(request))
        return qs


class OptimizedLegalUnitAdmin(OptimizedModelAdmin):
    """Admin بهینه‌شده برای LegalUnit"""
    
    # Limit fields shown in list view
    list_display = [
        'id', 'unit_type', 'number', 'get_work_title', 
        'parent', 'chunk_count_cached', 'is_active'
    ]
    
    # Use select_related for foreign keys
    list_select_related = ['work', 'expr', 'parent']
    
    # Reduce search fields
    search_fields = ['number', 'path_label']
    
    # Optimize filtering
    list_filter = ['unit_type', 'created_at']
    
    # Raw ID fields to avoid loading all options
    raw_id_fields = ['work', 'expr', 'manifestation', 'parent']
    
    # Readonly fields that don't need widgets
    readonly_fields = ['path_label', 'created_at', 'updated_at', 'chunk_count_display']
    
    # Exclude heavy fields from change form
    exclude = ['content'] if not admin.site.DEBUG else []
    
    def get_queryset(self, request):
        """Optimized queryset with annotations"""
        qs = super().get_queryset(request)
        qs = qs.select_related(
            'work', 'expr', 'manifestation', 'parent'
        ).prefetch_related(
            'chunks',
            'files',
        ).annotate(
            _chunk_count=Count('chunks', distinct=True),
            _file_count=Count('files', distinct=True),
        )
        return qs
    
    @admin.display(description='Work Title')
    def get_work_title(self, obj):
        """Display work title efficiently"""
        if obj.work:
            return obj.work.title_official[:50]
        return '-'
    
    @admin.display(description='Chunks', ordering='_chunk_count')
    def chunk_count_cached(self, obj):
        """Display chunk count with caching"""
        cache_key = f"legalunit_chunk_count_{obj.id}"
        count = cache.get(cache_key)
        
        if count is None:
            count = getattr(obj, '_chunk_count', 0)
            cache.set(cache_key, count, 300)
        
        return count
    
    @admin.display(description='Chunk Details')
    def chunk_count_display(self, obj):
        """Detailed chunk count display for detail view"""
        if obj.pk:
            synced = obj.chunks.filter(sync_logs__status='synced').count()
            total = obj.chunks.count()
            return format_html(
                '<span style="color: {};">{} / {} synced</span>',
                'green' if synced == total else 'orange',
                synced,
                total
            )
        return '-'
    
    # Optimize form loading
    def get_form(self, request, obj=None, change=False, **kwargs):
        form = super().get_form(request, obj, change, **kwargs)
        # Use queryset optimization for foreign key fields
        if 'parent' in form.base_fields:
            form.base_fields['parent'].queryset = LegalUnit.objects.only(
                'id', 'path_label', 'unit_type', 'number'
            )
        return form
    
    # Batch actions optimization
    def delete_queryset(self, request, queryset):
        """Optimized bulk delete"""
        # First clean up related SyncLogs
        chunk_ids = list(
            Chunk.objects.filter(
                unit__in=queryset
            ).values_list('id', flat=True)
        )
        
        if chunk_ids:
            SyncLog.objects.filter(chunk_id__in=chunk_ids).delete()
        
        # Then perform normal deletion
        super().delete_queryset(request, queryset)


class OptimizedChunkAdmin(OptimizedModelAdmin):
    """Admin بهینه‌شده برای Chunk"""
    
    list_display = ['id', 'get_unit_display', 'token_count', 'sync_status_cached']
    list_select_related = ['unit', 'expr', 'qaentry']
    search_fields = []  # Disable text search on large text fields
    list_filter = ['created_at']
    raw_id_fields = ['unit', 'expr', 'qaentry']
    
    # Make it mostly read-only
    readonly_fields = [
        'chunk_text', 'token_count', 'hash', 'node_id',
        'citation_payload_json', 'created_at', 'updated_at'
    ]
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.select_related(
            'unit', 'expr', 'qaentry'
        ).prefetch_related(
            Prefetch(
                'sync_logs',
                queryset=SyncLog.objects.only('status', 'synced_at')
            )
        )
        return qs
    
    @admin.display(description='Unit')
    def get_unit_display(self, obj):
        """Display unit info efficiently"""
        if obj.unit:
            return f"{obj.unit.unit_type} {obj.unit.number}"[:30]
        elif obj.qaentry:
            return f"QA: {obj.qaentry.id}"
        return '-'
    
    @admin.display(description='Sync Status')
    def sync_status_cached(self, obj):
        """Display sync status with caching"""
        cache_key = f"chunk_sync_status_{obj.id}"
        status = cache.get(cache_key)
        
        if status is None:
            sync_log = obj.sync_logs.first()
            status = sync_log.status if sync_log else 'not_synced'
            cache.set(cache_key, status, 180)
        
        colors = {
            'synced': 'green',
            'verified': 'blue',
            'failed': 'red',
            'pending': 'orange',
            'not_synced': 'gray'
        }
        
        return format_html(
            '<span style="color: {};">{}</span>',
            colors.get(status, 'black'),
            status
        )
    
    def has_add_permission(self, request):
        """Chunks are auto-generated, prevent manual addition"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Allow deletion but with warning"""
        return request.user.is_superuser


class OptimizedWorkAdmin(OptimizedModelAdmin):
    """Admin بهینه‌شده برای InstrumentWork"""
    
    list_display = [
        'id', 'title_official', 'work_type', 
        'expression_count', 'unit_count'
    ]
    list_select_related = ['organization']
    search_fields = ['title_official', 'title_unofficial']
    list_filter = ['work_type', 'created_at']
    raw_id_fields = ['organization']
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.select_related('organization').annotate(
            _expr_count=Count('expressions', distinct=True),
            _unit_count=Count('units', distinct=True)
        )
        return qs
    
    @admin.display(description='Expressions', ordering='_expr_count')
    def expression_count(self, obj):
        return getattr(obj, '_expr_count', 0)
    
    @admin.display(description='Units', ordering='_unit_count')
    def unit_count(self, obj):
        return getattr(obj, '_unit_count', 0)


# Performance monitoring decorator
def monitor_admin_performance(func):
    """Decorator برای مانیتورینگ عملکرد Admin actions"""
    @wraps(func)
    def wrapper(self, request, *args, **kwargs):
        start_time = time.time()
        result = func(self, request, *args, **kwargs)
        duration = time.time() - start_time
        
        if duration > 1.0:  # Log slow admin operations
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(
                f"Slow admin operation: {func.__name__} took {duration:.2f}s "
                f"for {self.__class__.__name__}"
            )
        
        return result
    return wrapper


# Utility function to clear admin caches
def clear_admin_cache():
    """پاک کردن cache های مربوط به Admin"""
    cache_pattern = "admin_*"
    keys_deleted = 0
    
    try:
        from django_redis import get_redis_connection
        redis_conn = get_redis_connection("default")
        keys = redis_conn.keys(f"ingest:{cache_pattern}")
        if keys:
            keys_deleted = redis_conn.delete(*keys)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to clear admin cache: {e}")
    
    return keys_deleted
