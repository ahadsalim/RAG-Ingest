"""
Jalali template filters for uniform date display across the project.
"""
from django import template
from django.utils.safestring import mark_safe
from ingest.core.jalali import (
    to_jalali_date, 
    to_jalali_datetime, 
    format_jalali_verbose,
    persian_digits,
    english_digits
)

register = template.Library()


@register.filter
def jalali(value):
    """
    Convert date to Jalali format.
    
    Usage: {{ obj.some_date|jalali }}
    """
    if value is None:
        return ""
    return to_jalali_date(value)


@register.filter
def jalali_datetime(value, include_timezone=False):
    """
    Convert datetime to Jalali format.
    
    Usage: {{ obj.created_at|jalali_datetime }}
           {{ obj.created_at|jalali_datetime:True }}
    """
    if value is None:
        return ""
    return to_jalali_datetime(value, include_timezone=include_timezone)


@register.filter
def jalali_verbose(value):
    """
    Convert date to verbose Jalali format.
    
    Usage: {{ obj.some_date|jalali_verbose }}
    Output: "پنج‌شنبه ۱۵ فروردین ۱۴۰۲"
    """
    if value is None:
        return ""
    return format_jalali_verbose(value)


@register.filter
def persian_digits(value):
    """
    Convert English digits to Persian digits.
    
    Usage: {{ "123"|persian_digits }}
    Output: "۱۲۳"
    """
    if value is None:
        return ""
    return persian_digits(str(value))


@register.filter
def english_digits(value):
    """
    Convert Persian digits to English digits.
    
    Usage: {{ "۱۲۳"|english_digits }}
    Output: "123"
    """
    if value is None:
        return ""
    return english_digits(str(value))


@register.simple_tag
def jalali_now():
    """
    Get current datetime in Jalali format.
    
    Usage: {% jalali_now %}
    """
    from ingest.core.jalali import now_jalali
    return now_jalali()


@register.simple_tag
def jalali_today():
    """
    Get current date in Jalali format.
    
    Usage: {% jalali_today %}
    """
    from ingest.core.jalali import today_jalali
    return today_jalali()


@register.inclusion_tag('core/jalali_date_display.html')
def jalali_date_display(value, show_weekday=False, show_verbose=False):
    """
    Render a date with Jalali formatting options.
    
    Usage: {% jalali_date_display obj.created_at show_weekday=True %}
    """
    return {
        'value': value,
        'jalali_date': to_jalali_date(value) if value else "",
        'jalali_verbose': format_jalali_verbose(value) if value and show_verbose else "",
        'show_weekday': show_weekday,
        'show_verbose': show_verbose,
    }


@register.inclusion_tag('core/jalali_datetime_display.html')
def jalali_datetime_display(value, show_timezone=False, show_verbose=False):
    """
    Render a datetime with Jalali formatting options.
    
    Usage: {% jalali_datetime_display obj.created_at show_timezone=True %}
    """
    return {
        'value': value,
        'jalali_datetime': to_jalali_datetime(value, include_timezone=show_timezone) if value else "",
        'jalali_verbose': format_jalali_verbose(value) if value and show_verbose else "",
        'show_timezone': show_timezone,
        'show_verbose': show_verbose,
    }
