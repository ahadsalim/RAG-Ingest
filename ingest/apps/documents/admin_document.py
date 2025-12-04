"""
Admin یکپارچه برای ثبت سند حقوقی
ادغام InstrumentWork + InstrumentExpression + InstrumentManifestation در یک فرم
"""
from django.contrib import admin
from django.db import transaction
from django import forms
from django.utils.html import format_html
from django.urls import reverse
from simple_history.admin import SimpleHistoryAdmin

from ingest.core.admin_mixins import JalaliAdminMixin as SimpleJalaliAdminMixin
from ingest.admin import admin_site
from .models import (
    InstrumentWork, InstrumentExpression, InstrumentManifestation,
    FileAsset
)
from .enums import DocumentType, ConsolidationLevel


class UnifiedDocumentForm(forms.ModelForm):
    """
    فرم یکپارچه برای ثبت سند حقوقی جدید.
    همه فیلدهای Work, Expression و Manifestation در یک فرم.
    """
    
    # === فیلدهای Work ===
    title_official = forms.CharField(
        max_length=500,
        label='عنوان رسمی سند',
        widget=forms.TextInput(attrs={'class': 'vLargeTextField', 'style': 'width: 100%;'})
    )
    doc_type = forms.ChoiceField(
        choices=DocumentType.choices,
        label='نوع سند',
        initial=DocumentType.LAW
    )
    jurisdiction = forms.ModelChoiceField(
        queryset=None,  # Set in __init__
        label='حوزه قضایی'
    )
    authority = forms.ModelChoiceField(
        queryset=None,  # Set in __init__
        label='مرجع صادرکننده'
    )
    subject_summary = forms.CharField(
        required=False,
        label='خلاصه موضوع',
        widget=forms.Textarea(attrs={'rows': 3})
    )
    
    # === فیلدهای Expression ===
    language = forms.ModelChoiceField(
        queryset=None,  # Set in __init__
        required=False,
        label='زبان'
    )
    consolidation_level = forms.ChoiceField(
        choices=ConsolidationLevel.choices,
        label='سطح تلفیق',
        initial=ConsolidationLevel.BASE
    )
    expression_date = forms.DateField(
        required=False,
        label='تاریخ تصویب/ابلاغ',
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    
    # === فیلدهای Manifestation ===
    publication_date = forms.DateField(
        label='تاریخ انتشار',
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    official_gazette_name = forms.CharField(
        max_length=200,
        required=False,
        label='نام روزنامه رسمی'
    )
    gazette_issue_no = forms.CharField(
        max_length=50,
        required=False,
        label='شماره نامه'
    )
    page_start = forms.IntegerField(
        required=False,
        label='صفحه شروع'
    )
    source_url = forms.URLField(
        required=False,
        label='URL منبع'
    )
    repeal_status = forms.ChoiceField(
        choices=InstrumentManifestation.RepealStatus.choices,
        label='وضعیت سند',
        initial=InstrumentManifestation.RepealStatus.IN_FORCE
    )
    in_force_from = forms.DateField(
        required=False,
        label='اجرا از تاریخ',
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    in_force_to = forms.DateField(
        required=False,
        label='اجرا تا تاریخ',
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    
    class Meta:
        model = InstrumentManifestation
        fields = []  # We handle all fields manually
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Import models for querysets
        from ingest.apps.masterdata.models import Jurisdiction, IssuingAuthority, Language
        
        self.fields['jurisdiction'].queryset = Jurisdiction.objects.all()
        self.fields['authority'].queryset = IssuingAuthority.objects.all()
        self.fields['language'].queryset = Language.objects.all()
        
        # اگر در حالت edit هستیم، فیلدها را پر کن
        if self.instance and self.instance.pk:
            manifestation = self.instance
            if manifestation.expr:
                expression = manifestation.expr
                work = expression.work
                
                # پر کردن فیلدهای Work
                self.fields['title_official'].initial = work.title_official
                self.fields['doc_type'].initial = work.doc_type
                self.fields['jurisdiction'].initial = work.jurisdiction
                self.fields['authority'].initial = work.authority
                self.fields['subject_summary'].initial = work.subject_summary
                
                # پر کردن فیلدهای Expression
                self.fields['language'].initial = expression.language
                self.fields['consolidation_level'].initial = expression.consolidation_level
                self.fields['expression_date'].initial = expression.expression_date
            
            # پر کردن فیلدهای Manifestation
            self.fields['publication_date'].initial = manifestation.publication_date
            self.fields['official_gazette_name'].initial = manifestation.official_gazette_name
            self.fields['gazette_issue_no'].initial = manifestation.gazette_issue_no
            self.fields['page_start'].initial = manifestation.page_start
            self.fields['source_url'].initial = manifestation.source_url
            self.fields['repeal_status'].initial = manifestation.repeal_status
            self.fields['in_force_from'].initial = manifestation.in_force_from
            self.fields['in_force_to'].initial = manifestation.in_force_to
    
    def clean(self):
        cleaned_data = super().clean()
        
        # Validation: اگر وضعیت لغو شده، تاریخ پایان الزامی است
        if cleaned_data.get('repeal_status') == InstrumentManifestation.RepealStatus.REPEALED:
            if not cleaned_data.get('in_force_to'):
                self.add_error('in_force_to', 'برای اسناد لغو شده، تعیین تاریخ پایان اجرا الزامی است.')
        
        return cleaned_data


class FileAssetInlineForDocument(admin.TabularInline):
    """Inline برای فایل‌های پیوست سند."""
    model = FileAsset
    extra = 1
    fields = ('file', 'description')
    readonly_fields = ('filename', 'formatted_size', 'uploaded_by')
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('uploaded_by')


class UnifiedDocumentAdmin(SimpleJalaliAdminMixin, SimpleHistoryAdmin):
    """
    Admin یکپارچه برای مدیریت اسناد حقوقی.
    ایجاد Work + Expression + Manifestation در یک مرحله.
    """
    form = UnifiedDocumentForm
    
    list_display = (
        'get_title', 
        'get_doc_type',
        'publication_date', 
        'repeal_status', 
        'get_unit_count',
        'jalali_created_at_display'
    )
    list_filter = ('repeal_status', 'publication_date', 'created_at')
    search_fields = ('expr__work__title_official', 'official_gazette_name')
    readonly_fields = ('id', 'checksum_sha256', 'retrieval_date', 'created_at', 'updated_at')
    inlines = [FileAssetInlineForDocument]
    
    fieldsets = (
        ('اطلاعات سند', {
            'fields': ('title_official', 'doc_type', 'jurisdiction', 'authority'),
            'description': 'اطلاعات اصلی سند حقوقی'
        }),
        ('نسخه و زبان', {
            'fields': ('language', 'consolidation_level', 'expression_date'),
            'classes': ('collapse',),
        }),
        ('اطلاعات انتشار', {
            'fields': ('publication_date', 'official_gazette_name', 'gazette_issue_no', 'page_start', 'source_url'),
        }),
        ('وضعیت اجرا', {
            'fields': ('repeal_status', 'in_force_from', 'in_force_to'),
        }),
        ('توضیحات', {
            'fields': ('subject_summary',),
            'classes': ('collapse',),
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'expr', 'expr__work', 'expr__work__jurisdiction', 
            'expr__work__authority', 'expr__language'
        ).prefetch_related('units')
    
    def get_title(self, obj):
        """نمایش عنوان سند."""
        if obj.expr and obj.expr.work:
            return obj.expr.work.title_official
        return '-'
    get_title.short_description = 'عنوان سند'
    get_title.admin_order_field = 'expr__work__title_official'
    
    def get_doc_type(self, obj):
        """نمایش نوع سند."""
        if obj.expr and obj.expr.work:
            return obj.expr.work.get_doc_type_display()
        return '-'
    get_doc_type.short_description = 'نوع'
    
    def get_unit_count(self, obj):
        """تعداد بندها."""
        count = obj.units.count()
        if count > 0:
            url = reverse('admin:documents_lunit_changelist') + f'?manifestation__id__exact={obj.id}'
            return format_html('<a href="{}">{} بند</a>', url, count)
        return '0'
    get_unit_count.short_description = 'بندها'
    
    @transaction.atomic
    def save_model(self, request, obj, form, change):
        """
        ذخیره یکپارچه: ابتدا Work، سپس Expression، سپس Manifestation.
        """
        cleaned = form.cleaned_data
        
        if change and obj.pk:
            # حالت Edit: بروزرسانی موجودی‌ها
            manifestation = obj
            expression = manifestation.expr
            work = expression.work
            
            # بروزرسانی Work
            work.title_official = cleaned['title_official']
            work.doc_type = cleaned['doc_type']
            work.jurisdiction = cleaned['jurisdiction']
            work.authority = cleaned['authority']
            work.subject_summary = cleaned.get('subject_summary', '')
            work.save()
            
            # بروزرسانی Expression
            expression.language = cleaned.get('language')
            expression.consolidation_level = cleaned['consolidation_level']
            expression.expression_date = cleaned.get('expression_date')
            expression.save()
            
            # بروزرسانی Manifestation
            manifestation.publication_date = cleaned['publication_date']
            manifestation.official_gazette_name = cleaned.get('official_gazette_name', '')
            manifestation.gazette_issue_no = cleaned.get('gazette_issue_no', '')
            manifestation.page_start = cleaned.get('page_start')
            manifestation.source_url = cleaned.get('source_url', '')
            manifestation.repeal_status = cleaned['repeal_status']
            manifestation.in_force_from = cleaned.get('in_force_from')
            manifestation.in_force_to = cleaned.get('in_force_to')
            manifestation.save()
            
        else:
            # حالت Add: ایجاد جدید
            # 1. ایجاد Work
            work = InstrumentWork.objects.create(
                title_official=cleaned['title_official'],
                doc_type=cleaned['doc_type'],
                jurisdiction=cleaned['jurisdiction'],
                authority=cleaned['authority'],
                subject_summary=cleaned.get('subject_summary', '')
            )
            
            # 2. ایجاد Expression
            expression = InstrumentExpression.objects.create(
                work=work,
                language=cleaned.get('language'),
                consolidation_level=cleaned['consolidation_level'],
                expression_date=cleaned.get('expression_date')
            )
            
            # 3. ایجاد Manifestation
            obj.expr = expression
            obj.publication_date = cleaned['publication_date']
            obj.official_gazette_name = cleaned.get('official_gazette_name', '')
            obj.gazette_issue_no = cleaned.get('gazette_issue_no', '')
            obj.page_start = cleaned.get('page_start')
            obj.source_url = cleaned.get('source_url', '')
            obj.repeal_status = cleaned['repeal_status']
            obj.in_force_from = cleaned.get('in_force_from')
            obj.in_force_to = cleaned.get('in_force_to')
            obj.save()
    
    def save_formset(self, request, form, formset, change):
        """Handle FileAsset inline."""
        if formset.model == FileAsset:
            instances = formset.save(commit=False)
            for instance in instances:
                if not instance.pk:
                    instance.uploaded_by = request.user
                instance.save()
            formset.save_m2m()
        else:
            super().save_formset(request, form, formset, change)
    
    def add_view(self, request, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context['title'] = 'افزودن سند حقوقی جدید'
        return super().add_view(request, form_url, extra_context)
    
    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context['title'] = 'ویرایش سند حقوقی'
        return super().change_view(request, object_id, form_url, extra_context)


# ایجاد یک Proxy Model برای نمایش جداگانه در admin
class Document(InstrumentManifestation):
    """
    Proxy model برای نمایش یکپارچه سند حقوقی در admin.
    """
    class Meta:
        proxy = True
        verbose_name = 'سند حقوقی'
        verbose_name_plural = 'اسناد حقوقی'


# ثبت admin یکپارچه
admin_site.register(Document, UnifiedDocumentAdmin)
