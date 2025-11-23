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
    LegalUnit, LegalUnitChange, LegalUnitVocabularyTerm, InstrumentRelation, PinpointCitation,
    FileAsset, Chunk, IngestLog, QAEntry
)
from .forms import (
    InstrumentExpressionForm, InstrumentManifestationForm, InstrumentRelationForm, LegalUnitForm, FileAssetForm
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
    list_display = ('filename', 'description', 'formatted_size', 'uploaded_by', 'jalali_created_at_display')
    list_filter = ('uploaded_by', 'created_at')
    search_fields = ('file', 'description')
    readonly_fields = ('id', 'filename', 'file_size', 'formatted_size', 'uploaded_by_display', 'created_at', 'updated_at')
    actions = ['delete_selected']
    
    fieldsets = (
        ('مراجع', {
            'fields': ('legal_unit', 'manifestation'),
            'description': 'لطفاً فقط یکی از موارد زیر را انتخاب کنید - یا جزء سند حقوقی یا انتشار سند'
        }),
        ('فایل', {
            'fields': ('file', 'description')
        }),
        ('اطلاعات سیستم', {
            'fields': ('uploaded_by', 'created_at', 'updated_at'),
            'classes': ('collapse',),
            'description': 'آپلودکننده خودکار کاربر جاری تنظیم می‌شود'
        }),
    )
    
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
        return super().get_form(request, obj, **kwargs)
    
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
    inlines = [EmbeddingInline]
    
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
    inlines = [EmbeddingInline]
    
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
    inlines = [FileAssetInline, EmbeddingInline]
    
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
    inlines = [LegalUnitVocabularyTermInline, LegalUnitChangeInline]
    actions = ['mark_as_repealed', 'mark_as_active']
    list_per_page = 100
    
    # MPTT settings برای نمایش درختی
    mptt_indent_field = "indented_title"
    
    def changelist_view(self, request, extra_context=None):
        """Override to show manifestation list if no manifestation filter."""
        manifestation_id = request.GET.get('manifestation__id__exact')
        
        if not manifestation_id:
            # Show manifestation selection page
            from django.shortcuts import render
            from ingest.apps.documents.models import InstrumentManifestation
            
            manifestations = InstrumentManifestation.objects.select_related(
                'expr', 'expr__work'
            ).annotate(
                legalunit_count=models.Count('units')
            ).order_by('-created_at')
            
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
        این متد بهترین روش Django برای فیلتر کردن ForeignKey است.
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
            if not manifestation_id and hasattr(request, 'resolver_match'):
                object_id = request.resolver_match.kwargs.get('object_id')
                if object_id:
                    try:
                        obj = self.model.objects.get(pk=object_id)
                        if obj.manifestation:
                            manifestation_id = str(obj.manifestation.id)
                    except self.model.DoesNotExist:
                        pass
            
            # اعمال فیلتر اگر manifestation پیدا شد
            if manifestation_id:
                # استفاده از همان queryset که در form استفاده می‌شود
                queryset = LegalUnit.objects.filter(
                    manifestation_id=manifestation_id
                ).order_by('order_index', 'number')
                
                # اگر در حال ویرایش هستیم، خود object را exclude کن
                if hasattr(request, 'resolver_match') and request.resolver_match:
                    object_id = request.resolver_match.kwargs.get('object_id')
                    if object_id:
                        queryset = queryset.exclude(pk=object_id)
                
                kwargs["queryset"] = queryset
            else:
                # اگر manifestation نداریم، همه را نشان بده (برای validation)
                # اما در form این محدود می‌شود
                kwargs["queryset"] = LegalUnit.objects.all()
        
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
    
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
        
        # If editing existing object, make manifestation readonly با HiddenInput
        if obj and 'manifestation' in form.base_fields:
            from django import forms as django_forms
            # استفاده از HiddenInput + readonly text برای نمایش
            form.base_fields['manifestation'].widget = django_forms.HiddenInput()
            form.base_fields['manifestation'].initial = obj.manifestation
        
        return form

    def save_model(self, request, obj, form, change):
        """Auto-populate work and expr based on manifestation selection."""
        if obj.manifestation:
            # Auto-populate expr from manifestation
            obj.expr = obj.manifestation.expr
            # Auto-populate work from expr
            if obj.expr:
                obj.work = obj.expr.work
        
        super().save_model(request, obj, form, change)
    
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

# QA Entry Admin
@admin.action(description='تأیید ورودی‌های انتخاب شده')
def approve_qa_entries(modeladmin, request, queryset):
    """Bulk approve QA entries."""
    for qa_entry in queryset:
        qa_entry.approve(request.user)
    modeladmin.message_user(request, f'{queryset.count()} ورودی تأیید شد.')


@admin.action(description='رد ورودی‌های انتخاب شده')
def reject_qa_entries(modeladmin, request, queryset):
    """Bulk reject QA entries."""
    for qa_entry in queryset:
        qa_entry.reject()
    modeladmin.message_user(request, f'{queryset.count()} ورودی رد شد.')


class QAEntryAdmin(SimpleJalaliAdminMixin, SimpleHistoryAdmin):
    list_display = (
        'id', 'short_question', 'status', 'created_by', 
        'approved_by', 'jalali_created_at_display', 'jalali_approved_at_display'
    )
    list_filter = ('status', 'tags', 'created_at', 'approved_at')
    search_fields = ('question', 'answer', 'canonical_question')
    readonly_fields = ('created_by_display', 'jalali_created_at_display', 'jalali_approved_at_display')
    actions = [approve_qa_entries, reject_qa_entries]
    
    fieldsets = (
        ('محتوای پرسش و پاسخ', {
            'fields': ('question', 'answer')
        }),
        ('وضعیت و تأیید', {
            'fields': ('status', 'approved_by', 'jalali_approved_at_display')
        }),
        ('منابع و ارجاعات', {
            'fields': ('source_work', 'source_unit', 'tags'),
            'classes': ('collapse',)
        }),
        ('اطلاعات سیستم', {
            'fields': ('created_by_display', 'jalali_created_at_display'),
            'classes': ('collapse',)
        }),
    )
    
    filter_horizontal = ('tags',)
    
    def created_by_display(self, obj):
        """نمایش ایجادکننده یا کاربر جاری برای ورودی جدید"""
        if obj and obj.created_by:
            return obj.created_by.username
        elif hasattr(self, '_current_request'):
            return f"{self._current_request.user.username} (کاربر جاری)"
        return "کاربر جاری"
    created_by_display.short_description = "ایجادکننده"
    
    def jalali_approved_at_display(self, obj):
        """Display approved_at in Jalali format."""
        if obj.approved_at:
            from ingest.core.jalali import to_jalali_datetime
            return to_jalali_datetime(obj.approved_at)
        return '-'
    jalali_approved_at_display.short_description = 'زمان تأیید (شمسی)'
    jalali_approved_at_display.admin_order_field = 'approved_at'
    
    def get_form(self, request, obj=None, **kwargs):
        # ذخیره request برای استفاده در created_by_display
        self._current_request = request
        return super().get_form(request, obj, **kwargs)
    
    def get_readonly_fields(self, request, obj=None):
        """Make different fields readonly based on create/edit mode."""
        readonly = list(self.readonly_fields)
        
        if obj:  # Editing existing object
            # In edit mode, only approved_by can be changed (for moderation)
            # All other fields including created_by should be readonly
            readonly.extend(['question', 'answer', 'source_work', 'source_unit'])
            # Remove approved_by from readonly if user has permission to moderate
            if request.user.has_perm('documents.change_qaentry'):
                # approved_by can be changed for moderation
                pass
        else:  # Creating new object
            # In create mode, created_by is automatically set and readonly
            pass
            
        return readonly
    
    def save_model(self, request, obj, form, change):
        """Set created_by when creating new QA entry."""
        if not change:  # Creating new object
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related(
            'created_by', 'approved_by', 'source_work', 'source_unit'
        ).prefetch_related('tags')


# IngestLogRAG moved to embeddings/admin.py to group with EmbeddingProxy

# Register main models
admin_site.register(InstrumentWork, InstrumentWorkAdmin)
admin_site.register(InstrumentExpression, InstrumentExpressionAdmin)
admin_site.register(InstrumentManifestation, InstrumentManifestationAdmin)
admin_site.register(LegalUnit, LegalUnitAdmin)
admin_site.register(InstrumentRelation, InstrumentRelationAdmin)
admin_site.register(PinpointCitation, PinpointCitationAdmin)
admin_site.register(FileAsset, FileAssetAdmin)
admin_site.register(QAEntry, QAEntryAdmin)
admin_site.register(Chunk, ChunkAdminRegistered)  # Register after QAEntry for sidebar ordering
