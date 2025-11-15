"""
Jalali (Persian/Shamsi) date utilities for the Ingest project.
Provides conversion between Gregorian and Jalali dates with timezone support.
"""
import re
from datetime import datetime, date, time, tzinfo
from typing import Optional, Union
from django.utils import timezone as dj_tz
from django.conf import settings
import jdatetime

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None


# Jalali date formats
JALALI_DATE_FORMAT = "yyyy/MM/dd"
JALALI_DATETIME_FORMAT = "yyyy/MM/dd HH:mm"
JALALI_DATETIME_FULL_FORMAT = "yyyy/MM/dd HH:mm:ss"

# Persian month names
PERSIAN_MONTHS = [
    'فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور',
    'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند'
]

# Persian weekday names
PERSIAN_WEEKDAYS = [
    'شنبه', 'یکشنبه', 'دوشنبه', 'سه‌شنبه', 'چهارشنبه', 'پنج‌شنبه', 'جمعه'
]


def _get_display_tz() -> tzinfo:
    """
    Get the display timezone for Jalali date conversions.
    
    Returns:
        tzinfo object for the display timezone
    """
    from django.conf import settings
    tzname = getattr(settings, "DISPLAY_TIME_ZONE", None)
    if tzname and ZoneInfo is not None:
        try:
            return ZoneInfo(tzname)
        except Exception:
            pass
    return dj_tz.get_current_timezone()


def to_jalali_date(d: Union[date, datetime], format_str: str = None) -> str:
    """
    Convert a Gregorian date to Jalali string representation.
    
    Args:
        d: Gregorian date or datetime object
        format_str: Custom format string (default: yyyy/MM/dd)
    
    Returns:
        Jalali date string
    """
    if d is None:
        return ""
    
    if isinstance(d, datetime):
        # Convert to display timezone if it's a datetime
        if dj_tz.is_aware(d):
            d = dj_tz.localtime(d, _get_display_tz())
        d = d.date()
    
    # Convert to Jalali
    jalali_date = jdatetime.date.fromgregorian(date=d)
    
    # Format the date
    if format_str is None:
        format_str = JALALI_DATE_FORMAT
    
    # Replace format tokens
    formatted = format_str.replace('yyyy', str(jalali_date.year))
    formatted = formatted.replace('MM', f"{jalali_date.month:02d}")
    formatted = formatted.replace('dd', f"{jalali_date.day:02d}")
    
    return formatted


def to_jalali_datetime(dt: Optional[datetime], format_str: str = None, include_timezone: bool = False) -> str:
    """
    Convert a Gregorian datetime to Jalali string representation.
    
    Args:
        dt: Gregorian datetime object
        format_str: Custom format string (default: yyyy/MM/dd HH:mm)
        include_timezone: Whether to include timezone info
    
    Returns:
        Jalali datetime string
    """
    if dt is None:
        return "-"
    
    # Convert to display timezone
    local = dj_tz.localtime(dt, _get_display_tz())
    
    # Convert to Jalali
    jalali_dt = jdatetime.datetime.fromgregorian(datetime=local)
    
    # Format the datetime
    if format_str is None:
        format_str = JALALI_DATETIME_FORMAT
    
    # Replace format tokens
    formatted = format_str.replace('yyyy', str(jalali_dt.year))
    formatted = formatted.replace('MM', f"{jalali_dt.month:02d}")
    formatted = formatted.replace('dd', f"{jalali_dt.day:02d}")
    formatted = formatted.replace('HH', f"{jalali_dt.hour:02d}")
    formatted = formatted.replace('mm', f"{jalali_dt.minute:02d}")
    formatted = formatted.replace('ss', f"{jalali_dt.second:02d}")
    
    # Add timezone info if requested
    if include_timezone and dj_tz.is_aware(dt):
        tz_name = local.tzinfo.tzname(local)
        tz_offset = local.strftime('%z')
        if tz_offset:
            tz_offset = f"{tz_offset[:3]}:{tz_offset[3:]}"
            formatted += f" ({tz_offset} {tz_name})"
    
    return formatted


def parse_jalali_date(date_str: str) -> Optional[date]:
    """
    Parse a Jalali date string to Gregorian date object.
    
    Args:
        date_str: Jalali date string (e.g., "1402/01/15")
    
    Returns:
        Gregorian date object or None if parsing fails
    """
    if not date_str or not date_str.strip():
        return None
    
    date_str = date_str.strip()
    
    # Support various formats
    patterns = [
        r'^(\d{4})/(\d{1,2})/(\d{1,2})$',  # 1402/1/15 or 1402/01/15
        r'^(\d{4})-(\d{1,2})-(\d{1,2})$',  # 1402-1-15 or 1402-01-15
        r'^(\d{1,2})/(\d{1,2})/(\d{4})$',  # 15/1/1402 or 15/01/1402
    ]
    
    for pattern in patterns:
        match = re.match(pattern, date_str)
        if match:
            groups = match.groups()
            
            # Determine year, month, day based on pattern
            if len(groups[0]) == 4:  # Year first
                year, month, day = int(groups[0]), int(groups[1]), int(groups[2])
            else:  # Day first
                day, month, year = int(groups[0]), int(groups[1]), int(groups[2])
            
            try:
                # Create Jalali date and convert to Gregorian
                jalali_date = jdatetime.date(year, month, day)
                return jalali_date.togregorian()
            except (ValueError, jdatetime.InvalidJalaliDate):
                continue
    
    return None


