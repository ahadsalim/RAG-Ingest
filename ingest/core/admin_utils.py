"""
Admin utility classes and decorators.
کلاس‌ها و decorator های کمکی برای Admin

استخراج شده از admin_optimized.py برای استفاده مجدد
"""
import time
from functools import wraps
from django.core.paginator import Paginator
from django.core.cache import cache
from django.contrib.admin.views.main import ChangeList


class CachedCountPaginator(Paginator):
    """
    Paginator که تعداد کل را cache می‌کند تا از COUNT های تکراری جلوگیری کند.
    مناسب برای جداول بزرگ که COUNT کند است.
    """
    
    @property
    def count(self):
        """Cache the count for 5 minutes"""
        # Create a stable cache key from the query
        cache_key = f"admin_paginator_count_{hash(str(self.object_list.query))}"
        count = cache.get(cache_key)
        
        if count is None:
            count = super().count
            cache.set(cache_key, count, 300)  # Cache for 5 minutes
        
        return count


class OptimizedChangeList(ChangeList):
    """
    ChangeList بهینه‌شده که از Paginator کش‌دار استفاده می‌کند.
    """
    
    def get_paginator(self, request, queryset, per_page, orphans=0, allow_empty=True):
        return CachedCountPaginator(queryset, per_page, orphans, allow_empty)


def monitor_admin_performance(func):
    """
    Decorator برای مانیتورینگ عملکرد Admin actions.
    عملیات‌های کند (بیش از 1 ثانیه) را لاگ می‌کند.
    
    Usage:
        @monitor_admin_performance
        def changelist_view(self, request, extra_context=None):
            ...
    """
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


def clear_admin_cache():
    """
    پاک کردن cache های مربوط به Admin.
    مفید برای زمانی که داده‌ها به‌روز شده و cache باید invalidate شود.
    
    Returns:
        تعداد کلیدهای حذف شده
    """
    keys_deleted = 0
    
    try:
        from django_redis import get_redis_connection
        redis_conn = get_redis_connection("default")
        
        # Find and delete admin-related cache keys
        keys = redis_conn.keys("*admin_paginator_count_*")
        if keys:
            keys_deleted = redis_conn.delete(*keys)
    except ImportError:
        # django_redis not available, skip
        pass
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to clear admin cache: {e}")
    
    return keys_deleted
