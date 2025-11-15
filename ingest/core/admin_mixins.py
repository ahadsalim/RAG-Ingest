"""
Admin mixins for uniform Jalali date handling across the project.
"""
from django.contrib import admin
from django.db import models
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from ingest.core.forms.widgets import JalaliDateInput, JalaliDateTimeInput
from ingest.core.jalali import to_jalali_date, to_jalali_datetime, format_jalali_verbose


class JalaliAdminMixin(admin.ModelAdmin):
    """
    Base admin mixin that provides uniform Jalali date handling.
    
    Features:
    - Automatic Jalali widgets for date/datetime fields
    - Helper methods for Jalali display in list views
    - Consistent date formatting across admin
    """
    
    # Override form field widgets to use Jalali inputs
    formfield_overrides = {
        models.DateField: {'widget': JalaliDateInput},
        models.DateTimeField: {'widget': JalaliDateTimeInput},
    }
    
    def formfield_for_dbfield(self, db_field, request, **kwargs):
        """
        Override to ensure Jalali widgets are used for date fields.
        """
        if isinstance(db_field, models.DateField):
            kwargs['widget'] = JalaliDateInput
        elif isinstance(db_field, models.DateTimeField):
            kwargs['widget'] = JalaliDateTimeInput
        
        return super().formfield_for_dbfield(db_field, request, **kwargs)
    
    def _format_jalali_date(self, value, verbose=False):
        """
        Format a date value in Jalali format.
        
        Args:
            value: Date or datetime value
            verbose: Whether to use verbose format
        
        Returns:
            Formatted Jalali date string
        """
        if value is None:
            return "-"
        
        if verbose:
            return format_jalali_verbose(value)
        else:
            return to_jalali_date(value)
    
    def _format_jalali_datetime(self, value, include_timezone=False, verbose=False):
        """
        Format a datetime value in Jalali format.
        
        Args:
            value: Datetime value
            include_timezone: Whether to include timezone info
            verbose: Whether to use verbose format for date part
        
        Returns:
            Formatted Jalali datetime string
        """
        if value is None:
            return "-"
        
        if verbose:
            date_part = format_jalali_verbose(value)
            time_part = value.strftime('%H:%M')
            return f"{date_part} {time_part}"
        else:
            return to_jalali_datetime(value, include_timezone=include_timezone)
    
    def jalali_date_display(self, value):
        """
        Helper method to format a date value in Jalali format.
        Used by admin methods that need to display dates.
        
        Args:
            value: Date or datetime value
        
        Returns:
            Formatted Jalali date string
        """
        return self._format_jalali_date(value)
    
    # Common display methods that can be used in list_display
    @admin.display(description='تاریخ ایجاد (شمسی)', ordering='created_at')
    def created_at_jalali(self, obj):
        """Display created_at in Jalali format."""
        return self._format_jalali_datetime(getattr(obj, 'created_at', None))
    
    @admin.display(description='تاریخ بروزرسانی (شمسی)', ordering='updated_at')
    def updated_at_jalali(self, obj):
        """Display updated_at in Jalali format."""
        return self._format_jalali_datetime(getattr(obj, 'updated_at', None))
    
    @admin.display(description='تاریخ ایجاد', ordering='created_at')
    def jalali_created_at_display(self, obj):
        """
        Display created_at in Jalali format - compatible with existing admin usage.
        Safe if model has no `created_at` (returns "-").
        """
        created = getattr(obj, 'created_at', None)
        if not created:
            return "-"
        return self._format_jalali_datetime(created)
    
    @admin.display(description='تاریخ اجرا', ordering='effective_date')
    def jalali_effective_date_display(self, obj):
        """
        Display effective_date in Jalali format.
        Safe if model has no `effective_date` (returns "-").
        """
        effective_date = getattr(obj, 'effective_date', None)
        if not effective_date:
            return "-"
        return self._format_jalali_date(effective_date)
    
    @admin.display(description='تاریخ تأیید', ordering='approved_at')
    def jalali_approved_at_display(self, obj):
        """
        Display approved_at in Jalali format.
        Safe if model has no `approved_at` (returns "-").
        """
        approved_at = getattr(obj, 'approved_at', None)
        if not approved_at:
            return "-"
        return self._format_jalali_datetime(approved_at)
    
    @admin.display(description='تاریخ ایجاد', ordering='created_at')
    def created_at_jalali_verbose(self, obj):
        """Display created_at in verbose Jalali format."""
        return self._format_jalali_datetime(getattr(obj, 'created_at', None), verbose=True)
    
    @admin.display(description='تاریخ بروزرسانی', ordering='updated_at')
    def updated_at_jalali_verbose(self, obj):
        """Display updated_at in verbose Jalali format."""
        return self._format_jalali_datetime(getattr(obj, 'updated_at', None), verbose=True)


