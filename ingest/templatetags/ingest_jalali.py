"""Custom template tags for Jalali date conversion in Ingest system."""
from django import template
from django.utils import timezone
import jdatetime

register = template.Library()


@register.filter
def jalali_date(value, format_string='%Y/%m/%d'):
    """Convert Gregorian date to Jalali date."""
    if not value:
        return ''
    
    try:
        # Convert to Tehran timezone if it's a datetime
        if hasattr(value, 'astimezone'):
            tehran_tz = timezone.get_current_timezone()
            value = value.astimezone(tehran_tz)
        
        # Convert to jdatetime
        if hasattr(value, 'date'):
            # It's a datetime object
            j_date = jdatetime.datetime.fromgregorian(
                datetime=value
            )
        else:
            # It's a date object
            j_date = jdatetime.date.fromgregorian(
                date=value
            )
        
        return j_date.strftime(format_string)
    except (ValueError, AttributeError, TypeError):
        return str(value)


@register.filter
def jalali_datetime(value, format_string='%Y/%m/%d %H:%M'):
    """Convert Gregorian datetime to Jalali datetime."""
    if not value:
        return ''
    
    try:
        # Convert to Tehran timezone
        if hasattr(value, 'astimezone'):
            tehran_tz = timezone.get_current_timezone()
            value = value.astimezone(tehran_tz)
        
        # Convert to jdatetime
        j_datetime = jdatetime.datetime.fromgregorian(
            datetime=value
        )
        
        return j_datetime.strftime(format_string)
    except (ValueError, AttributeError, TypeError):
        return str(value)


@register.filter
def jalali_short_date(value):
    """Convert to short Jalali date format."""
    return jalali_date(value, '%Y/%m/%d')


@register.filter
def jalali_long_date(value):
    """Convert to long Jalali date format with day name."""
    if not value:
        return ''
    
    try:
        # Convert to Tehran timezone if it's a datetime
        if hasattr(value, 'astimezone'):
            tehran_tz = timezone.get_current_timezone()
            value = value.astimezone(tehran_tz)
        
        # Convert to jdatetime
        if hasattr(value, 'date'):
            j_date = jdatetime.datetime.fromgregorian(datetime=value)
        else:
            j_date = jdatetime.date.fromgregorian(date=value)
        
        # Persian day names
        day_names = {
            0: 'شنبه',
            1: 'یکشنبه', 
            2: 'دوشنبه',
            3: 'سه‌شنبه',
            4: 'چهارشنبه',
            5: 'پنج‌شنبه',
            6: 'جمعه'
        }
        
        # Persian month names
        month_names = {
            1: 'فروردین', 2: 'اردیبهشت', 3: 'خرداد',
            4: 'تیر', 5: 'مرداد', 6: 'شهریور',
            7: 'مهر', 8: 'آبان', 9: 'آذر',
            10: 'دی', 11: 'بهمن', 12: 'اسفند'
        }
        
        day_name = day_names.get(j_date.weekday(), '')
        month_name = month_names.get(j_date.month, str(j_date.month))
        
        return f"{day_name} {j_date.day} {month_name} {j_date.year}"
    except (ValueError, AttributeError, TypeError):
        return str(value)


@register.filter
def time_ago_jalali(value):
    """Show time ago in Persian."""
    if not value:
        return ''
    
    try:
        now = timezone.now()
        if hasattr(value, 'astimezone'):
            tehran_tz = timezone.get_current_timezone()
            value = value.astimezone(tehran_tz)
            now = now.astimezone(tehran_tz)
        
        diff = now - value
        
        if diff.days > 0:
            if diff.days == 1:
                return 'دیروز'
            elif diff.days < 7:
                return f'{diff.days} روز پیش'
            elif diff.days < 30:
                weeks = diff.days // 7
                return f'{weeks} هفته پیش'
            elif diff.days < 365:
                months = diff.days // 30
                return f'{months} ماه پیش'
            else:
                years = diff.days // 365
                return f'{years} سال پیش'
        
        seconds = diff.seconds
        if seconds < 60:
            return 'همین الان'
        elif seconds < 3600:
            minutes = seconds // 60
            return f'{minutes} دقیقه پیش'
        else:
            hours = seconds // 3600
            return f'{hours} ساعت پیش'
            
    except (ValueError, AttributeError, TypeError):
        return str(value)
