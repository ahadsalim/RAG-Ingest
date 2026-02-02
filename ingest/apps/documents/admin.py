""" 
╔══════════════════════════════════════════════════════════════════════════════╗
║  توجه: برای مدیریت بندهای حقوقی (LegalUnit) از LUnit استفاده کنید!          ║
║  LUnit یک proxy model برای LegalUnit است با رابط کاربری بهتر.               ║
║  فایل مربوطه: admin_lunit.py                                                 ║
║  URL در admin: /admin/documents/lunit/                                       ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.contrib.auth.models import User
from django.contrib.contenttypes.admin import GenericTabularInline
from django import forms
from django.utils.timezone import localdate
from django.contrib import messages
from django.db import models
from simple_history.admin import SimpleHistoryAdmin
from mptt.admin import MPTTModelAdmin
from ingest.core.admin_mixins import JalaliAdminMixin as SimpleJalaliAdminMixin

from .models import (
    InstrumentWork, InstrumentExpression, InstrumentManifestation,
    LegalUnit, LUnit, LegalUnitChange, LegalUnitVocabularyTerm, InstrumentRelation, PinpointCitation,
    FileAsset, Chunk, IngestLog, QAEntry, TextEntry, 
    TextEntryVocabularyTerm, TextEntryRelatedUnit,
    QAEntryVocabularyTerm, QAEntryRelatedUnit
)
from .forms import (
    InstrumentExpressionForm, InstrumentManifestationForm, InstrumentRelationForm, LegalUnitForm, FileAssetForm,
    TextEntryForm
)
from .enums import QAStatus
from ingest.admin import admin_site
from ingest.apps.embeddings.models import Embedding


class EmbeddingInline(GenericTabularInline):
    model = Embedding
    extra = 0
    readonly_fields = ("vector_preview", "dimension", "created_at")
    fields = ("vector_preview", "model_name", "dimension", "created_at")

    def vector_preview(self, obj):
        if obj.vector and len(obj.vector) > 0:
            preview = str(obj.vector[:3])[1:-1]  # Remove brackets
            return f"[{preview}...]"
        return "Empty"
    vector_preview.short_description = "Vector Preview"


# Simple FileAsset Admin
class FileAssetAdmin(SimpleJalaliAdminMixin, SimpleHistoryAdmin):
    list_display = ('filename', 'file_link', 'description', 'formatted_size', 'uploaded_by', 'jalali_created_at_display')
    list_filter = ('uploaded_by', 'created_at')
    search_fields = ('file', 'description')
    readonly_fields = ('id', 'filename', 'file_size', 'formatted_size', 'file_link', 'created_at', 'updated_at')
    actions = ['delete_selected']
    
    fieldsets = (
        ('فایل', {
            'fields': ('file', 'file_link', 'manifestation', 'description')
        }),
    )
    
    def file_link(self, obj):
        """نمایش لینک دانلود فایل"""
        if obj and obj.file:
            return format_html(
                '<a href="{}" target="_blank">دانلود فایل</a>',
                obj.file.url
            )
        return '-'
    file_link.short_description = 'لینک دانلود'
    
    def uploaded_by_display(self, obj):
        """نمایش آپلودکننده یا کاربر جاری برای فایل جدید"""
        if obj and obj.uploaded_by:
            return obj.uploaded_by.username
        elif hasattr(self, '_current_request'):
            return f"{self._current_request.user.username} (کاربر جاری)"
        return "کاربر جاری"
    uploaded_by_display.short_description = "آپلودکننده"
    
    def get_form(self, request, obj=None, **kwargs):
        # ذخیره request برای استفاده در uploaded_by_display
        self._current_request = request
        form = super().get_form(request, obj, **kwargs)
        # بزرگ کردن فیلد توضیحات
        if 'description' in form.base_fields:
            form.base_fields['description'].widget = forms.Textarea(attrs={'rows': 4, 'cols': 60})
        return form
    
    def save_model(self, request, obj, form, change):
        # همیشه کاربر جاری را به عنوان آپلودکننده تنظیم کن (فقط در ایجاد جدید)
        if not change:  # فقط هنگام ایجاد فایل جدید
            obj.uploaded_by = request.user
        super().save_model(request, obj, form, change)


class FileAssetInline(admin.TabularInline):
    model = FileAsset
    extra = 1
    readonly_fields = ('filename', 'file_size', 'formatted_size', 'uploaded_by', 'created_at')
    fields = ('file', 'description')
    
    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for instance in instances:
            if not instance.pk:  # Only on create
                instance.uploaded_by = request.user
            instance.save()
        formset.save_m2m()


class LegalUnitVocabularyTermInline(admin.TabularInline):
    model = LegalUnitVocabularyTerm
    extra = 1
    fields = ('vocabulary_term', 'weight', 'jalali_created_at', 'jalali_updated_at')
    readonly_fields = ('jalali_created_at', 'jalali_updated_at')
    
    def jalali_created_at(self, obj):
        """نمایش تاریخ ایجاد به شمسی (با تایم‌زون تهران)"""
        if obj and obj.created_at:
            from ingest.core.jalali import to_jalali_datetime
            return to_jalali_datetime(obj.created_at)
        return '-'
    jalali_created_at.short_description = 'تاریخ ایجاد'
    
    def jalali_updated_at(self, obj):
        """نمایش تاریخ به‌روزرسانی به شمسی (با تایم‌زون تهران)"""
        if obj and obj.updated_at:
            from ingest.core.jalali import to_jalali_datetime
            return to_jalali_datetime(obj.updated_at)
        return '-'
    jalali_updated_at.short_description = 'تاریخ به‌روزرسانی'
    
    class Media:
        css = {
            'all': ('admin/css/custom-inline.css',)
        }


class LegalUnitChangeInline(admin.StackedInline):
    """Inline for managing changes to a legal unit with enhanced UI."""
    model = LegalUnitChange
    fk_name = "unit"  # disambiguate; changes belong to this unit
    extra = 1
    readonly_fields = ('created_at', 'updated_at')
    
    def get_formset(self, request, obj=None, **kwargs):
        """Use custom form with Jalali date support."""
        from .forms import LegalUnitChangeForm
        kwargs['form'] = LegalUnitChangeForm
        return super().get_formset(request, obj, **kwargs)
    
    fieldsets = (
        ('اطلاعات تغییر', {
            'fields': ('change_type', 'effective_date', 'source_expression', 'superseded_by', 'note'),
            'classes': ('collapse',),
        }),
    )
    
    def has_add_permission(self, request, obj=None):
        return True  # Allow adding changes directly
    
    class Media:
        js = ('admin/js/legalunit-changes.js',)
        css = {
            'all': ('admin/css/legalunit-changes.css',)
        }


class ActiveTodayListFilter(admin.SimpleListFilter):
    """Custom filter to show units active today."""
    title = 'وضعیت فعلی'
    parameter_name = 'active_today'

    def lookups(self, request, model_admin):
        return (
            ('yes', 'فعال امروز'),
            ('no', 'غیرفعال امروز'),
            ('expired', 'منقضی شده'),
            ('future', 'آینده'),
        )

    def queryset(self, request, queryset):
        today = localdate()
        if self.value() == 'yes':
            return queryset.filter(
                models.Q(valid_from__isnull=True) | models.Q(valid_from__lte=today),
                models.Q(valid_to__isnull=True) | models.Q(valid_to__gte=today),
            )
        elif self.value() == 'no':
            return queryset.exclude(
                models.Q(valid_from__isnull=True) | models.Q(valid_from__lte=today),
                models.Q(valid_to__isnull=True) | models.Q(valid_to__gte=today),
            )
        elif self.value() == 'expired':
            return queryset.filter(valid_to__lt=today)
        elif self.value() == 'future':
            return queryset.filter(valid_from__gt=today)
        return queryset


class HasExpiryListFilter(admin.SimpleListFilter):
    """Custom filter to show units with/without expiry dates."""
    title = 'تاریخ انقضا'
    parameter_name = 'has_expiry'

    def lookups(self, request, model_admin):
        return (
            ('yes', 'دارای تاریخ انقضا'),
            ('no', 'بدون تاریخ انقضا'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.filter(valid_to__isnull=False)
        elif self.value() == 'no':
            return queryset.filter(valid_to__isnull=True)
        return queryset


class InstrumentWorkAdmin(SimpleJalaliAdminMixin, SimpleHistoryAdmin):
    list_display = ('title_official', 'doc_type', 'jurisdiction', 'authority', 'jalali_created_at_display')
    list_filter = ('doc_type', 'jurisdiction', 'authority', 'created_at')
    search_fields = ('title_official', 'urn_lex', 'subject_summary')
    readonly_fields = ('id', 'created_at', 'updated_at')
    
    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related(
            'jurisdiction', 'authority', 'primary_language'
        )
    
    fieldsets = (
        ('اطلاعات اصلی', {
            'fields': ('title_official', 'doc_type', 'jurisdiction', 'authority')
        }),
        ('شناسه‌ها', {
            'fields': ('urn_lex',),
            'classes': ('collapse',)
        }),
        ('محتوا', {
            'fields': ('primary_language', 'subject_summary')
        }),
    )


class InstrumentExpressionAdmin(SimpleJalaliAdminMixin, SimpleHistoryAdmin):
    form = InstrumentExpressionForm
    list_display = ('work', 'language', 'consolidation_level', 'expression_date', 'jalali_created_at_display')
    list_filter = ('consolidation_level', 'language', 'created_at')
    search_fields = ('work__title_official', 'eli_uri_expr')
    readonly_fields = ('id', 'created_at', 'updated_at')
    
    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related(
            'work', 'work__jurisdiction', 'work__authority', 'language'
        )
    
    fieldsets = (
        ('مرجع سند', {
            'fields': ('work',)
        }),
        ('اطلاعات نسخه', {
            'fields': ('language', 'consolidation_level', 'expression_date')
        }),
        ('شناسه‌ها', {
            'fields': ('eli_uri_expr',),
            'classes': ('collapse',)
        }),
    )
    
    def get_form(self, request, obj=None, **kwargs):
        # Exclude non-editable fields
        kwargs.setdefault('exclude', []).extend(['id', 'created_at', 'updated_at'])
        return super().get_form(request, obj, **kwargs)


class InstrumentManifestationAdmin(SimpleJalaliAdminMixin, SimpleHistoryAdmin):
    form = InstrumentManifestationForm
    list_display = ('expr', 'publication_date', 'repeal_status', 'jalali_created_at_display')
    list_filter = ('repeal_status', 'publication_date', 'created_at')
    search_fields = ('expr__work__title_official', 'official_gazette_name', 'source_url')
    readonly_fields = ('id', 'checksum_sha256', 'retrieval_date', 'created_at', 'updated_at')
    inlines = [FileAssetInline]
    
    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related(
            'expr', 'expr__work', 'expr__work__jurisdiction', 'expr__language'
        )
    
    fieldsets = (
        ('مرجع نسخه', {
            'fields': ('expr',)
        }),
        ('اطلاعات انتشار', {
            'fields': ('publication_date', 'official_gazette_name', 'gazette_issue_no', 'page_start')
        }),
        ('منابع و شناسه‌ها', {
            'fields': ('source_url', 'checksum_sha256'),
            'classes': ('collapse',),
            'description': 'چکسام SHA256 خودکار بر اساس اطلاعات فرم تولید می‌شود'
        }),
        ('وضعیت اجرا', {
            'fields': ('repeal_status', 'in_force_from', 'in_force_to')
        }),
    )
    
    def get_form(self, request, obj=None, **kwargs):
        # Exclude non-editable fields
        kwargs.setdefault('exclude', []).extend(['id', 'created_at', 'updated_at', 'checksum_sha256'])
        return super().get_form(request, obj, **kwargs)
    
    def save_formset(self, request, form, formset, change):
        """Handle FileAsset inline formset to set uploaded_by."""
        if formset.model == FileAsset:
            instances = formset.save(commit=False)
            for instance in instances:
                if not instance.pk:  # Only on create
                    instance.uploaded_by = request.user
                instance.save()
            formset.save_m2m()
        else:
            super().save_formset(request, form, formset, change)


class LegalUnitAdmin(SimpleJalaliAdminMixin, MPTTModelAdmin, SimpleHistoryAdmin):
    """Admin for LegalUnit with MPTT support and Jalali dates."""
    form = LegalUnitForm
    # اولین فیلد باید با indent نمایش داده شود برای tree view
    list_display = ('indented_title', 'unit_type', 'order_index', 'is_active_display', 'jalali_valid_from_display', 'jalali_valid_to_display', 'chunk_count', 'jalali_created_at_display')
    list_filter = ('unit_type', ActiveTodayListFilter, HasExpiryListFilter, 'created_at')
    search_fields = ('content', 'path_label', 'eli_fragment', 'xml_id')
    mptt_level_indent = 20
    readonly_fields = ('path_label', 'created_at', 'updated_at')
    # inlines به صورت dynamic load می‌شوند (get_inlines)
    actions = ['mark_as_repealed', 'mark_as_active']
    list_per_page = 100
    
    # MPTT settings برای نمایش درختی
    mptt_indent_field = "indented_title"
    
    def get_inlines(self, request, obj):
        """Lazy load inlines - فقط در edit mode برای بهینه‌سازی performance."""
        if obj:  # Edit mode - object exists
            return [LegalUnitVocabularyTermInline, LegalUnitChangeInline]
        return []  # Add mode - no inlines for faster load
    
    def changelist_view(self, request, extra_context=None):
        """Override to show manifestation list if no manifestation filter."""
        manifestation_id = request.GET.get('manifestation__id__exact')
        
        if not manifestation_id:
            # Show manifestation selection page
            from django.shortcuts import render
            from ingest.apps.documents.models import InstrumentManifestation
            import jdatetime
            
            manifestations_qs = InstrumentManifestation.objects.select_related(
                'expr', 'expr__work'
            ).annotate(
                legalunit_count=models.Count('units')
            ).order_by('expr__work__title_official')
            
            # اضافه کردن تاریخ شمسی به هر manifestation
            manifestations = []
            for m in manifestations_qs:
                if m.publication_date:
                    try:
                        jalali_date = jdatetime.date.fromgregorian(date=m.publication_date)
                        m.jalali_publication_date = jalali_date.strftime('%Y/%m/%d')
                    except Exception:
                        m.jalali_publication_date = str(m.publication_date)
                else:
                    m.jalali_publication_date = '-'
                manifestations.append(m)
            
            context = {
                **self.admin_site.each_context(request),
                'title': 'بندهای قانونی',
                'manifestations': manifestations,
                'opts': self.model._meta,
                'has_view_permission': self.has_view_permission(request),
            }
            return render(request, 'admin/documents/legalunit_manifestation_list.html', context)
        
        # Normal changelist with manifestation filter
        # Add manifestation info to context
        if not extra_context:
            extra_context = {}
        
        try:
            from ingest.apps.documents.models import InstrumentManifestation
            manifestation = InstrumentManifestation.objects.select_related(
                'expr', 'expr__work'
            ).get(id=manifestation_id)
            extra_context['manifestation'] = manifestation
            extra_context['manifestation_title'] = (
                manifestation.expr.work.title_official 
                if manifestation.expr and manifestation.expr.work 
                else f'نسخه سند #{manifestation.id}'
            )
        except:
            pass
        
        return super().changelist_view(request, extra_context)
    
    def get_deleted_objects(self, objs, request):
        """
        Override to bypass SyncLog permission check.
        Delete SyncLogs before checking cascade deletion.
        """
        from django.db import connection
        
        # If objs is a single object, make it a list
        if not hasattr(objs, '__iter__'):
            objs = [objs]
        
        # Collect all chunk IDs
        all_chunk_ids = []
        for obj in objs:
            chunk_ids = list(obj.chunks.values_list('id', flat=True))
            all_chunk_ids.extend(chunk_ids)
        
        # Delete SyncLogs using raw SQL to bypass permissions
        if all_chunk_ids:
            with connection.cursor() as cursor:
                placeholders = ','.join(['%s'] * len(all_chunk_ids))
                query = f"DELETE FROM embeddings_synclog WHERE chunk_id IN ({placeholders})"
                cursor.execute(query, all_chunk_ids)
        
        # Now call parent to get deleted objects (SyncLogs already deleted)
        return super().get_deleted_objects(objs, request)
    
    def delete_model(self, request, obj):
        """Override delete to clean up SyncLogs first."""
        from django.db import transaction, connection
        import logging
        
        logger = logging.getLogger(__name__)
        
        try:
            with transaction.atomic():
                # Get chunk IDs
                chunk_ids = list(obj.chunks.values_list('id', flat=True))
                
                if chunk_ids:
                    # Delete SyncLogs using raw SQL to bypass permissions
                    with connection.cursor() as cursor:
                        placeholders = ','.join(['%s'] * len(chunk_ids))
                        query = f"DELETE FROM embeddings_synclog WHERE chunk_id IN ({placeholders})"
                        cursor.execute(query, chunk_ids)
                        deleted_count = cursor.rowcount
                        
                        if deleted_count > 0:
                            logger.info(f'Deleted {deleted_count} SyncLog entries before deleting LegalUnit {obj.id}')
                
                # Now delete the object (parent will show success message)
                super().delete_model(request, obj)
                
        except Exception as e:
            logger.error(f'Error deleting LegalUnit {obj.id}: {e}', exc_info=True)
            self.message_user(request, f'❌ خطا در حذف: {e}', level='error')
            raise
    
    def delete_queryset(self, request, queryset):
        """Override delete queryset to clean up SyncLogs first."""
        from django.db import transaction, connection
        import logging
        
        logger = logging.getLogger(__name__)
        
        try:
            with transaction.atomic():
                # Collect all chunk IDs from all LegalUnits
                all_chunk_ids = []
                for obj in queryset:
                    chunk_ids = list(obj.chunks.values_list('id', flat=True))
                    all_chunk_ids.extend(chunk_ids)
                
                if all_chunk_ids:
                    # Delete SyncLogs using raw SQL to bypass permissions
                    with connection.cursor() as cursor:
                        placeholders = ','.join(['%s'] * len(all_chunk_ids))
                        query = f"DELETE FROM embeddings_synclog WHERE chunk_id IN ({placeholders})"
                        cursor.execute(query, all_chunk_ids)
                        deleted_count = cursor.rowcount
                        
                        if deleted_count > 0:
                            logger.info(f'Deleted {deleted_count} SyncLog entries before bulk delete')
                
                # Now delete the queryset (parent will show success message)
                super().delete_queryset(request, queryset)
                
        except Exception as e:
            logger.error(f'Error in bulk delete: {e}', exc_info=True)
            self.message_user(request, f'❌ خطا در حذف دسته‌جمعی: {e}', level='error')
            raise
    
    def get_queryset(self, request):
        """Optimize queryset with select_related, prefetch_related and annotate."""
        from django.db.models import Count
        
        qs = super().get_queryset(request).select_related(
            'work', 'expr', 'expr__work', 'manifestation', 'parent'
        )
        
        # Filter by manifestation if provided
        manifestation_id = request.GET.get('manifestation__id__exact')
        if manifestation_id:
            qs = qs.filter(manifestation_id=manifestation_id)
        
        # Add chunk count annotation to avoid N+1 queries
        qs = qs.annotate(chunks_count=Count('chunks'))
        
        # Only prefetch in change view to avoid loading too much data in list view
        if request.resolver_match and '_change' in request.resolver_match.url_name:
            qs = qs.prefetch_related('vocabulary_terms', 'chunks')
        
        return qs
    
    def add_view(self, request, form_url='', extra_context=None):
        """Override add view to pass manifestation to form."""
        extra_context = extra_context or {}
        
        # Check for manifestation in URL
        manifestation_id = request.GET.get('manifestation')
        
        # If not found, try to parse from _changelist_filters
        if not manifestation_id:
            changelist_filters = request.GET.get('_changelist_filters')
            if changelist_filters and 'manifestation__id__exact' in changelist_filters:
                # Parse: manifestation__id__exact=<uuid>
                import re
                match = re.search(r'manifestation__id__exact[=%]([a-f0-9-]+)', changelist_filters)
                if match:
                    manifestation_id = match.group(1)
        
        if manifestation_id:
            extra_context['manifestation_id'] = manifestation_id
        return super().add_view(request, form_url, extra_context)
    
    def get_changeform_initial_data(self, request):
        """Set initial data for the form."""
        initial = super().get_changeform_initial_data(request)
        
        # Get manifestation from URL
        manifestation_id = request.GET.get('manifestation')
        
        # If not found, try to parse from _changelist_filters
        if not manifestation_id:
            changelist_filters = request.GET.get('_changelist_filters')
            if changelist_filters and 'manifestation__id__exact' in changelist_filters:
                import re
                match = re.search(r'manifestation__id__exact[=%]([a-f0-9-]+)', changelist_filters)
                if match:
                    manifestation_id = match.group(1)
        
        if manifestation_id:
            initial['manifestation'] = manifestation_id
        
        return initial
    
    fieldsets = (
        ('اطلاعات اصلی', {
            'fields': ('manifestation','parent', 'unit_type', 'number', 'order_index', 'content'),
            'description': 'اطلاعات پایه و محتوای این بند قانونی'
        }),
        ('اعتبار زمانی', {
            'fields': ('valid_from', 'valid_to'),
            'description': 'لطفا تاریخ ها شمسی وارد شود.'
        }),
        ('شناسه‌های Akoma Ntoso', {
            'fields': ('eli_fragment', 'xml_id'),
            'classes': ('collapse',),
            'description': 'شناسه‌های فنی برای پیوند با استانداردهای بین‌المللی'
        }),
    )
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """
        بهینه‌سازی parent field برای نمایش فقط LegalUnit های همان manifestation.
        استفاده از ParentAutocompleteWidget برای جستجوی سریع.
        """
        if db_field.name == "parent":
            # دریافت manifestation از URL یا object
            manifestation_id = request.GET.get('manifestation')
            
            # اگر در URL نبود، از _changelist_filters بخوان
            if not manifestation_id:
                changelist_filters = request.GET.get('_changelist_filters')
                if changelist_filters and 'manifestation__id__exact' in changelist_filters:
                    import re
                    match = re.search(r'manifestation__id__exact[=%]([a-f0-9-]+)', changelist_filters)
                    if match:
                        manifestation_id = match.group(1)
            
            # اگر در حال ویرایش هستیم، از object بخوان
            if not manifestation_id and hasattr(request, 'resolver_match') and request.resolver_match:
                object_id = request.resolver_match.kwargs.get('object_id')
                if object_id:
                    try:
                        obj = self.model.objects.get(pk=object_id)
                        if obj.manifestation:
                            manifestation_id = str(obj.manifestation.id)
                    except self.model.DoesNotExist:
                        pass
            
            # استفاده از ParentAutocompleteWidget
            if manifestation_id:
                from .widgets import ParentAutocompleteWidget
                kwargs["widget"] = ParentAutocompleteWidget(manifestation_id=manifestation_id, model_name='legalunit')
                # queryset باید all() باشد تا validation کار کند
                kwargs["queryset"] = LegalUnit.objects.all()
            else:
                # اگر manifestation نداریم، همه را نشان بده
                kwargs["queryset"] = LegalUnit.objects.all()
        
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
    
    def get_urls(self):
        """اضافه کردن URL برای AJAX search."""
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path('search-parents/', self.admin_site.admin_view(self.search_parents_view), name='documents_legalunit_search_parents'),
        ]
        return custom_urls + urls
    
    def search_parents_view(self, request):
        """
        AJAX endpoint برای جستجوی والدها.
        مشابه LUnitAdmin.search_parents_view
        """
        from django.http import JsonResponse
        from django.db.models import Q
        
        query = request.GET.get('q', '').strip()
        manifestation_id = request.GET.get('manifestation_id', '')
        
        if not query or not manifestation_id:
            return JsonResponse({'results': []})
        
        # نقشه نوع واحدها
        unit_type_map = {
            'باب': 'part',
            'بخش': 'part',
            'فصل': 'chapter',
            'قسمت': 'section',
            'ماده': 'article',
            'بند': 'clause',
            'زیربند': 'subclause',
            'تبصره': 'note',
            'ضمیمه': 'appendix',
        }
        
        query_lower = query.lower().strip()
        unit_type_filter = None
        number_filter = None
        
        # چک کردن نوع واحد + شماره
        for persian_name, english_code in unit_type_map.items():
            if query_lower.startswith(persian_name.lower()):
                unit_type_filter = english_code
                remaining = query_lower[len(persian_name):].strip()
                if remaining:
                    number_filter = remaining
                break
        
        if not unit_type_filter:
            for persian_name, english_code in unit_type_map.items():
                if query_lower == persian_name.lower():
                    unit_type_filter = english_code
                    break
        
        # ساخت query
        base_query = LegalUnit.objects.filter(manifestation_id=manifestation_id)
        
        if unit_type_filter:
            parents = base_query.filter(unit_type=unit_type_filter)
            if number_filter:
                parents = parents.filter(number=number_filter)
        else:
            parents = base_query.filter(
                Q(number__exact=query) |
                Q(content__icontains=query)
            )
        
        parents = parents.only('id', 'unit_type', 'number', 'content', 'path_label', 'parent').select_related('parent').order_by('parent__order_index', 'order_index', 'number')[:30]
        
        results = []
        for parent in parents:
            display_parts = []
            status_icon = '✓' if parent.is_active else '✗'
            display_parts.append(status_icon)
            
            if parent.path_label:
                display_parts.append(parent.path_label)
            display_parts.append(parent.get_unit_type_display())
            if parent.number:
                display_parts.append(str(parent.number))
            
            display = ' > '.join(display_parts)
            content_preview = parent.content[:50] if parent.content else ''
            
            results.append({
                'id': str(parent.id),
                'type': parent.get_unit_type_display(),
                'number': parent.number or '',
                'path': parent.path_label or '',
                'content': content_preview,
                'display': display,
                'is_active': parent.is_active
            })
        
        return JsonResponse({'results': results})
    
    def get_form(self, request, obj=None, **kwargs):
        # Exclude non-editable fields and hide work/expr since they're auto-populated
        kwargs.setdefault('exclude', []).extend(['id', 'created_at', 'updated_at', 'path_label', 'work', 'expr'])
        
        # Get manifestation from URL
        manifestation_id = request.GET.get('manifestation')
        
        # If not found, try to parse from _changelist_filters
        if not manifestation_id:
            changelist_filters = request.GET.get('_changelist_filters')
            if changelist_filters and 'manifestation__id__exact' in changelist_filters:
                import re
                match = re.search(r'manifestation__id__exact[=%]([a-f0-9-]+)', changelist_filters)
                if match:
                    manifestation_id = match.group(1)
        
        # Store manifestation_id for later use in formfield_for_foreignkey
        request._manifestation_id = manifestation_id
        
        # Clear cache قبل از ساخت form - برای "ذخیره و ایجاد یکی دیگر"
        if manifestation_id:
            from django.core.cache import cache
            cache_key = f'legalunit_parents_{manifestation_id}'
            cache.delete(cache_key)
        
        form = super().get_form(request, obj, **kwargs)
        
        # If manifestation is provided in URL, set it as initial (not disabled)
        if manifestation_id and 'manifestation' in form.base_fields:
            from ingest.apps.documents.models import InstrumentManifestation
            try:
                manifestation = InstrumentManifestation.objects.get(id=manifestation_id)
                form.base_fields['manifestation'].initial = manifestation
                # نباید disabled کنیم چون در POST data نخواهد بود
                form.base_fields['manifestation'].help_text = 'نسخه سند از URL انتخاب شده'
            except InstrumentManifestation.DoesNotExist:
                pass
        
        # ⭐ در edit mode، manifestation از form exclude شده
        # پس نیازی به تنظیمات widget نیست
        
        return form

    def save_model(self, request, obj, form, change):
        """Auto-populate work and expr based on manifestation selection."""
        
        # در add mode، اگر manifestation نداریم
        if not change and not obj.manifestation:
            # اول سعی کن از parent بگیر
            if obj.parent and obj.parent.manifestation:
                obj.manifestation = obj.parent.manifestation
            # اگر parent نداشت، از URL بگیر
            elif not obj.parent:
                manifestation_id = request.GET.get('manifestation')
                if not manifestation_id:
                    changelist_filters = request.GET.get('_changelist_filters')
                    if changelist_filters and 'manifestation__id__exact' in changelist_filters:
                        import re
                        match = re.search(r'manifestation__id__exact[=%]([a-f0-9-]+)', changelist_filters)
                        if match:
                            manifestation_id = match.group(1)
                
                if manifestation_id:
                    from ingest.apps.documents.models import InstrumentManifestation
                    try:
                        obj.manifestation = InstrumentManifestation.objects.get(id=manifestation_id)
                    except InstrumentManifestation.DoesNotExist:
                        pass
        
        # ⭐ در edit mode، manifestation از form exclude شده
        # پس باید از instance قبلی بگیریم
        if change and not obj.manifestation:
            try:
                old_obj = self.model.objects.get(pk=obj.pk)
                obj.manifestation = old_obj.manifestation
            except self.model.DoesNotExist:
                pass
        
        if obj.manifestation:
            # Auto-populate expr from manifestation
            obj.expr = obj.manifestation.expr
            # Auto-populate work from expr
            if obj.expr:
                obj.work = obj.expr.work
        
        super().save_model(request, obj, form, change)
        
        # Clear cache برای parent queryset - تا ایتم جدید فوراً در لیست والد ظاهر شود
        from django.core.cache import cache
        if obj.manifestation:
            cache_key = f'legalunit_parents_{obj.manifestation.id}'
            cache.delete(cache_key)
    
    def response_add(self, request, obj, post_url_continue=None):
        """Override to prevent duplicate success messages."""
        # Don't show message here, let parent handle it
        return super().response_add(request, obj, post_url_continue)
    
    def indented_title(self, obj):
        """
        نمایش عنوان با indent برای tree view.
        این متد توسط MPTTModelAdmin به صورت خودکار indent می‌شود.
        """
        # فقط نمایش محتوا (بدون شماره)
        content = obj.content[:80] if obj.content else '-'
        return content
    indented_title.short_description = 'عنوان'

    def get_source_ref(self, obj):
        if obj.work:
            return f"سند: {obj.work.title_official}"
        elif obj.expr:
            return f"نسخه: {obj.expr.work.title_official}"
        elif obj.manifestation:
            return f"انتشار: {obj.manifestation.expr.work.title_official}"
        return "بدون مرجع"
    get_source_ref.short_description = 'مرجع'

    def chunk_count(self, obj):
        # Use annotated count if available (from optimized queryset)
        if hasattr(obj, 'chunks_count'):
            return obj.chunks_count
        # Fallback to direct count (slower)
        return obj.chunks.count() if hasattr(obj, 'chunks') else 0
    chunk_count.short_description = 'تعداد چانک‌ها'
    
    def is_active_display(self, obj):
        """Display active status with color coding."""
        if obj.is_active:
            return format_html('<span style="color: green;">✓ فعال</span>')
        else:
            return format_html('<span style="color: red;">✗ غیرفعال</span>')
    is_active_display.short_description = 'وضعیت'
    is_active_display.admin_order_field = 'valid_from'
    
    def jalali_valid_from_display(self, obj):
        """Display valid_from in Jalali format."""
        if obj.valid_from:
            return self.jalali_date_display(obj.valid_from)
        return '-'
    jalali_valid_from_display.short_description = 'شروع اعتبار'
    jalali_valid_from_display.admin_order_field = 'valid_from'
    
    def jalali_valid_to_display(self, obj):
        """Display valid_to in Jalali format."""
        if obj.valid_to:
            return self.jalali_date_display(obj.valid_to)
        return 'نامحدود'
    jalali_valid_to_display.short_description = 'پایان اعتبار'
    jalali_valid_to_display.admin_order_field = 'valid_to'
    
    def mark_as_repealed(self, request, queryset):
        """Mark selected units as repealed effective today."""
        from .services.legalunit_changes import LegalUnitChangeService
        
        today = localdate()
        count = 0
        
        for unit in queryset:
            try:
                LegalUnitChangeService.repeal_unit(
                    unit=unit,
                    effective_date=today,
                    note=f"لغو شده توسط {request.user.username} در تاریخ {today}"
                )
                count += 1
            except Exception as e:
                messages.error(request, f"خطا در لغو {unit}: {e}")
        
        if count:
            messages.success(request, f"{count} واحد قانونی با موفقیت لغو شد.")
    mark_as_repealed.short_description = "لغو واحدهای انتخاب شده (اجرا از امروز)"
    
    def mark_as_active(self, request, queryset):
        """Mark selected units as active (remove expiry date)."""
        count = 0
        
        for unit in queryset.filter(valid_to__isnull=False):
            unit.valid_to = None
            unit.save(update_fields=['valid_to'])
            count += 1
        
        if count:
            messages.success(request, f"{count} واحد قانونی به حالت فعال برگردانده شد.")
        else:
            messages.info(request, "هیچ واحد منقضی‌شده‌ای برای فعال‌سازی یافت نشد.")
    mark_as_active.short_description = "فعال‌سازی واحدهای انتخاب شده"
    
    def save_formset(self, request, form, formset, change):
        """Handle FileAsset inline formset to set uploaded_by."""
        if formset.model == FileAsset:
            instances = formset.save(commit=False)
            for instance in instances:
                if not instance.pk:  # Only on create
                    instance.uploaded_by = request.user
                instance.save()
            formset.save_m2m()
        else:
            super().save_formset(request, form, formset, change)
    
    class Media:
        js = ('admin/js/legalunit-parent-filter.js',)
        css = {
            'all': ('admin/css/legalunit-changes.css',)
        }




class InstrumentRelationAdmin(SimpleJalaliAdminMixin, SimpleHistoryAdmin):
    form = InstrumentRelationForm
    list_display = ('from_work', 'relation_type', 'to_work', 'effective_date', 'jalali_created_at_display')
    list_filter = ('relation_type', 'effective_date', 'created_at')
    search_fields = ('from_work__title_official', 'to_work__title_official', 'notes')
    readonly_fields = ('id', 'created_at', 'updated_at')
    
    fieldsets = (
        ('رابطه', {
            'fields': ('from_work', 'relation_type', 'to_work')
        }),
        ('جزئیات', {
            'fields': ('effective_date', 'notes')
        }),
    )
    
    def get_form(self, request, obj=None, **kwargs):
        # Exclude non-editable fields
        kwargs.setdefault('exclude', []).extend(['id', 'created_at', 'updated_at'])
        return super().get_form(request, obj, **kwargs)


class PinpointCitationAdmin(SimpleJalaliAdminMixin, SimpleHistoryAdmin):
    list_display = ('from_unit', 'citation_type', 'to_unit', 'jalali_created_at_display')
    list_filter = ('citation_type', 'created_at')
    search_fields = ('from_unit__path_label', 'to_unit__path_label', 'context_text')
    readonly_fields = ('id', 'created_at', 'updated_at')
    
    fieldsets = (
        ('راهنمای تکمیل فرم', {
            'description': 'در این فرم وقتی یک متن حقوقی (مثلاً قانون مالیات) می‌خواهد به یک بخش مشخص از متن دیگر (مثلا ماده ۵ قانون کار) اشاره کند آنرا در اینجا ثبت می کنیم.',
            'fields': (),
        }),
        ('اطلاعات ارجاع', {
            'fields': ('from_unit', 'citation_type', 'to_unit', 'context_text')
        }),
    )
    
    def get_form(self, request, obj=None, **kwargs):
        # Exclude non-editable fields
        kwargs.setdefault('exclude', []).extend(['id', 'created_at', 'updated_at'])
        return super().get_form(request, obj, **kwargs)


class IngestLogAdmin(SimpleHistoryAdmin):
    list_display = ('operation_type', 'source_system', 'status', 'records_processed', 'started_by', 'created_at')
    list_filter = ('operation_type', 'status', 'source_system', 'created_at')
    search_fields = ('source_id', 'error_message')
    readonly_fields = ('id', 'created_at', 'updated_at')
    
    fieldsets = (
        ('عملیات', {
            'fields': ('operation_type', 'source_system', 'source_id')
        }),
        ('اهداف', {
            'fields': ('target_work', 'target_expression', 'target_manifestation'),
            'classes': ('collapse',)
        }),
        ('نتایج', {
            'fields': ('status', 'records_processed', 'records_failed', 'error_message')
        }),
        ('متادیتا', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        }),
        ('اطلاعات سیستم', {
            'fields': ('started_by', 'id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )


# Chunk Admin - Read-only for viewing automatically generated chunks
class ChunkAdmin(SimpleJalaliAdminMixin, SimpleHistoryAdmin):
    list_display = ('id', 'get_unit_label', 'get_expr_title', 'token_count', 'chunk_preview', 'jalali_created_at_display')
    list_filter = ('created_at', 'expr__work__title_official', 'unit__unit_type')
    search_fields = ('chunk_text', 'unit__label', 'expr__work__title_official')
    readonly_fields = ('expr', 'unit', 'chunk_text', 'token_count', 'overlap_prev', 'citation_payload_json', 'hash', 'created_at', 'updated_at')
    
    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related(
            'expr', 'expr__work', 'unit'
        )
    
    fieldsets = (
        ('اطلاعات چانک', {
            'fields': ('expr', 'unit', 'chunk_text')
        }),
        ('تنظیمات چانک', {
            'fields': ('token_count', 'overlap_prev', 'citation_payload_json')
        }),
        ('اطلاعات سیستم', {
            'fields': ('hash', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [EmbeddingInline]

    def has_add_permission(self, request):
        """Disable adding chunks manually - they are auto-generated"""
        return False
    
    def has_view_permission(self, request, obj=None):
        """Allow viewing chunks"""
        return True
    
    def has_change_permission(self, request, obj=None):
        """Disable editing chunks - read-only access"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Allow superuser to delete chunks, but warn others"""
        return request.user.is_superuser

    def get_unit_label(self, obj):
        return obj.unit.path_label if obj.unit else '-'
    get_unit_label.short_description = 'واحد حقوقی'
    
    def get_expr_title(self, obj):
        if obj.expr and obj.expr.work:
            return obj.expr.work.title_official
        return '-'
    get_expr_title.short_description = 'عنوان سند'
    
    def chunk_preview(self, obj):
        return obj.chunk_text[:100] + '...' if len(obj.chunk_text) > 100 else obj.chunk_text
    chunk_preview.short_description = 'پیش‌نمای متن'


