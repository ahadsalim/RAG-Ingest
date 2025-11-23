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
    extra = 1
    fields = ('vocabulary_term', 'weight')
    autocomplete_fields = ['vocabulary_term']
    verbose_name = 'برچسب'
    verbose_name_plural = 'برچسب‌ها'


class LUnitAdmin(SimpleJalaliAdminMixin, MPTTModelAdmin, SimpleHistoryAdmin):
    """
    Admin برای LUnit با رابط کاربری ساده و بهینه.
    """
    form = LUnitForm
    
    # List display
    list_display = ('indented_title_short', 'unit_type', 'order_index', 'chunk_display', 'jalali_created_at_display')
    list_filter = ('unit_type', 'created_at')
    search_fields = ('content', 'path_label', 'number')
    mptt_level_indent = 20
    readonly_fields = ('path_label', 'created_at', 'updated_at')
    list_per_page = 100
    
    # MPTT settings
    mptt_indent_field = "indented_title_short"
    
    # Inlines
    inlines = [LegalUnitVocabularyTermInlineSimple]
    
    # Fieldsets برای layout بهتر
    fieldsets = (
        (None, {
            'fields': (('parent', 'unit_type'), ('order_index', 'number'), 'content')
        }),
        ('تاریخ‌های اعتبار', {
            'fields': (('valid_from', 'valid_to'),),
            'description': '<p style="color: #666;">خالی گذاشتن فیلد "تاریخ پایان اعتبار" به معنی بدون تاریخ انقضا است.</p>'
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
        """
        query = request.GET.get('q', '').strip()
        manifestation_id = request.GET.get('manifestation_id', '')
        
        if not query or not manifestation_id:
            return JsonResponse({'results': []})
        
        # جستجو در والدها
        parents = LegalUnit.objects.filter(
            manifestation_id=manifestation_id
        ).filter(
            Q(number__icontains=query) |
            Q(content__icontains=query) |
            Q(unit_type__icontains=query)
        ).only('id', 'unit_type', 'number', 'content').order_by('order_index', 'number')[:20]
        
        results = []
        for parent in parents:
            results.append({
                'id': str(parent.id),
                'type': parent.get_unit_type_display(),
                'number': parent.number or '',
                'content': parent.content[:50] if parent.content else ''
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
    
    # حذف formfield_for_foreignkey چون از autocomplete استفاده می‌کنیم
    
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
        """عنوان کوتاه (40 کاراکتر) برای list display."""
        content = obj.content[:40] if obj.content else '-'
        if len(obj.content) > 40:
            content += '...'
        return format_html('<span style="font-weight: normal; font-size: 13px;">{}</span>', content)
    indented_title_short.short_description = 'عنوان'
    
    def chunk_display(self, obj):
        """نمایش تعداد چانک‌ها."""
        count = obj.chunks.count() if hasattr(obj, 'chunks') else 0
        if count > 0:
            return format_html('<span style="color: green;">{}</span>', count)
        return format_html('<span style="color: #999;">0</span>')
    chunk_display.short_description = 'چانک'
    chunk_display.admin_order_field = 'chunks__count'
