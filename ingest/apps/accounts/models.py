import uuid
import random
import string
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from django.conf import settings

# Proxy models for Celery Beat to group under accounts app
# Only PeriodicTask and CrontabSchedule are used (IntervalSchedule and ClockedSchedule removed)
try:
    from django_celery_beat.models import PeriodicTask, CrontabSchedule
    
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

except ImportError:
    # If django_celery_beat is not available, create empty proxy classes
    class PeriodicTaskProxy:
        pass
    class CrontabScheduleProxy:
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


class UserProfile(models.Model):
    """Extended user profile with mobile number for OTP authentication."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField('auth.User', on_delete=models.CASCADE, related_name='profile')
    mobile = models.CharField(max_length=15, unique=True, verbose_name='شماره موبایل',
                              help_text='شماره موبایل باید در پیام‌رسان بله ثبت‌نام شده باشد')
    is_mobile_verified = models.BooleanField(default=False, verbose_name='موبایل تایید شده')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'پروفایل کاربر'
        verbose_name_plural = 'پروفایل‌های کاربران'

    def __str__(self):
        return f"{self.user.username} - {self.mobile}"


class OTPCode(models.Model):
    """OTP codes for mobile authentication via Bale messenger."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    mobile = models.CharField(max_length=15, verbose_name='شماره موبایل')
    code = models.CharField(max_length=6, verbose_name='کد تایید')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(verbose_name='زمان انقضا')
    is_used = models.BooleanField(default=False, verbose_name='استفاده شده')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    attempts = models.PositiveIntegerField(default=0, verbose_name='تعداد تلاش')

    class Meta:
        verbose_name = 'کد تایید OTP'
        verbose_name_plural = 'کدهای تایید OTP'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['mobile', 'is_used']),
            models.Index(fields=['expires_at']),
        ]

    def __str__(self):
        return f"{self.mobile} - {self.code}"

    @classmethod
    def generate_code(cls, mobile, ip_address=None, expiry_minutes=5):
        """Generate a new OTP code for the given mobile number."""
        # Invalidate previous unused codes
        cls.objects.filter(mobile=mobile, is_used=False).update(is_used=True)
        
        # Generate 6-digit code
        code = ''.join(random.choices(string.digits, k=6))
        
        # Create new OTP
        otp = cls.objects.create(
            mobile=mobile,
            code=code,
            expires_at=timezone.now() + timezone.timedelta(minutes=expiry_minutes),
            ip_address=ip_address
        )
        return otp

    def is_valid(self):
        """Check if OTP is still valid."""
        return (
            not self.is_used and 
            self.expires_at > timezone.now() and 
            self.attempts < 5
        )

    def verify(self, code):
        """Verify the OTP code."""
        self.attempts += 1
        self.save()
        
        if not self.is_valid():
            return False
        
        if self.code == code:
            self.is_used = True
            self.save()
            return True
        
        return False