# ChunkAdminRegistered will be registered after QAEntry for proper sidebar ordering
class ChunkAdminRegistered(ChunkAdmin):
    def has_module_permission(self, request):
        """Override to ensure proper view-only permissions"""
        return self.has_view_permission(request)
    
    def get_model_perms(self, request):
        """Return only view permission to show view icon instead of change icon"""
        return {
            'add': self.has_add_permission(request),
            'change': False,  # Force change to False to show view icon
            'delete': self.has_delete_permission(request),
            'view': self.has_view_permission(request),
        }

# QA Entry Admin - Inlines
class QAEntryVocabularyTermInline(admin.TabularInline):
    """Inline برای تگ‌های QAEntry با autocomplete."""
    model = QAEntryVocabularyTerm
    extra = 1
    fields = ('vocabulary_term', 'weight')
    autocomplete_fields = ['vocabulary_term']
    verbose_name = 'برچسب'
    verbose_name_plural = 'برچسب‌ها'


class QAEntryRelatedUnitInline(admin.TabularInline):
    """Inline برای بندهای مرتبط QAEntry با autocomplete."""
    model = QAEntryRelatedUnit
    extra = 1
    fields = ('legal_unit',)
    autocomplete_fields = ['legal_unit']
    verbose_name = 'بند مرتبط'
    verbose_name_plural = 'بندهای مرتبط'


