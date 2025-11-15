import logging
from datetime import timedelta
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.contrib.admin.models import LogEntry, ADDITION, CHANGE, DELETION
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from .models import LoginEvent, UserActivityLog, UserWorkSession

logger = logging.getLogger(__name__)


@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    """Log user login events and create work session."""
    ip_address = get_client_ip(request)
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    
    # Create login event
    LoginEvent.objects.create(
        user=user,
        ip_address=ip_address,
        user_agent=user_agent,
        success=True
    )
    
    # Create activity log
    UserActivityLog.objects.create(
        user=user,
        action='login',
        description=f'کاربر وارد سیستم شد',
        ip_address=ip_address
    )
    
    # Create or update work session
    UserWorkSession.objects.create(
        user=user,
        login_time=timezone.now(),
        ip_address=ip_address
    )


@receiver(user_logged_out)
def log_user_logout(sender, request, user, **kwargs):
    """Log user logout events and update work session."""
    if user and user.is_authenticated:
        ip_address = get_client_ip(request)
        
        # Find the latest work session
        try:
            session = UserWorkSession.objects.filter(
                user=user,
                logout_time__isnull=True
            ).latest('login_time')
            
            session.logout_time = timezone.now()
            session.calculate_duration()
            
            # Create activity log with session duration
            UserActivityLog.objects.create(
                user=user,
                action='logout',
                description=f'کاربر از سیستم خارج شد',
                ip_address=ip_address,
                session_duration=session.total_duration
            )
            
        except UserWorkSession.DoesNotExist:
            # Create logout activity without session info
            UserActivityLog.objects.create(
                user=user,
                action='logout',
                description=f'کاربر از سیستم خارج شد',
                ip_address=ip_address
            )


@receiver(post_save, sender=LogEntry)
def log_admin_activity(sender, instance, created, **kwargs):
    """Track admin panel activities."""
    if created and instance.user:
        action_map = {
            ADDITION: 'create',
            CHANGE: 'update',
            DELETION: 'delete'
        }
        
        action = action_map.get(instance.action_flag, 'view')
        model_name = instance.content_type.model if instance.content_type else 'unknown'
        
        # Get IP address from current request (if available)
        ip_address = '127.0.0.1'  # Default fallback
        
        # Update activities count in current session
        try:
            session = UserWorkSession.objects.filter(
                user=instance.user,
                logout_time__isnull=True
            ).latest('login_time')
            session.activities_count += 1
            session.save()
        except UserWorkSession.DoesNotExist:
            pass
        
        UserActivityLog.objects.create(
            user=instance.user,
            action=action,
            model_name=model_name,
            object_id=str(instance.object_id) if instance.object_id else None,
            description=instance.change_message or f'{action} {model_name}',
            ip_address=ip_address
        )


def get_client_ip(request):
    """Get the client IP address from the request."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip
