"""
Django forms for documents app with Jalali date support.
"""

from django import forms
from django.utils import timezone
from .models import FileAsset, LegalUnitChange

# Import unified Jalali fields
try:
    from ingest.core.forms.fields import JalaliDateField, JalaliDateTimeField
    from ingest.core.forms.widgets import JalaliDateInput as JalaliDateWidget, JalaliDateTimeInput as JalaliDateTimeWidget
    JALALI_AVAILABLE = True
except ImportError:
    # Fallback to regular Django fields if core not available
    from django.forms import DateField as JalaliDateField
    from django.forms import DateTimeField as JalaliDateTimeField
    from django.forms.widgets import DateInput as JalaliDateWidget
    from django.forms.widgets import DateTimeInput as JalaliDateTimeWidget
    JALALI_AVAILABLE = False

from .models import (
    InstrumentExpression, 
    InstrumentManifestation, 
    InstrumentRelation,
    LegalUnit,
    LUnit
)
from .widgets import ParentAutocompleteWidget


class InstrumentExpressionForm(forms.ModelForm):
    """ModelForm for InstrumentExpression."""
    
    expression_date = JalaliDateField(
        label='تاریخ نسخه/تصویب',
        required=False,
        help_text='فرمت: 1404/07/05' if JALALI_AVAILABLE else 'فرمت: YYYY-MM-DD'
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if JALALI_AVAILABLE:
            self.fields['expression_date'].widget = JalaliDateWidget()
    
    class Meta:
        model = InstrumentExpression
        fields = '__all__'


class InstrumentManifestationForm(forms.ModelForm):
    """ModelForm for InstrumentManifestation."""
    
    publication_date = JalaliDateField(
        label='تاریخ انتشار ' if JALALI_AVAILABLE else 'تاریخ انتشار',
        required=True,
        help_text='فرمت: 1404/07/05' if JALALI_AVAILABLE else 'فرمت: YYYY-MM-DD'
    )
    
    in_force_from = JalaliDateField(
        label='اجرا از تاریخ ' if JALALI_AVAILABLE else 'اجرا از تاریخ',
        required=False,
        help_text='فرمت: 1404/07/05' if JALALI_AVAILABLE else 'فرمت: YYYY-MM-DD'
    )
    
    in_force_to = JalaliDateField(
        label='اجرا تا تاریخ ' if JALALI_AVAILABLE else 'اجرا تا تاریخ',
        required=False,
        help_text='در صورتی که وضعیت سند "لغو یا منسوخ شده" باشد، این فیلد الزامی است. فرمت: 1404/07/05' if JALALI_AVAILABLE else 'در صورتی که وضعیت سند "لغو یا منسوخ شده" باشد، این فیلد الزامی است. فرمت: YYYY-MM-DD'
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if JALALI_AVAILABLE:
            # Only set widgets for fields that exist in the form
            if 'publication_date' in self.fields:
                self.fields['publication_date'].widget = JalaliDateWidget()
            if 'in_force_from' in self.fields:
                self.fields['in_force_from'].widget = JalaliDateWidget()
            if 'in_force_to' in self.fields:
                self.fields['in_force_to'].widget = JalaliDateWidget()
    
    class Meta:
        model = InstrumentManifestation
        exclude = ['retrieval_date']  # Exclude auto fields
    
    def clean(self):
        """Custom validation to ensure in_force_to is provided for repealed documents."""
        cleaned_data = super().clean()
        repeal_status = cleaned_data.get('repeal_status')
        in_force_to = cleaned_data.get('in_force_to')
        
        # Safe validation - only check if repeal_status exists and has specific value
        try:
            if hasattr(InstrumentManifestation, 'RepealStatus') and repeal_status:
                if str(repeal_status).upper() in ['REPEALED', 'REVOKED', 'CANCELLED'] and not in_force_to:
                    self.add_error('in_force_to', 'برای اسناد لغو شده، تعیین تاریخ پایان اجرا الزامی است.')
        except Exception:
            # Skip validation if there's any issue with RepealStatus
            pass
        
        return cleaned_data


class InstrumentRelationForm(forms.ModelForm):
    """ModelForm for InstrumentRelation with Jalali date support."""
    
    effective_date = JalaliDateField(
        label='تاریخ اجرا ' if JALALI_AVAILABLE else 'تاریخ اجرا',
        required=False,
        help_text='فرمت: 1404/07/05' if JALALI_AVAILABLE else 'فرمت: YYYY-MM-DD'
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if JALALI_AVAILABLE:
            self.fields['effective_date'].widget = JalaliDateWidget()
    
    class Meta:
        model = InstrumentRelation
        fields = '__all__'


class LegalUnitForm(forms.ModelForm):
    """ModelForm for LegalUnit with Jalali date support."""
    
    valid_from = JalaliDateField(
        label='تاریخ تصویب / اجرا ' if JALALI_AVAILABLE else 'تاریخ تصویب / اجرا',
        required=False,
        help_text='فرمت: 1402/01/15 - خالی گذاشتن به معنی استفاده از تاریخ انتشار سند است.' if JALALI_AVAILABLE else 'فرمت: YYYY-MM-DD'
    )
    
    valid_to = JalaliDateField(
        label='تاریخ پایان اعتبار ' if JALALI_AVAILABLE else 'تاریخ پایان اعتبار',
        required=False,
        help_text='فرمت: 1402/01/15 - خالی گذاشتن فیلد به معنی بدون تاریخ انقضا است.' if JALALI_AVAILABLE else 'فرمت: YYYY-MM-DD'
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if JALALI_AVAILABLE:
            self.fields['valid_from'].widget = JalaliDateWidget(attrs={'placeholder': '1404/07/05'})
            self.fields['valid_to'].widget = JalaliDateWidget(attrs={'placeholder': '1404/07/05'})
        
        # Make content field wider with larger textarea
        if 'content' in self.fields:
            self.fields['content'].widget = forms.Textarea(attrs={
                'rows': 10,
                'cols': 80,
                'style': 'width: 100%; max-width: 800px; font-family: "Vazirmatn", "Tahoma", sans-serif;'
            })
        
        # Filter parent field based on manifestation
        if 'parent' in self.fields:
            # غیرفعال کردن validation خودکار Django برای parent
            self.fields['parent'].required = False
            
            # If instance exists (editing), filter by its manifestation
            if self.instance and self.instance.pk and self.instance.manifestation:
                # فیلتر parent به LegalUnit های همان manifestation
                # استفاده از only() برای بهینه‌سازی
                self.fields['parent'].queryset = LegalUnit.objects.filter(
                    manifestation=self.instance.manifestation
                ).exclude(pk=self.instance.pk).only(
                    'id', 'number', 'unit_type', 'content', 'order_index'
                ).order_by('order_index', 'number')
            # If manifestation is set (from initial data), filter by it
            elif self.initial.get('manifestation') or ('manifestation' in self.fields and self.fields['manifestation'].initial):
                manifestation_id = self.initial.get('manifestation')
                if not manifestation_id and 'manifestation' in self.fields:
                    manifestation_id = self.fields['manifestation'].initial
                # تبدیل به string اگر UUID object است
                if hasattr(manifestation_id, 'hex'):
                    manifestation_id = str(manifestation_id)
                # استفاده از only() برای بهینه‌سازی
                if manifestation_id:
                    self.fields['parent'].queryset = LegalUnit.objects.filter(
                        manifestation_id=manifestation_id
                    ).only(
                        'id', 'number', 'unit_type', 'content', 'order_index'
                    ).order_by('order_index', 'number')
                else:
                    # اگر manifestation نداریم، همه را نشان بده
                    self.fields['parent'].queryset = LegalUnit.objects.all()
            else:
                # اگر manifestation نداریم، همه را نشان بده (برای validation)
                self.fields['parent'].queryset = LegalUnit.objects.all()
    
    def clean_parent(self):
        """
        Custom validation for parent field.
        استفاده از queryset فیلد برای جلوگیری از query اضافی.
        """
        # دریافت parent_id از داده‌های خام
        parent_id = self.data.get('parent')
        
        # اگر parent_id خالی است، parent را None برگردان
        if not parent_id:
            return None
        
        # استفاده از queryset فیلد (از cache) به جای query جدید
        try:
            parent = self.fields['parent'].queryset.get(pk=parent_id)
        except (LegalUnit.DoesNotExist, ValueError, AttributeError):
            # اگر queryset مشکل داشت، fallback به query مستقیم
            try:
                parent = LegalUnit.objects.get(pk=parent_id)
            except (LegalUnit.DoesNotExist, ValueError):
                raise forms.ValidationError(
                    'والد انتخاب شده معتبر نیست.'
                )
        
        # بررسی manifestation
        # ⭐ در edit mode از instance استفاده کن، نه cleaned_data
        if self.instance and self.instance.pk:
            manifestation = self.instance.manifestation
        else:
            manifestation = self.cleaned_data.get('manifestation')
        
        if parent and manifestation:
            # Check if parent belongs to the same manifestation
            if parent.manifestation != manifestation:
                raise forms.ValidationError(
                    'والد انتخاب شده باید متعلق به همان نسخه سند باشد.'
                )
            
            # Check for circular reference
            if self.instance and self.instance.pk and parent.pk == self.instance.pk:
                raise forms.ValidationError(
                    'یک واحد قانونی نمی‌تواند والد خودش باشد.'
                )
        
        return parent
    
    def clean_manifestation(self):
        """
        Prevent changing manifestation in edit mode.
        """
        manifestation = self.cleaned_data.get('manifestation')
        
        # در edit mode، manifestation نباید تغییر کند
        if self.instance and self.instance.pk and self.instance.manifestation:
            if manifestation != self.instance.manifestation:
                # اگر کاربر سعی کرد تغییر دهد، مقدار قبلی را برگردان
                return self.instance.manifestation
        
        return manifestation
    
    def clean(self):
        """Override clean to update parent queryset dynamically."""
        cleaned_data = super().clean()
        
        # ⭐ در edit mode از instance استفاده کن، نه cleaned_data
        if self.instance and self.instance.pk:
            manifestation = self.instance.manifestation
        else:
            manifestation = cleaned_data.get('manifestation')
        
        # Update parent queryset based on selected manifestation
        if manifestation and 'parent' in self.fields:
            valid_parents = LegalUnit.objects.filter(manifestation=manifestation)
            if self.instance and self.instance.pk:
                valid_parents = valid_parents.exclude(pk=self.instance.pk)
            
            # Update the queryset for validation
            self.fields['parent'].queryset = valid_parents
        
        return cleaned_data
    
    def save(self, commit=True):
        """Override save to set default valid_from from manifestation publication_date."""
        instance = super().save(commit=False)
        
        # اگر valid_from خالی است و manifestation موجود است، از publication_date استفاده کن
        if not instance.valid_from and instance.manifestation and hasattr(instance.manifestation, 'publication_date'):
            if instance.manifestation.publication_date:
                instance.valid_from = instance.manifestation.publication_date
        
        if commit:
            instance.save()
        return instance
    
    class Meta:
        model = LegalUnit
        fields = '__all__'


class LUnitForm(forms.ModelForm):
    """
    فرم بهینه شده برای LUnit با layout بهتر و تجربه کاربری ساده‌تر.
    """
    
    valid_from = JalaliDateField(
        label='تاریخ ابلاغ/اجرا',
        required=False,
        help_text='در صورت عدم ورود مقدار، تاریخ انتشار از سند اصلی درج خواهد شد.'
    )
    
    valid_to = JalaliDateField(
        label='تاریخ پایان اعتبار',
        required=False,
        help_text='خالی گذاشتن این فیلد به معنی بدون تاریخ انقضا است.'
    )
    
    def __init__(self, *args, **kwargs):
        # دریافت manifestation_id از kwargs
        self.manifestation_id = kwargs.pop('manifestation_id', None)
        
        super().__init__(*args, **kwargs)
        
        if JALALI_AVAILABLE:
            self.fields['valid_from'].widget = JalaliDateWidget(attrs={'placeholder': 'مثال: 1404/07/05'})
            self.fields['valid_to'].widget = JalaliDateWidget(attrs={'placeholder': 'مثال: 1404/07/05'})
        
        # تنظیمات فیلد محتوا - سطرهای بیشتر
        if 'content' in self.fields:
            self.fields['content'].widget = forms.Textarea(attrs={
                'rows': 20,
                'cols': 100,
                'style': 'width: 95%; font-family: "Vazirmatn", "Tahoma", sans-serif; font-size: 14px;'
            })
        
        # تنظیمات فیلدهای کوچک برای جا شدن در یک خط
        if 'unit_type' in self.fields:
            self.fields['unit_type'].widget.attrs['style'] = 'width: 200px; display: inline-block;'
        
        if 'number' in self.fields:
            self.fields['number'].widget.attrs['style'] = 'width: 100px;'
            self.fields['number'].widget.attrs['placeholder'] = 'مثال: 1'
        
        if 'order_index' in self.fields:
            self.fields['order_index'].widget.attrs['style'] = 'width: 80px;'
            self.fields['order_index'].widget.attrs['placeholder'] = '0'
        
        # parent widget در admin.get_form.CustomFormClass تنظیم می‌شود
    
    def clean_parent(self):
        """Validation برای parent field."""
        parent_id = self.data.get('parent')
        
        if not parent_id:
            return None
        
        # دریافت parent از دیتابیس (چون از autocomplete استفاده می‌کنیم)
        try:
            from .models import LegalUnit
            parent = LegalUnit.objects.get(pk=parent_id)
        except (LegalUnit.DoesNotExist, ValueError):
            raise forms.ValidationError('والد انتخاب شده معتبر نیست.')
        
        # تعیین manifestation
        if self.instance and self.instance.pk:
            manifestation = self.instance.manifestation
        else:
            manifestation = self.cleaned_data.get('manifestation')
        
        # بررسی manifestation
        if parent and manifestation:
            if parent.manifestation != manifestation:
                raise forms.ValidationError('والد انتخاب شده باید متعلق به همان سند باشد.')
            
            if self.instance and self.instance.pk and parent.pk == self.instance.pk:
                raise forms.ValidationError('یک بند نمی‌تواند والد خودش باشد.')
        
        return parent
    
    def clean(self):
        """Validation کلی."""
        cleaned_data = super().clean()
        # با autocomplete widget دیگر نیازی به update کردن queryset نیست
        return cleaned_data
    
    def save(self, commit=True):
        """ذخیره با تنظیمات پیش‌فرض."""
        instance = super().save(commit=False)
        
        # اگر valid_from خالی است، از publication_date استفاده کن
        if not instance.valid_from and instance.manifestation:
            if hasattr(instance.manifestation, 'publication_date') and instance.manifestation.publication_date:
                instance.valid_from = instance.manifestation.publication_date
        
        if commit:
            instance.save()
        return instance
    
    class Meta:
        model = LUnit
        exclude = ['id', 'created_at', 'updated_at', 'path_label', 'work', 'expr', 'eli_fragment', 'xml_id']
        # parent widget در admin.get_form تنظیم می‌شود


class FileAssetForm(forms.ModelForm):
    """Form for FileAsset with automatic uploaded_by handling."""
    
    class Meta:
        model = FileAsset
        fields = ['file', 'description', 'legal_unit', 'manifestation']
        
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
    def save(self, commit=True):
        instance = super().save(commit=False)
        if not instance.pk and self.user:  # Only on create
            instance.uploaded_by = self.user
        if commit:
            instance.save()
        return instance


class LegalUnitChangeForm(forms.ModelForm):
    """Form for LegalUnitChange with Jalali date support."""
    
    effective_date = JalaliDateField(
        label='تاریخ اجرای قانونی تغییر ' if JALALI_AVAILABLE else 'تاریخ اجرای قانونی تغییر',
        required=False,
        help_text='فرمت: 1404/07/05' if JALALI_AVAILABLE else 'فرمت: YYYY-MM-DD'
    )
    
    class Meta:
        model = LegalUnitChange
        fields = '__all__'
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if JALALI_AVAILABLE:
            self.fields['effective_date'].widget = JalaliDateWidget()