class QAEntryAdmin(SimpleJalaliAdminMixin, SimpleHistoryAdmin):
    """Admin برای پرسش و پاسخ با تگ و ارتباط با بندها."""
    
    list_display = (
        'id', 'short_question', 'tags_display', 'units_display',
        'created_by', 'jalali_created_at_display', 'jalali_updated_at_display'
    )
    list_filter = ('tags', 'created_at')
    search_fields = ('question', 'answer', 'canonical_question')
    readonly_fields = ('created_by_display', 'jalali_created_at_display', 'jalali_updated_at_display')
    inlines = [QAEntryVocabularyTermInline, QAEntryRelatedUnitInline]
    
    fieldsets = (
        ('محتوای پرسش و پاسخ', {
            'fields': ('question', 'answer')
        }),
        ('اطلاعات سیستم', {
            'fields': ('created_by_display', 'jalali_created_at_display', 'jalali_updated_at_display'),
            'classes': ('collapse',)
        }),
    )
    
    def created_by_display(self, obj):
        """نمایش ایجادکننده یا کاربر جاری برای ورودی جدید"""
        if obj and obj.created_by:
            return obj.created_by.username
        elif hasattr(self, '_current_request'):
            return f"{self._current_request.user.username} (کاربر جاری)"
        return "کاربر جاری"
    created_by_display.short_description = "ایجادکننده"
    
    def jalali_updated_at_display(self, obj):
        """Display updated_at in Jalali format."""
        if obj.updated_at:
            from ingest.core.jalali import to_jalali_datetime
            return to_jalali_datetime(obj.updated_at)
        return '-'
    jalali_updated_at_display.short_description = 'زمان ویرایش (شمسی)'
    jalali_updated_at_display.admin_order_field = 'updated_at'
    
    def tags_display(self, obj):
        """نمایش تگ‌ها."""
        tags = obj.tags.all()[:3]
        if tags:
            tag_names = [t.term for t in tags]
            result = ', '.join(tag_names)
            if obj.tags.count() > 3:
                result += f' (+{obj.tags.count() - 3})'
            return result
        return '-'
    tags_display.short_description = 'برچسب‌ها'
    
    def units_display(self, obj):
        """نمایش بندهای مرتبط."""
        units = obj.related_units.all()[:2]
        if units:
            unit_labels = []
            for unit in units:
                label = unit.get_unit_type_display()
                if unit.number:
                    label += f" {unit.number}"
                unit_labels.append(label)
            result = ', '.join(unit_labels)
            if obj.related_units.count() > 2:
                result += f' (+{obj.related_units.count() - 2})'
            return result
        return '-'
    units_display.short_description = 'بندهای مرتبط'
    
    def get_form(self, request, obj=None, **kwargs):
        # ذخیره request برای استفاده در created_by_display
        self._current_request = request
        return super().get_form(request, obj, **kwargs)
    
    def save_model(self, request, obj, form, change):
        """Set created_by when creating new QA entry."""
        if not change:  # Creating new object
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related(
            'created_by'
        ).prefetch_related('tags', 'related_units')
    
    def get_deleted_objects(self, objs, request):
        """
        Override to bypass SyncLog permission check.
        Delete SyncLogs before checking cascade deletion.
        """
        from django.db import connection
        from .models import Chunk
        
        # If objs is a single object, make it a list
        if not hasattr(objs, '__iter__'):
            objs = [objs]
        
        # Collect all chunk IDs
        all_chunk_ids = []
        for obj in objs:
            chunk_ids = list(Chunk.objects.filter(qaentry_id=obj.id).values_list('id', flat=True))
            all_chunk_ids.extend(chunk_ids)
        
        # Delete SyncLogs using raw SQL to bypass permissions
        if all_chunk_ids:
            with connection.cursor() as cursor:
                placeholders = ','.join(['%s'] * len(all_chunk_ids))
                query = f"DELETE FROM embeddings_synclog WHERE chunk_id IN ({placeholders})"
                cursor.execute(query, all_chunk_ids)
        
        # Now call parent to get deleted objects (SyncLogs already deleted)
        return super().get_deleted_objects(objs, request)
    
    def delete_model(self, request, obj):
        """Override delete to clean up SyncLogs, chunks, and embeddings first."""
        from django.db import transaction, connection
        import logging
        
        logger = logging.getLogger(__name__)
        
        try:
            with transaction.atomic():
                # Get chunk IDs for this QAEntry
                from .models import Chunk
                chunk_ids = list(Chunk.objects.filter(qaentry_id=obj.id).values_list('id', flat=True))
                
                if chunk_ids:
                    # Delete SyncLogs using raw SQL to bypass permissions
                    with connection.cursor() as cursor:
                        placeholders = ','.join(['%s'] * len(chunk_ids))
                        query = f"DELETE FROM embeddings_synclog WHERE chunk_id IN ({placeholders})"
                        cursor.execute(query, chunk_ids)
                        deleted_count = cursor.rowcount
                        
                        if deleted_count > 0:
                            logger.info(f'Deleted {deleted_count} SyncLog entries before deleting QAEntry {obj.id}')
                
                # Now delete the object (signals will handle chunk and embedding cleanup)
                super().delete_model(request, obj)
                
        except Exception as e:
            logger.error(f'Error deleting QAEntry {obj.id}: {e}', exc_info=True)
            self.message_user(request, f'❌ خطا در حذف: {e}', level='error')
            raise


