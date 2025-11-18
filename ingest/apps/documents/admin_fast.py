"""
Optimized Admin for LegalUnit - Fast version
نسخه بهینه‌شده Admin برای سرعت بالا
"""

from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Prefetch
from django.core.cache import cache
from simple_history.admin import SimpleHistoryAdmin
from mptt.admin import MPTTModelAdmin

from ingest.core.admin_mixins import JalaliAdminMixin as SimpleJalaliAdminMixin
from .models import LegalUnit, FileAsset
from .forms import LegalUnitForm
from .admin import (
    ActiveTodayListFilter, 
    HasExpiryListFilter,
    LegalUnitVocabularyTermInline,
    LegalUnitChangeInline
)


class OptimizedLegalUnitAdmin(SimpleJalaliAdminMixin, MPTTModelAdmin, SimpleHistoryAdmin):
    """
    نسخه بهینه‌شده Admin برای LegalUnit
    - حذف inline های سنگین در list view
    - استفاده از annotate برای chunk_count
    - کاهش تعداد فیلدهای list_display
    - Cache برای query های تکراری
    """
    
    form = LegalUnitForm
    
    # فقط فیلدهای ضروری در list view
    list_display = (
        'unit_type', 
        'get_title_short',
        'parent',
        'order_index',
        'is_active_display',
        'chunk_count_cached',
        'jalali_created_at_display'
    )
    
    list_filter = (
        'unit_type', 
        'work',
        ActiveTodayListFilter,
        'created_at'
    )
    
    search_fields = ('content', 'path_label', 'number')
    mptt_level_indent = 20
    readonly_fields = ('path_label', 'created_at', 'updated_at')
    
    # فقط inline های سبک در change view
    inlines = [LegalUnitVocabularyTermInline]
    
    # Pagination
    list_per_page = 50  # کاهش از 100 به 50
    list_max_show_all = 200
    
    # Select/Prefetch optimization
    list_select_related = ('work', 'expr', 'manifestation', 'parent')
    
    def get_queryset(self, request):
        """
        بهینه‌سازی queryset با:
        - select_related برای foreign keys
        - annotate برای count ها
        - prefetch_related فقط در change view
        """
        qs = super().get_queryset(request)
        
        # در list view فقط select_related
        if not request.resolver_match.url_name.endswith('_change'):
            qs = qs.select_related(
                'work', 
                'expr', 
                'expr__work',
                'manifestation', 
                'parent'
            ).annotate(
                chunks_count=Count('chunks')
            )
        else:
            # در change view هم prefetch_related
            qs = qs.select_related(
                'work', 
                'expr', 
                'expr__work',
                'manifestation', 
                'parent'
            ).prefetch_related(
                'vocabulary_terms',
                'chunks',
                'file_assets'
            )
        
        return qs
    
    def get_title_short(self, obj):
        """نمایش عنوان کوتاه"""
        if obj.work:
            title = obj.work.title_official
            if len(title) > 50:
                return title[:50] + '...'
            return title
        return '-'
    get_title_short.short_description = 'سند'
    get_title_short.admin_order_field = 'work__title_official'
    
    def chunk_count_cached(self, obj):
        """
        تعداد chunk ها با استفاده از annotate
        بدون query اضافی!
        """
        if hasattr(obj, 'chunks_count'):
            return obj.chunks_count
        
        # Fallback (فقط در change view)
        cache_key = f'legalunit_chunks_{obj.id}'
        count = cache.get(cache_key)
        
        if count is None:
            count = obj.chunks.count()
            cache.set(cache_key, count, 300)  # 5 minutes
        
        return count
    chunk_count_cached.short_description = 'چانک‌ها'
    chunk_count_cached.admin_order_field = 'chunks_count'
    
    def is_active_display(self, obj):
        """نمایش وضعیت فعال/غیرفعال"""
        if obj.is_active:
            return format_html('<span style="color: green;">✓</span>')
        return format_html('<span style="color: red;">✗</span>')
    is_active_display.short_description = 'فعال'
    is_active_display.admin_order_field = 'valid_from'
    
    def get_inlines(self, request, obj):
        """
        در create view: بدون inline
        در change view: inline های سبک
        """
        if obj is None:  # Create view
            return []
        
        # در change view فقط inline های ضروری
        return [LegalUnitVocabularyTermInline, LegalUnitChangeInline]
    
    def save_model(self, request, obj, form, change):
        """Auto-populate work and expr"""
        if obj.manifestation:
            obj.expr = obj.manifestation.expr
            if obj.expr:
                obj.work = obj.expr.work
        
        super().save_model(request, obj, form, change)
        
        # Clear cache
        cache_key = f'legalunit_chunks_{obj.id}'
        cache.delete(cache_key)
    
    def delete_model(self, request, obj):
        """Clear cache on delete"""
        cache_key = f'legalunit_chunks_{obj.id}'
        cache.delete(cache_key)
        super().delete_model(request, obj)
    
    fieldsets = (
        ('اطلاعات اصلی', {
            'fields': ('manifestation', 'parent', 'unit_type', 'number', 'order_index', 'content'),
        }),
        ('اعتبار زمانی', {
            'fields': ('valid_from', 'valid_to'),
        }),
        ('شناسه‌ها', {
            'fields': ('eli_fragment', 'xml_id'),
            'classes': ('collapse',),
        }),
    )
    
    def get_form(self, request, obj=None, **kwargs):
        kwargs.setdefault('exclude', []).extend([
            'id', 'created_at', 'updated_at', 'path_label', 'work', 'expr'
        ])
        return super().get_form(request, obj, **kwargs)
    
    class Media:
        js = ('admin/js/legalunit-parent-filter.js',)
        css = {
            'all': ('admin/css/legalunit-changes.css',)
        }


# برای استفاده:
# از ingest.admin import admin_site
# admin_site.unregister(LegalUnit)
# admin_site.register(LegalUnit, OptimizedLegalUnitAdmin)
