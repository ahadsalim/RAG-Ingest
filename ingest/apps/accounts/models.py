import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone

# Proxy models for Celery Beat to group under accounts app
try:
    from django_celery_beat.models import PeriodicTask, CrontabSchedule, IntervalSchedule, ClockedSchedule
    
    class PeriodicTaskProxy(PeriodicTask):
        class Meta:
            proxy = True
            app_label = 'accounts'
            verbose_name = 'وظیفه تناوبی'
            verbose_name_plural = 'وظایف تناوبی'
    
    class CrontabScheduleProxy(CrontabSchedule):
        class Meta:
            proxy = True
            app_label = 'accounts'
            verbose_name = 'زمان‌بندی Crontab'
            verbose_name_plural = 'زمان‌بندی‌های Crontab'
    
    class IntervalScheduleProxy(IntervalSchedule):
        class Meta:
            proxy = True
            app_label = 'accounts'
            verbose_name = 'زمان‌بندی بازه‌ای'
            verbose_name_plural = 'زمان‌بندی‌های بازه‌ای'
    
    class ClockedScheduleProxy(ClockedSchedule):
        class Meta:
            proxy = True
            app_label = 'accounts'
            verbose_name = 'زمان‌بندی یکباره'
            verbose_name_plural = 'زمان‌بندی‌های یکباره'

except ImportError:
    # If django_celery_beat is not available, create empty proxy classes
    class PeriodicTaskProxy:
        pass
    class CrontabScheduleProxy:
        pass
    class IntervalScheduleProxy:
        pass
    class ClockedScheduleProxy:
        pass


class LoginEvent(models.Model):
    """Track user login events for security auditing."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='login_events')
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    timestamp = models.DateTimeField(default=timezone.now)
    success = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'رویداد ورود'
        verbose_name_plural = 'رویدادهای ورود'
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.user.username} - {self.timestamp}"


class UserActivityLog(models.Model):
    """Track user activities for payroll calculation."""
    ACTION_CHOICES = [
        ('login', 'ورود'),
        ('logout', 'خروج'),
        ('create', 'ایجاد'),
        ('update', 'ویرایش'),
        ('delete', 'حذف'),
        ('view', 'مشاهده'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='activity_logs')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    model_name = models.CharField(max_length=100, blank=True, null=True)
    object_id = models.CharField(max_length=100, blank=True, null=True)
    description = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField()
    timestamp = models.DateTimeField(default=timezone.now)
    session_duration = models.DurationField(blank=True, null=True)  # For logout events

    class Meta:
        verbose_name = 'لاگ فعالیت کاربر'
        verbose_name_plural = 'لاگ‌های فعالیت کاربران'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['action', 'timestamp']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.get_action_display()} - {self.timestamp}"


class UserWorkSession(models.Model):
    """Track work sessions for payroll calculation."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='work_sessions')
    login_time = models.DateTimeField()
    logout_time = models.DateTimeField(blank=True, null=True)
    ip_address = models.GenericIPAddressField()
    total_duration = models.DurationField(blank=True, null=True)
    activities_count = models.PositiveIntegerField(default=0)
    
    class Meta:
        verbose_name = 'جلسه کاری'
        verbose_name_plural = 'جلسات کاری'
        ordering = ['-login_time']

    def __str__(self):
        return f"{self.user.username} - {self.login_time.date()}"
    
    def calculate_duration(self):
        """Calculate session duration."""
        if self.logout_time:
            self.total_duration = self.logout_time - self.login_time
            self.save()
            return self.total_duration
        return None
