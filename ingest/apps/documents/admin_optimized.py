"""
Optimized admin configurations for better performance.
پیکربندی بهینه‌شده Admin برای عملکرد بهتر

DEPRECATED: این فایل منسوخ شده است.
کلاس‌های utility به ingest.core.admin_utils منتقل شده‌اند.
"""

import warnings
warnings.warn(
    "admin_optimized.py is deprecated. "
    "Use ingest.core.admin_utils instead.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export utility classes for backward compatibility
from ingest.core.admin_utils import (
    CachedCountPaginator,
    OptimizedChangeList,
    monitor_admin_performance,
    clear_admin_cache,
)

# Legacy imports - no longer used but kept for backward compatibility
from django.contrib import admin


class OptimizedModelAdmin(admin.ModelAdmin):
    """
    Base class برای Admin های بهینه‌شده
    
    استفاده:
        from ingest.apps.documents.admin_optimized import OptimizedModelAdmin
        
        class MyAdmin(OptimizedModelAdmin):
            pass
    """
    
    show_full_result_count = False  # Don't count all results
    list_per_page = 25  # Reduce default page size
    list_max_show_all = 100  # Limit "show all" to prevent memory issues
    
    def get_changelist(self, request, **kwargs):
        """Use optimized changelist with cached pagination"""
        return OptimizedChangeList


# کلاس‌های خاص (OptimizedLegalUnitAdmin, OptimizedChunkAdmin, OptimizedWorkAdmin)
# حذف شدند چون استفاده نمی‌شدند.
# بهینه‌سازی‌های آنها به admin.py اصلی منتقل شده‌اند.