def parse_jalali_datetime(datetime_str: str, tz: Optional[tzinfo] = None) -> Optional[datetime]:
    """
    Parse a Jalali datetime string to Gregorian datetime object.
    
    Args:
        datetime_str: Jalali datetime string (e.g., "1402/01/15 14:30")
        tz: Timezone to apply (default: DISPLAY_TIME_ZONE)
    
    Returns:
        Timezone-aware Gregorian datetime object in UTC or None if parsing fails
    """
    if not datetime_str:
        return None
    
    try:
        jdt = jdatetime.datetime.strptime(datetime_str.strip(), "%Y/%m/%d %H:%M")
        gdt_naive: datetime = jdt.togregorian()
        local_tz = tz or _get_display_tz()
        gdt_local = dj_tz.make_aware(gdt_naive, local_tz)
        return gdt_local.astimezone(dj_tz.utc)
    except Exception:
        return None


def get_jalali_month_name(month: int) -> str:
    """
    Get Persian month name for given month number (1-12).
    
    Args:
        month: Month number (1-12)
    
    Returns:
        Persian month name
    """
    if 1 <= month <= 12:
        return PERSIAN_MONTHS[month - 1]
    return str(month)


def get_jalali_weekday_name(weekday: int) -> str:
    """
    Get Persian weekday name for given weekday number (0-6, Saturday=0).
    
    Args:
        weekday: Weekday number (0-6, Saturday=0)
    
    Returns:
        Persian weekday name
    """
    if 0 <= weekday <= 6:
        return PERSIAN_WEEKDAYS[weekday]
    return str(weekday)


def format_jalali_verbose(d: Union[date, datetime]) -> str:
    """
    Format date/datetime in verbose Persian format.
    
    Args:
        d: Date or datetime object
    
    Returns:
        Verbose Jalali string (e.g., "پنج‌شنبه ۱۵ فروردین ۱۴۰۲")
    """
    if d is None:
        return ""
    
    if isinstance(d, datetime):
        if dj_tz.is_aware(d):
            d = dj_tz.localtime(d, _get_display_tz())
        d = d.date()
    
    # Convert to Jalali
    jalali_date = jdatetime.date.fromgregorian(date=d)
    
    # Get weekday (jdatetime uses Monday=0, we need Saturday=0)
    weekday = (jalali_date.weekday() + 2) % 7
    weekday_name = get_jalali_weekday_name(weekday)
    
    # Format: "پنج‌شنبه ۱۵ فروردین ۱۴۰۲"
    day_persian = persian_digits(str(jalali_date.day))
    year_persian = persian_digits(str(jalali_date.year))
    month_name = get_jalali_month_name(jalali_date.month)
    
    return f"{weekday_name} {day_persian} {month_name} {year_persian}"


def persian_digits(text: str) -> str:
    """
    Convert English digits to Persian digits.
    
    Args:
        text: Text containing English digits
    
    Returns:
        Text with Persian digits
    """
    persian_digit_map = {
        '0': '۰', '1': '۱', '2': '۲', '3': '۳', '4': '۴',
        '5': '۵', '6': '۶', '7': '۷', '8': '۸', '9': '۹'
    }
    
    for english, persian in persian_digit_map.items():
        text = text.replace(english, persian)
    
    return text


def english_digits(text: str) -> str:
    """
    Convert Persian digits to English digits.
    
    Args:
        text: Text containing Persian digits
    
    Returns:
        Text with English digits
    """
    english_digit_map = {
        '۰': '0', '۱': '1', '۲': '2', '۳': '3', '۴': '4',
        '۵': '5', '۶': '6', '۷': '7', '۸': '8', '۹': '9'
    }
    
    for persian, english in english_digit_map.items():
        text = text.replace(persian, english)
    
    return text


def now_jalali() -> str:
    """
    Get current datetime in Jalali format.
    
    Returns:
        Current datetime in Jalali format
    """
    now = dj_tz.now()
    return to_jalali_datetime(now, include_timezone=True)


def today_jalali() -> str:
    """
    Get current date in Jalali format.
    
    Returns:
        Current date in Jalali format
    """
    today = dj_tz.now().date()
    return to_jalali_date(today)
