"""Complete Jalali admin solution with automatic date field conversion."""
import jdatetime
from django.contrib import admin
from django.utils.safestring import mark_safe
from simple_history.admin import SimpleHistoryAdmin


class JalaliModelAdmin(SimpleHistoryAdmin):
    """Base admin class with automatic Jalali date conversion."""
    
    def __init__(self, model, admin_site):
        super().__init__(model, admin_site)
        # Automatically convert date fields in list_display
        self._convert_list_display_dates()
    
    def _convert_list_display_dates(self):
        """Convert date fields in list_display to Jalali versions."""
        if hasattr(self, 'list_display'):
            new_list_display = []
            for field in self.list_display:
                if field in ['created_at', 'updated_at']:
                    # Replace with Jalali version
                    jalali_field = f'jalali_{field}_auto'
                    new_list_display.append(jalali_field)
                    # Add the method dynamically
                    setattr(self, jalali_field, self._make_jalali_method(field))
                else:
                    new_list_display.append(field)
            self.list_display = tuple(new_list_display)
    
    def _make_jalali_method(self, field_name):
        """Create a Jalali date method for the given field."""
        def jalali_method(obj):
            field_value = getattr(obj, field_name, None)
            if field_value:
                try:
                    j_datetime = jdatetime.datetime.fromgregorian(datetime=field_value)
                    jalali_str = j_datetime.strftime('%Y/%m/%d')
                    if hasattr(field_value, 'hour'):  # It's a datetime
                        jalali_str += j_datetime.strftime(' %H:%M')
                    return mark_safe(f'<span dir="ltr" class="jalali-date">{jalali_str}</span>')
                except Exception:
                    return field_value.strftime('%Y-%m-%d %H:%M') if field_value else '-'
            return '-'
        
        jalali_method.short_description = f'تاریخ {field_name.replace("_", " ")}'
        jalali_method.admin_order_field = field_name
        return jalali_method
    
    def get_form(self, request, obj=None, **kwargs):
        """Override to exclude non-editable fields safely."""
        # Always exclude these fields to prevent FieldError
        exclude = kwargs.get('exclude', []) or []
        exclude.extend(['id', 'created_at', 'updated_at'])
        kwargs['exclude'] = exclude
        return super().get_form(request, obj, **kwargs)
    
    class Media:
        css = {
            'all': ('admin/css/jalali-admin.css',)
        }


class JalaliTabularInline(admin.TabularInline):
    """Jalali-enabled tabular inline."""
    
    def get_readonly_fields(self, request, obj=None):
        """Add date fields to readonly."""
        readonly = list(super().get_readonly_fields(request, obj))
        if 'created_at' not in readonly:
            readonly.append('created_at')
        if 'updated_at' not in readonly:
            readonly.append('updated_at')
        return readonly


class JalaliStackedInline(admin.StackedInline):
    """Jalali-enabled stacked inline."""
    
    def get_readonly_fields(self, request, obj=None):
        """Add date fields to readonly."""
        readonly = list(super().get_readonly_fields(request, obj))
        if 'created_at' not in readonly:
            readonly.append('created_at')
        if 'updated_at' not in readonly:
            readonly.append('updated_at')
        return readonly