# IngestLogRAG moved to embeddings/admin.py to group with EmbeddingProxy


# ============================================================================
# TextEntry Admin - متون
# ============================================================================

class TextEntryVocabularyTermInline(admin.TabularInline):
    """Inline برای تگ‌های TextEntry با autocomplete."""
    model = TextEntryVocabularyTerm
    extra = 1
    fields = ('vocabulary_term', 'weight')
    autocomplete_fields = ['vocabulary_term']
    verbose_name = 'برچسب'
    verbose_name_plural = 'برچسب‌ها'


class TextEntryRelatedUnitInline(admin.TabularInline):
    """Inline برای بندهای مرتبط TextEntry با autocomplete."""
    model = TextEntryRelatedUnit
    extra = 1
    fields = ('legal_unit',)
    autocomplete_fields = ['legal_unit']
    verbose_name = 'بند مرتبط'
    verbose_name_plural = 'بندهای مرتبط'


class TextEntryAdmin(SimpleJalaliAdminMixin, SimpleHistoryAdmin):
    """Admin برای متون با قابلیت آپلود فایل و ارتباط با بندها."""
    
    form = TextEntryForm
    list_display = (
        'title', 'text_type', 'validity_status', 'jalali_validity_start_display', 
        'created_by', 'jalali_created_at_display'
    )
    list_filter = ('text_type', 'created_at', 'vocabulary_terms', 'validity_start_date', 'validity_end_date')
    search_fields = ('title', 'content')
    readonly_fields = ('jalali_created_at_display', 'jalali_updated_at_display', 'jalali_validity_start_display', 'original_filename', 'content_extracted')
    inlines = [TextEntryVocabularyTermInline, TextEntryRelatedUnitInline]
    
    fieldsets = (
        ('اطلاعات اصلی', {
            'fields': ('title', 'text_type')
        }),
        ('محتوا', {
            'fields': ('content', 'source_file', 'original_filename')
        }),
        ('اعتبار', {
            'fields': ('validity_start_date', 'validity_end_date'),
            'description': 'تاریخ شروع خالی = از ابتدا معتبر | تاریخ پایان خالی = همچنان معتبر'
        }),
        ('اطلاعات سیستم', {
            'fields': ('jalali_created_at_display', 'jalali_updated_at_display'),
            'classes': ('collapse',)
        }),
    )
    
    def content_preview(self, obj):
        """نمایش پیش‌نمایش محتوا."""
        if obj.content:
            preview = obj.content[:100]
            if len(obj.content) > 100:
                preview += '...'
            return preview
        return '-'
    content_preview.short_description = 'پیش‌نمایش محتوا'
    
    def file_info(self, obj):
        """نمایش اطلاعات فایل."""
        if obj.source_file:
            return format_html(
                '<a href="{}" target="_blank">{}</a>',
                obj.source_file.url,
                obj.original_filename or 'دانلود'
            )
        return '-'
    file_info.short_description = 'فایل'
    
    def tags_display(self, obj):
        """نمایش تگ‌ها."""
        tags = obj.vocabulary_terms.all()[:3]
        if tags:
            tag_names = [t.term for t in tags]
            result = ', '.join(tag_names)
            if obj.vocabulary_terms.count() > 3:
                result += f' (+{obj.vocabulary_terms.count() - 3})'
            return result
        return '-'
    tags_display.short_description = 'برچسب‌ها'
    
    def jalali_updated_at_display(self, obj):
        """Display updated_at in Jalali format."""
        if obj.updated_at:
            from ingest.core.jalali import to_jalali_datetime
            return to_jalali_datetime(obj.updated_at)
        return '-'
    jalali_updated_at_display.short_description = 'زمان ویرایش (شمسی)'
    jalali_updated_at_display.admin_order_field = 'updated_at'
    
    def jalali_validity_start_display(self, obj):
        """Display validity_start_date in Jalali format."""
        if obj.validity_start_date:
            from ingest.core.jalali import to_jalali_date
            return to_jalali_date(obj.validity_start_date)
        return '-'
    jalali_validity_start_display.short_description = 'تاریخ شروع اعتبار'
    jalali_validity_start_display.admin_order_field = 'validity_start_date'
    
    def content_extracted(self, obj):
        """نمایش وضعیت استخراج محتوا."""
        if obj.source_file and obj.content:
            return '✅ استخراج شده'
        elif obj.source_file:
            return '⏳ در انتظار استخراج'
        return '-'
    content_extracted.short_description = 'وضعیت استخراج'
    
    def validity_status(self, obj):
        """نمایش وضعیت اعتبار."""
        from django.utils import timezone
        today = timezone.now().date()
        
        # بررسی تاریخ شروع
        if obj.validity_start_date and today < obj.validity_start_date:
            return '⏳ هنوز شروع نشده'
        
        # بررسی تاریخ پایان
        if obj.validity_end_date and today > obj.validity_end_date:
            return '❌ منقضی شده'
        
        return '✅ معتبر'
    validity_status.short_description = 'وضعیت اعتبار'
    
    def save_model(self, request, obj, form, change):
        """Set created_by when creating new entry."""
        if not change:
            obj.created_by = request.user
        
        # اگر فایل آپلود شده و محتوا خالی است، استخراج کن
        if obj.source_file and not obj.content:
            obj.extract_content_from_file()
        
        super().save_model(request, obj, form, change)
    
    def get_urls(self):
        """اضافه کردن URL برای AJAX search بندها."""
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path('search-units/', self.admin_site.admin_view(self.search_units_view), name='textentry_search_units'),
        ]
        return custom_urls + urls
    
    def search_units_view(self, request):
        """AJAX endpoint برای جستجوی بندها."""
        from django.http import JsonResponse
        
        query = request.GET.get('q', '').strip()
        if not query or len(query) < 2:
            return JsonResponse({'results': []})
        
        # جستجو در عنوان، شماره و path_label
        units = LegalUnit.objects.filter(
            models.Q(content__icontains=query) |
            models.Q(number__icontains=query) |
            models.Q(path_label__icontains=query) |
            models.Q(manifestation__expr__work__title_official__icontains=query)
        ).select_related(
            'manifestation__expr__work'
        )[:20]
        
        results = []
        for unit in units:
            work_title = ''
            if unit.manifestation and unit.manifestation.expr and unit.manifestation.expr.work:
                work_title = unit.manifestation.expr.work.title_official
            
            label = f"{work_title} - {unit.get_unit_type_display()}"
            if unit.number:
                label += f" {unit.number}"
            if unit.path_label:
                label += f" ({unit.path_label})"
            
            results.append({
                'id': str(unit.id),
                'text': label
            })
        
        return JsonResponse({'results': results})
    
    def get_queryset(self, request):
        """Optimize queryset."""
        return super().get_queryset(request).select_related(
            'created_by'
        ).prefetch_related('vocabulary_terms', 'related_units')
    
    def get_deleted_objects(self, objs, request):
        """
        Override to bypass SyncLog permission check.
        Delete SyncLogs before checking cascade deletion.
        """
        from django.db import connection
        from .models import Chunk
        
        # If objs is a single object, make it a list
        if not hasattr(objs, '__iter__'):
            objs = [objs]
        
        # Collect all chunk IDs
        all_chunk_ids = []
        for obj in objs:
            chunk_ids = list(Chunk.objects.filter(textentry_id=obj.id).values_list('id', flat=True))
            all_chunk_ids.extend(chunk_ids)
        
        # Delete SyncLogs using raw SQL to bypass permissions
        if all_chunk_ids:
            with connection.cursor() as cursor:
                placeholders = ','.join(['%s'] * len(all_chunk_ids))
                query = f"DELETE FROM embeddings_synclog WHERE chunk_id IN ({placeholders})"
                cursor.execute(query, all_chunk_ids)
        
        # Now call parent to get deleted objects (SyncLogs already deleted)
        return super().get_deleted_objects(objs, request)
    
    def delete_model(self, request, obj):
        """Override delete to clean up SyncLogs, chunks, and embeddings first."""
        from django.db import transaction, connection
        import logging
        
        logger = logging.getLogger(__name__)
        
        try:
            with transaction.atomic():
                # Get chunk IDs for this TextEntry
                from .models import Chunk
                chunk_ids = list(Chunk.objects.filter(textentry_id=obj.id).values_list('id', flat=True))
                
                if chunk_ids:
                    # Delete SyncLogs using raw SQL to bypass permissions
                    with connection.cursor() as cursor:
                        placeholders = ','.join(['%s'] * len(chunk_ids))
                        query = f"DELETE FROM embeddings_synclog WHERE chunk_id IN ({placeholders})"
                        cursor.execute(query, chunk_ids)
                        deleted_count = cursor.rowcount
                        
                        if deleted_count > 0:
                            logger.info(f'Deleted {deleted_count} SyncLog entries before deleting TextEntry {obj.id}')
                
                # Now delete the object (signals will handle chunk and embedding cleanup)
                super().delete_model(request, obj)
                
        except Exception as e:
            logger.error(f'Error deleting TextEntry {obj.id}: {e}', exc_info=True)
            self.message_user(request, f'❌ خطا در حذف: {e}', level='error')
            raise


