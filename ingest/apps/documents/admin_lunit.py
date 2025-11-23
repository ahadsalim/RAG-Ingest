"""
Admin interface برای LUnit - نسخه بهینه شده LegalUnit
با تجربه کاربری بهتر و فرآیند ساده‌تر
"""
from django.contrib import admin
from django.db import models
from django.utils.html import format_html
from django.shortcuts import render
from mptt.admin import MPTTModelAdmin
from simple_history.admin import SimpleHistoryAdmin

from ingest.core.admin_mixins import JalaliAdminMixin as SimpleJalaliAdminMixin
from .models import LUnit, InstrumentManifestation, LegalUnit, LegalUnitVocabularyTerm
from .forms import LUnitForm
from django.http import JsonResponse
from django.db.models import Q


class LegalUnitVocabularyTermInlineSimple(admin.TabularInline):
    """Inline ساده برای Tags با autocomplete."""
    model = LegalUnitVocabularyTerm
    extra = 0  # بدون ردیف پیش‌فرض
    fields = ('vocabulary_term', 'weight')
    autocomplete_fields = ['vocabulary_term']
    verbose_name = 'برچسب'
    verbose_name_plural = 'برچسب‌ها'
    
    def get_queryset(self, request):
        """فقط تگ‌های موجود را نمایش بده، نه همه."""
        qs = super().get_queryset(request)
        # اگر object جدید است، queryset خالی برگردان
        if not hasattr(request, '_obj_') or not request._obj_:
            return qs.none()
        return qs


