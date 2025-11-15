"""
Custom API fields for Jalali date support.
"""

from rest_framework import serializers
import jdatetime


class JalaliDateTimeField(serializers.DateTimeField):
    """
    Custom serializer field that returns Jalali date format for API responses.
    """
    
    def to_representation(self, value):
        if not value:
            return None
        
        try:
            # Convert to Jalali date
            jalali_dt = jdatetime.datetime.fromgregorian(datetime=value)
            return jalali_dt.strftime('%Y/%m/%d %H:%M:%S')
        except Exception:
            # Fallback to original format
            return super().to_representation(value)


class JalaliDateField(serializers.DateField):
    """
    Custom serializer field that returns Jalali date format for API responses.
    """
    
    def to_representation(self, value):
        if not value:
            return None
        
        try:
            # Convert to Jalali date
            if hasattr(value, 'date'):
                # If it's a datetime, get the date part
                value = value.date()
            
            jalali_date = jdatetime.date.fromgregorian(date=value)
            return jalali_date.strftime('%Y/%m/%d')
        except Exception:
            # Fallback to original format
            return super().to_representation(value)
