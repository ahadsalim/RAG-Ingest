from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from .models import LoginEvent, UserActivityLog, UserWorkSession, UserProfile, OTPCode
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


class UserActivityLogAdmin(SimpleJalaliAdminMixin, admin.ModelAdmin):
    list_display = ('user', 'action', 'model_name', 'jalali_timestamp', 'ip_address')
    list_filter = ('action', 'model_name', 'timestamp', 'user')
    search_fields = ('user__username', 'description', 'ip_address')
    readonly_fields = ('id', 'user', 'action', 'model_name', 'object_id', 'description', 'ip_address', 'jalali_timestamp', 'session_duration')
    ordering = ('-timestamp',)
    date_hierarchy = 'timestamp'
    
    def jalali_timestamp(self, obj):
        """Display timestamp in Jalali format (Tehran timezone)."""
        return self._format_jalali_datetime(obj.timestamp) if obj.timestamp else '-'
    jalali_timestamp.short_description = 'زمان فعالیت'
    jalali_timestamp.admin_order_field = 'timestamp'
    
    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['show_report_link'] = True
        return super().changelist_view(request, extra_context)
    
    actions = ['generate_user_report']
    
    def generate_user_report(self, request, queryset):
        """Generate report for selected users."""
        user_ids = list(queryset.values_list('user_id', flat=True).distinct())
        if user_ids:
            # Redirect to report page with selected users
            user_params = '&'.join([f'user={uid}' for uid in user_ids[:1]])  # Take first user for simplicity
            return HttpResponseRedirect(f'/admin/accounts/user-activity-report/?{user_params}')
        else:
            self.message_user(request, 'هیچ کاربری انتخاب نشده است.')
    generate_user_report.short_description = '📊 تولید گزارش برای کاربران انتخاب شده'
    
    fieldsets = (
        ('اطلاعات کاربر', {
            'fields': ('user', 'ip_address', 'timestamp')
        }),
        ('جزئیات فعالیت', {
            'fields': ('action', 'model_name', 'object_id', 'description')
        }),
        ('اطلاعات جلسه', {
            'fields': ('session_duration',),
            'classes': ('collapse',)
        }),
        ('اطلاعات سیستم', {
            'fields': ('id',),
            'classes': ('collapse',)
        })
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


class UserWorkSessionAdmin(SimpleJalaliAdminMixin, admin.ModelAdmin):
    list_display = ('user', 'jalali_login_time', 'jalali_logout_time', 'total_duration_display', 'activities_count', 'ip_address')
    list_filter = ('login_time', 'user')
    search_fields = ('user__username', 'ip_address')
    readonly_fields = ('id', 'user', 'jalali_login_time', 'jalali_logout_time', 'ip_address', 'total_duration', 'activities_count')
    ordering = ('-login_time',)
    date_hierarchy = 'login_time'
    
    def jalali_login_time(self, obj):
        """Display login time in Jalali format (Tehran timezone)."""
        return self._format_jalali_datetime(obj.login_time) if obj.login_time else '-'
    jalali_login_time.short_description = 'زمان ورود'
    jalali_login_time.admin_order_field = 'login_time'
    
    def jalali_logout_time(self, obj):
        """Display logout time in Jalali format (Tehran timezone)."""
        return self._format_jalali_datetime(obj.logout_time) if obj.logout_time else '-'
    jalali_logout_time.short_description = 'زمان خروج'
    jalali_logout_time.admin_order_field = 'logout_time'
    
    fieldsets = (
        ('اطلاعات جلسه', {
            'fields': ('user', 'login_time', 'logout_time', 'ip_address')
        }),
        ('آمار فعالیت', {
            'fields': ('total_duration', 'activities_count')
        }),
        ('اطلاعات سیستم', {
            'fields': ('id',),
            'classes': ('collapse',)
        })
    )

    def total_duration_display(self, obj):
        if obj.total_duration:
            total_seconds = int(obj.total_duration.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            return f"{hours}:{minutes:02d}"
        return "-"
    total_duration_display.short_description = 'مدت زمان کل'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


# Register models with custom admin site
admin_site.register(LoginEvent, LoginEventAdmin)
admin_site.register(UserActivityLog, UserActivityLogAdmin)
admin_site.register(UserWorkSession, UserWorkSessionAdmin)

# Custom admin class for reports
class ReportsAdmin(admin.ModelAdmin):
    """Custom admin for reports section."""
    
    def changelist_view(self, request, extra_context=None):
        """Override changelist to show reports dashboard."""
        extra_context = extra_context or {}
        extra_context.update({
            'title': 'گزارش‌های سیستم',
            'reports': [
                {
                    'title': 'گزارش فعالیت کاربران',
                    'description': 'گزارش تفصیلی فعالیت‌ها و ساعات کار کاربران',
                    'url': reverse('admin:accounts_user_activity_report'),
                    'icon': '📊',
                },
                {
                    'title': 'گزارش حقوق و دستمزد',
                    'description': 'محاسبه حقوق ماهانه بر اساس ساعات کار',
                    'url': reverse('admin:accounts_payroll_summary_report'),
                    'icon': '💰',
                },
            ]
        })
        return super().changelist_view(request, extra_context)

# Create a dummy model for reports
class ReportsModel:
    class Meta:
        verbose_name = 'گزارش'
        verbose_name_plural = 'گزارش‌ها'
        app_label = 'accounts'

# Celery Beat models removed - not needed in admin interface
# UserProfileInline is defined in /srv/ingest/admin.py to avoid circular imports


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


class OTPCodeAdmin(SimpleJalaliAdminMixin, admin.ModelAdmin):
    """Admin for OTPCode model."""
    list_display = ('mobile', 'code', 'jalali_created_at', 'jalali_expires_at', 'is_used', 'attempts')
    list_filter = ('is_used', 'created_at')
    search_fields = ('mobile', 'code')
    readonly_fields = ('id', 'mobile', 'code', 'jalali_created_at', 'jalali_expires_at', 'is_used', 'ip_address', 'attempts')
    ordering = ('-created_at',)
    
    def jalali_created_at(self, obj):
        return self._format_jalali_datetime(obj.created_at) if obj.created_at else '-'
    jalali_created_at.short_description = 'تاریخ ایجاد'
    
    def jalali_expires_at(self, obj):
        return self._format_jalali_datetime(obj.expires_at) if obj.expires_at else '-'
    jalali_expires_at.short_description = 'زمان انقضا'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False


# Register new models
admin_site.register(UserProfile, UserProfileAdmin)
admin_site.register(OTPCode, OTPCodeAdmin)
