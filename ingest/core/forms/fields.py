"""
Jalali date/datetime form fields.
"""
from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from ingest.core.forms.widgets import JalaliDateInput, JalaliDateTimeInput, JalaliTimeInput
from ingest.core.jalali import parse_jalali_date, parse_jalali_datetime, english_digits


class JalaliDateField(forms.DateField):
    """
    Date field that accepts Jalali date input and converts to Gregorian.
    """
    widget = JalaliDateInput
    default_error_messages = {
        'invalid': _('تاریخ وارد شده معتبر نیست. لطفاً از فرمت 1402/01/15 استفاده کنید.'),
    }
    
    def __init__(self, *args, **kwargs):
        # Set default input formats for Jalali
        if 'input_formats' not in kwargs:
            kwargs['input_formats'] = [
                '%Y/%m/%d',  # 1402/01/15
                '%Y-%m-%d',  # 1402-01-15
                '%d/%m/%Y',  # 15/01/1402
            ]
        super().__init__(*args, **kwargs)
    
    def to_python(self, value):
        """
        Convert Jalali date string to Gregorian date object.
        """
        if value in self.empty_values:
            return None
        
        if isinstance(value, str):
            # Convert Persian digits to English
            value = english_digits(value.strip())
            
            # Try to parse as Jalali date
            parsed_date = parse_jalali_date(value)
            if parsed_date:
                return parsed_date
            
            # If Jalali parsing fails, try standard Django parsing
            try:
                return super().to_python(value)
            except ValidationError:
                pass
        
        # If it's already a date object, return as-is
        if hasattr(value, 'year') and hasattr(value, 'month') and hasattr(value, 'day'):
            return value
        
        raise ValidationError(self.error_messages['invalid'], code='invalid')
    
    def prepare_value(self, value):
        """
        Convert date object to Jalali string for display.
        """
        if value is None:
            return ''
        
        # Import here to avoid circular imports
        from ingest.core.jalali import to_jalali_date
        
        if hasattr(value, 'year') and hasattr(value, 'month') and hasattr(value, 'day'):
            return to_jalali_date(value)
        
        return str(value)


class JalaliDateTimeField(forms.DateTimeField):
    """
    DateTime field that accepts Jalali datetime input and converts to Gregorian UTC.
    """
    widget = JalaliDateTimeInput
    default_error_messages = {
        'invalid': _('تاریخ و زمان وارد شده معتبر نیست. لطفاً از فرمت 1402/01/15 14:30 استفاده کنید.'),
    }
    
    def __init__(self, *args, **kwargs):
        # Set default input formats for Jalali
        if 'input_formats' not in kwargs:
            kwargs['input_formats'] = [
                '%Y/%m/%d %H:%M',     # 1402/01/15 14:30
                '%Y/%m/%d %H:%M:%S',  # 1402/01/15 14:30:45
                '%Y-%m-%d %H:%M',     # 1402-01-15 14:30
                '%Y-%m-%d %H:%M:%S',  # 1402-01-15 14:30:45
            ]
        super().__init__(*args, **kwargs)
    
    def to_python(self, value):
        """
        Convert Jalali datetime string to timezone-aware Gregorian datetime in UTC.
        """
        if value in self.empty_values:
            return None
        
        if isinstance(value, str):
            # Convert Persian digits to English
            value = english_digits(value.strip())
            
            # Try to parse as Jalali datetime
            parsed_datetime = parse_jalali_datetime(value)
            if parsed_datetime:
                return parsed_datetime
            
            # If Jalali parsing fails, try standard Django parsing
            try:
                return super().to_python(value)
            except ValidationError:
                pass
        
        # If it's already a datetime object, return as-is
        if hasattr(value, 'year') and hasattr(value, 'hour'):
            return value
        
        raise ValidationError(self.error_messages['invalid'], code='invalid')
    
    def prepare_value(self, value):
        """
        Convert datetime object to Jalali string for display.
        """
        if value is None:
            return ''
        
        # Import here to avoid circular imports
        from ingest.core.jalali import to_jalali_datetime
        
        if hasattr(value, 'year') and hasattr(value, 'hour'):
            return to_jalali_datetime(value)
        
        return str(value)


class JalaliTimeField(forms.TimeField):
    """
    Time field with Persian digit support.
    """
    widget = JalaliTimeInput
    
    def to_python(self, value):
        """
        Convert time string with Persian digits to time object.
        """
        if value in self.empty_values:
            return None
        
        if isinstance(value, str):
            # Convert Persian digits to English
            value = english_digits(value.strip())
        
        return super().to_python(value)