class JalaliReadOnlyAdminMixin(JalaliAdminMixin):
    """
    Jalali admin mixin for read-only models.
    Excludes system fields from forms but shows them in Jalali format.
    """
    
    def get_readonly_fields(self, request, obj=None):
        """
        Make system fields readonly and display in Jalali format.
        """
        readonly_fields = list(super().get_readonly_fields(request, obj))
        
        # Add common system fields as readonly
        system_fields = ['created_at', 'updated_at', 'id']
        for field in system_fields:
            if hasattr(self.model, field) and field not in readonly_fields:
                readonly_fields.append(field)
        
        return readonly_fields
    
    def get_exclude(self, request, obj=None):
        """
        Exclude system fields from forms (they'll be shown as readonly).
        """
        exclude = list(super().get_exclude(request, obj) or [])
        
        # Don't exclude if they're in readonly_fields
        readonly_fields = self.get_readonly_fields(request, obj)
        
        system_fields = ['created_at', 'updated_at']
        for field in system_fields:
            if (hasattr(self.model, field) and 
                field not in readonly_fields and 
                field not in exclude):
                exclude.append(field)
        
        return exclude if exclude else None


class JalaliTabularInline(admin.TabularInline):
    """
    Tabular inline with Jalali date support.
    """
    formfield_overrides = {
        models.DateField: {'widget': JalaliDateInput},
        models.DateTimeField: {'widget': JalaliDateTimeInput},
    }


class JalaliStackedInline(admin.StackedInline):
    """
    Stacked inline with Jalali date support.
    """
    formfield_overrides = {
        models.DateField: {'widget': JalaliDateInput},
        models.DateTimeField: {'widget': JalaliDateTimeInput},
    }


def jalali_date_display(field_name, description=None, verbose=False):
    """
    Decorator to create Jalali date display methods for admin.
    
    Usage:
        @jalali_date_display('birth_date', 'تاریخ تولد')
        def birth_date_jalali(self, obj):
            pass
    """
    def decorator(func):
        def wrapper(self, obj):
            value = getattr(obj, field_name, None)
            if verbose:
                return format_jalali_verbose(value) if value else "-"
            else:
                return to_jalali_date(value) if value else "-"
        
        wrapper.short_description = description or field_name
        wrapper.admin_order_field = field_name
        return wrapper
    
    return decorator


def jalali_datetime_display(field_name, description=None, include_timezone=False, verbose=False):
    """
    Decorator to create Jalali datetime display methods for admin.
    
    Usage:
        @jalali_datetime_display('created_at', 'زمان ایجاد', include_timezone=True)
        def created_at_jalali(self, obj):
            pass
    """
    def decorator(func):
        def wrapper(self, obj):
            value = getattr(obj, field_name, None)
            if value is None:
                return "-"
            
            if verbose:
                date_part = format_jalali_verbose(value)
                time_part = value.strftime('%H:%M')
                return f"{date_part} {time_part}"
            else:
                return to_jalali_datetime(value, include_timezone=include_timezone)
        
        wrapper.short_description = description or field_name
        wrapper.admin_order_field = field_name
        return wrapper
    
    return decorator
