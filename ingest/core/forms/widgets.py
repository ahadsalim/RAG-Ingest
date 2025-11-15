"""
Jalali date/datetime widgets for forms.
"""
from django import forms
from django.forms.widgets import Media
from django.utils.safestring import mark_safe


class JalaliDateInput(forms.TextInput):
    """
    Jalali date input widget with Persian datepicker.
    """
    input_type = 'text'
    
    def __init__(self, attrs=None, format=None):
        default_attrs = {
            'class': 'jalali-date-input form-control',
            'data-jalali': '1',
            'placeholder': '1403/01/15',
            'dir': 'ltr',
        }
        if attrs:
            default_attrs.update(attrs)
        super().__init__(default_attrs)
        self.format = format
    
    @property
    def media(self):
        return Media(
            css={
                'all': [
                    'vendor/persian-datepicker/persian-datepicker.min.css',
                    'css/jalali-widgets.css',
                ]
            },
            js=[
                'vendor/persian-date/persian-date.min.js',
                'vendor/persian-datepicker/persian-datepicker.min.js',
                'js/jalali-init.js',
            ]
        )


class JalaliDateTimeInput(forms.TextInput):
    """
    Jalali datetime input widget with Persian datepicker.
    """
    input_type = 'text'
    
    def __init__(self, attrs=None, format=None):
        default_attrs = {
            'class': 'jalali-datetime-input form-control',
            'data-jalali': '1',
            'data-timepicker': '1',
            'placeholder': '1403/01/15 14:30',
            'dir': 'ltr',
        }
        if attrs:
            default_attrs.update(attrs)
        super().__init__(default_attrs)
        self.format = format
    
    @property
    def media(self):
        return Media(
            css={
                'all': [
                    'vendor/persian-datepicker/persian-datepicker.min.css',
                    'css/jalali-widgets.css',
                ]
            },
            js=[
                'vendor/persian-date/persian-date.min.js',
                'vendor/persian-datepicker/persian-datepicker.min.js',
                'js/jalali-init.js',
            ]
        )


class JalaliTimeInput(forms.TimeInput):
    """
    Time input widget with Persian digits support.
    """
    
    def __init__(self, attrs=None, format=None):
        default_attrs = {
            'class': 'jalali-time-input',
            'placeholder': 'مثال: 14:30',
            'dir': 'ltr',
        }
        if attrs:
            default_attrs.update(attrs)
        super().__init__(default_attrs, format)
    
    @property
    def media(self):
        return Media(
            css={
                'all': ['css/jalali-widgets.css']
            },
            js=['js/jalali-init.js']
        )