# ============================================================================
# ثبت مدل‌ها در admin - ترتیب مهم است!
# ============================================================================

# 0. LegalUnit برای autocomplete (بدون نمایش در منو)
class LegalUnitAutocompleteAdmin(admin.ModelAdmin):
    """Admin مخفی برای LegalUnit - فقط برای autocomplete استفاده می‌شود."""
    search_fields = ('content', 'path_label', 'number', 'manifestation__expr__work__title_official')
    
    def has_module_permission(self, request):
        """مخفی کردن از منوی admin."""
        return False

admin_site.register(LegalUnit, LegalUnitAutocompleteAdmin)

# 1. بندهای اسناد حقوقی - اول
from .admin_lunit import LUnitAdmin
admin_site.register(LUnit, LUnitAdmin)

# 2. پرسش و پاسخ - دوم
admin_site.register(QAEntry, QAEntryAdmin)

# 3. متون - سوم
admin_site.register(TextEntry, TextEntryAdmin)

# 4. سایر مدل‌های مدیریت اسناد
admin_site.register(PinpointCitation, PinpointCitationAdmin)
admin_site.register(FileAsset, FileAssetAdmin)
admin_site.register(Chunk, ChunkAdminRegistered)

# 4. اسناد حقوقی (فرم یکپارچه) - قبل از Work/Expression/Manifestation
import ingest.apps.documents.admin_document  # noqa: F401

# 5. تعریف اسناد (Work/Expression/Manifestation)
admin_site.register(InstrumentWork, InstrumentWorkAdmin)
admin_site.register(InstrumentExpression, InstrumentExpressionAdmin)
admin_site.register(InstrumentManifestation, InstrumentManifestationAdmin)
admin_site.register(InstrumentRelation, InstrumentRelationAdmin)