class LUnitAdmin(SimpleJalaliAdminMixin, MPTTModelAdmin, SimpleHistoryAdmin):
    """
    Admin برای LUnit با رابط کاربری ساده و بهینه.
    """
    form = LUnitForm
    
    
    # List display
    list_display = ('indented_title_short', 'is_active_display', 'unit_type_display', 'order_index_display', 'chunk_display', 'jalali_created_at_display')
    list_filter = ('unit_type', 'created_at')
    search_fields = ('content', 'path_label', 'number')
    mptt_level_indent = 20
    readonly_fields = ('path_label', 'created_at', 'updated_at')
    list_per_page = 100
    
    # MPTT settings
    mptt_indent_field = "indented_title_short"
    
    # Inlines
    inlines = [LegalUnitVocabularyTermInlineSimple]
    
    # از get_fieldsets استفاده می‌کنیم تا parent با widget سفارشی اضافه شود
    def get_fieldsets(self, request, obj=None):
        """Fieldsets با ساختار جدید - 3 بخش."""
        return (
            ('', {
                'fields': (
                    ('parent', 'order_index'),
                    ('unit_type', 'number'),
                ),
                'classes': ('wide',),
            }),
            ('', {
                'fields': (
                    'content',
                    ('valid_from', 'valid_to'),
                ),
                'classes': ('wide',),
            }),
        )
    
    def get_queryset(self, request):
        """بهینه‌سازی queryset."""
        qs = super().get_queryset(request)
        return qs.select_related('manifestation', 'manifestation__expr', 'manifestation__expr__work')
    
    def get_urls(self):
        """اضافه کردن URL برای AJAX search."""
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path('search-parents/', self.admin_site.admin_view(self.search_parents_view), name='lunit_search_parents'),
        ]
        return custom_urls + urls
    
    def search_parents_view(self, request):
        """
        AJAX endpoint برای جستجوی والدها.
        جستجو در: مسیر + نوع واحد + شماره + 15 کاراکتر اول محتوا
        """
        query = request.GET.get('q', '').strip()
        manifestation_id = request.GET.get('manifestation_id', '')
        
        if not query or not manifestation_id:
            return JsonResponse({'results': []})
        
        # جستجو در والدها - در مسیر، نوع، شماره، و محتوا
        parents = LegalUnit.objects.filter(
            manifestation_id=manifestation_id
        ).filter(
            Q(path_label__icontains=query) |
            Q(number__icontains=query) |
            Q(unit_type__icontains=query) |
            Q(content__icontains=query)
        ).only('id', 'unit_type', 'number', 'content', 'path_label').order_by('order_index', 'number')[:20]
        
        results = []
        for parent in parents:
            # ترکیب: مسیر + نوع + شماره + 15 کاراکتر اول محتوا
            display_parts = []
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
                'display': display
            })
        
        return JsonResponse({'results': results})
    
    def changelist_view(self, request, extra_context=None):
        """
        نمایش لیست manifestation ها اگر manifestation انتخاب نشده.
        """
        manifestation_id = request.GET.get('manifestation__id__exact')
        
        if not manifestation_id:
            # نمایش لیست اسناد حقوقی
            manifestations = InstrumentManifestation.objects.select_related(
                'expr', 'expr__work'
            ).annotate(
                legalunit_count=models.Count('units')
            ).order_by('-created_at')
            
            context = {
                **self.admin_site.each_context(request),
                'title': 'اسناد حقوقی',
                'manifestations': manifestations,
                'opts': self.model._meta,
                'has_view_permission': self.has_view_permission(request),
                'has_add_permission': self.has_add_permission(request),
            }
            return render(request, 'admin/documents/lunit_manifestation_list.html', context)
        
        # نمایش لیست بندها با اطلاعات سند
        if not extra_context:
            extra_context = {}
        
        try:
            manifestation = InstrumentManifestation.objects.select_related(
                'expr', 'expr__work'
            ).get(id=manifestation_id)
            extra_context['manifestation'] = manifestation
            extra_context['manifestation_title'] = (
                manifestation.expr.work.title_official 
                if manifestation.expr and manifestation.expr.work 
                else f'سند #{manifestation.id}'
            )
        except:
            pass
        
        return super().changelist_view(request, extra_context)
    
    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        """تنظیم عنوان صفحه."""
        extra_context = extra_context or {}
        
        # دریافت manifestation
        manifestation_id = request.GET.get('manifestation') or request.GET.get('_changelist_filters', '')
        if 'manifestation__id__exact' in manifestation_id:
            import re
            match = re.search(r'manifestation__id__exact[=%]([a-f0-9-]+)', manifestation_id)
            if match:
                manifestation_id = match.group(1)
        
        if manifestation_id and not object_id:
            try:
                manifestation = InstrumentManifestation.objects.get(id=manifestation_id)
                manifestation_title = (
                    manifestation.expr.work.title_official 
                    if manifestation.expr and manifestation.expr.work 
                    else f'سند #{manifestation.id}'
                )
                extra_context['title'] = f'اضافه کردن بند به سند: {manifestation_title}'
            except:
                pass
        
        return super().changeform_view(request, object_id, form_url, extra_context)
    
    def get_form(self, request, obj=None, **kwargs):
        """
        تنظیمات فرم.
        در edit mode: manifestation را exclude کن.
        """
        # در edit mode: exclude manifestation
        if obj:
            kwargs.setdefault('exclude', []).append('manifestation')
        
        # Get manifestation_id از URL
        manifestation_id = request.GET.get('manifestation')
        
        if not manifestation_id:
            changelist_filters = request.GET.get('_changelist_filters')
            if changelist_filters and 'manifestation__id__exact' in changelist_filters:
                import re
                match = re.search(r'manifestation__id__exact[=%]([a-f0-9-]+)', changelist_filters)
                if match:
                    manifestation_id = match.group(1)
        
        # ذخیره برای استفاده در form
        request._manifestation_id = manifestation_id
        
        # دریافت form
        FormClass = super().get_form(request, obj, **kwargs)
        
        # Custom form class که manifestation_id را pass می‌کند
        class CustomFormClass(FormClass):
            def __init__(self, *args, **kwargs):
                # Pass manifestation_id به form
                if manifestation_id and not obj:
                    kwargs['manifestation_id'] = manifestation_id
                super().__init__(*args, **kwargs)
                
                # اجبار استفاده از ParentAutocompleteWidget
                if manifestation_id and 'parent' in self.fields:
                    from .widgets import ParentAutocompleteWidget
                    self.fields['parent'].widget = ParentAutocompleteWidget(manifestation_id=manifestation_id)
                    self.fields['parent'].widget.attrs['style'] = 'width: 500px; display: inline-block;'
                    self.fields['parent'].queryset = LegalUnit.objects.none()
        
        # Set initial برای add mode
        if manifestation_id and not obj:
            try:
                manifestation = InstrumentManifestation.objects.get(id=manifestation_id)
                if 'manifestation' in CustomFormClass.base_fields:
                    CustomFormClass.base_fields['manifestation'].initial = manifestation
            except InstrumentManifestation.DoesNotExist:
                pass
        
        return CustomFormClass
    
    def save_model(self, request, obj, form, change):
        """ذخیره با auto-populate."""
        
        # در edit mode، manifestation را restore کن
        if change and not obj.manifestation:
            try:
                old_obj = self.model.objects.get(pk=obj.pk)
                obj.manifestation = old_obj.manifestation
            except self.model.DoesNotExist:
                pass
        
        # Auto-populate work/expr
        if obj.manifestation:
            obj.expr = obj.manifestation.expr
            if obj.expr:
                obj.work = obj.expr.work
        
        super().save_model(request, obj, form, change)
    
    def response_add(self, request, obj, post_url_continue=None):
        """بعد از add، به لیست همان manifestation برگرد."""
        response = super().response_add(request, obj, post_url_continue)
        
        # اگر به changelist برمی‌گردد، manifestation filter را حفظ کن
        if obj.manifestation and response.status_code == 302:
            if '/change/' not in response.url and '/add/' not in response.url:
                if '?' not in response.url:
                    response.url += f'?manifestation__id__exact={obj.manifestation.id}'
        
        return response
    
    def response_change(self, request, obj):
        """بعد از edit، به لیست همان manifestation برگرد."""
        response = super().response_change(request, obj)
        
        # اگر به changelist برمی‌گردد، manifestation filter را حفظ کن
        if obj.manifestation and response.status_code == 302:
            if '/change/' not in response.url and '/add/' not in response.url:
                if '?' not in response.url:
                    response.url += f'?manifestation__id__exact={obj.manifestation.id}'
        
        return response
    
    # Custom display methods
    def indented_title_short(self, obj):
        """عنوان کوتاه (30 کاراکتر) برای list display."""
        content = obj.content[:30] if obj.content else '-'
        if len(obj.content) > 30:
            content += '...'
        return format_html('<span style="font-weight: normal; font-size: 13px; white-space: nowrap;">{}</span>', content)
    indented_title_short.short_description = 'عنوان'
    
    def is_active_display(self, obj):
        """نمایش وضعیت فعال بودن بر اساس تاریخ انقضا."""
        if obj.is_active:
            return format_html('<span style="color: green; font-size: 16px; display: inline-block; width: 25px; text-align: center;">✓</span>')
        else:
            return format_html('<span style="color: red; font-size: 16px; display: inline-block; width: 25px; text-align: center;">✗</span>')
    is_active_display.short_description = 'معتبر'
    is_active_display.admin_order_field = 'valid_to'
    
    def unit_type_display(self, obj):
        """نمایش نوع واحد با عرض کمتر."""
        value = obj.get_unit_type_display() if obj.unit_type else '-'
        return format_html('<span style="display: inline-block; width: 40px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; padding: 0 2px; font-size: 12px;">{}</span>', value)
    unit_type_display.short_description = 'واحد'
    unit_type_display.admin_order_field = 'unit_type'
    
    def order_index_display(self, obj):
        """نمایش ترتیب با عرض کمتر."""
        value = obj.order_index if obj.order_index is not None else '-'
        return format_html('<span style="display: inline-block; width: 30px; text-align: center; padding: 0 2px; font-size: 12px;">{}</span>', value)
    order_index_display.short_description = 'ترتیب'
    order_index_display.admin_order_field = 'order_index'
    
    def chunk_display(self, obj):
        """نمایش تعداد چانک‌ها."""
        count = obj.chunks.count() if hasattr(obj, 'chunks') else 0
        color = 'green' if count > 0 else '#999'
        return format_html('<span style="display: inline-block; width: 30px; text-align: center; color: {}; padding: 0 2px; font-size: 12px;">{}</span>', color, count)
    chunk_display.short_description = 'چانک'
    chunk_display.admin_order_field = 'chunks__count'
