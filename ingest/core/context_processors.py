"""
Context processors for exposing Jalali and timezone settings to templates.
"""
from django.conf import settings


def jalali_context(request):
    """
    Add Jalali and timezone context to all templates.
    
    Provides:
    - DISPLAY_TIME_ZONE: Current display timezone
    - DISPLAY_LOCALE: Current display locale
    - DISPLAY_CALENDAR: Calendar type (jalali)
    - JALALI_DATE_FORMAT: Default Jalali date format
    - JALALI_DATETIME_FORMAT: Default Jalali datetime format
    """
    from ingest.core.jalali import JALALI_DATE_FORMAT, JALALI_DATETIME_FORMAT
    
    return {
        'DISPLAY_TIME_ZONE': getattr(settings, 'DISPLAY_TIME_ZONE', 'Asia/Tehran'),
        'DISPLAY_LOCALE': getattr(settings, 'DISPLAY_LOCALE', 'fa_IR'),
        'DISPLAY_CALENDAR': getattr(settings, 'DISPLAY_CALENDAR', 'jalali'),
        'JALALI_DATE_FORMAT': JALALI_DATE_FORMAT,
        'JALALI_DATETIME_FORMAT': JALALI_DATETIME_FORMAT,
    }
