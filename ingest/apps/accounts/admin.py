from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from .models import LoginEvent, UserProfile, OTPCode
from ingest.admin import admin_site
from ingest.core.admin_mixins import JalaliAdminMixin as SimpleJalaliAdminMixin
from ingest.core.jalali import to_jalali_datetime


class LoginEventAdmin(SimpleJalaliAdminMixin, admin.ModelAdmin):
    list_display = ('user', 'ip_address', 'jalali_timestamp', 'success')
    list_filter = ('success', 'timestamp')
    search_fields = ('user__username', 'ip_address')
    readonly_fields = ('id', 'user', 'ip_address', 'user_agent', 'jalali_timestamp', 'success')
    ordering = ('-timestamp',)
    
    def jalali_timestamp(self, obj):
        """Display timestamp in Jalali format (Tehran timezone)."""
        return self._format_jalali_datetime(obj.timestamp) if obj.timestamp else '-'
    jalali_timestamp.short_description = 'زمان ورود'
    jalali_timestamp.admin_order_field = 'timestamp'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


# Register models with custom admin site
admin_site.register(LoginEvent, LoginEventAdmin)


class UserProfileAdmin(SimpleJalaliAdminMixin, admin.ModelAdmin):
    """Admin for UserProfile model."""
    list_display = ('user', 'mobile', 'is_mobile_verified', 'jalali_created_at')
    list_filter = ('is_mobile_verified',)
    search_fields = ('user__username', 'mobile')
    readonly_fields = ('id', 'jalali_created_at', 'jalali_updated_at')
    
    def jalali_created_at(self, obj):
        return self._format_jalali_datetime(obj.created_at) if obj.created_at else '-'
    jalali_created_at.short_description = 'تاریخ ایجاد'
    
    def jalali_updated_at(self, obj):
        return self._format_jalali_datetime(obj.updated_at) if obj.updated_at else '-'
    jalali_updated_at.short_description = 'تاریخ به‌روزرسانی'


# Register new models
admin_site.register(UserProfile, UserProfileAdmin)
# OTPCode is not registered - it contains sensitive security data and should not be visible to users
