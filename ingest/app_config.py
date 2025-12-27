from django.apps import AppConfig


class IngestConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ingest'

    def ready(self):
        """Register built-in Django models with custom admin site after apps are loaded"""
        print("DEBUG: IngestConfig.ready() called")
        from django.contrib.auth.models import User, Group
        from django.contrib.auth.admin import UserAdmin, GroupAdmin
        from django.contrib.admin.sites import AlreadyRegistered
        from .admin import admin_site
        
        # Register User and Group models with custom admin site (if not already registered)
        try:
            if User not in admin_site._registry:
                admin_site.register(User, UserAdmin)
            if Group not in admin_site._registry:
                admin_site.register(Group, GroupAdmin)
            print(f"DEBUG: Registered User and Group. Total models: {len(admin_site._registry)}")
        except AlreadyRegistered:
            print("DEBUG: User/Group already registered, skipping")
        
        # Register django_celery_beat models (only PeriodicTask and CrontabSchedule)
        # IntervalSchedule and ClockedSchedule are not used and hidden from admin
        try:
            from django_celery_beat.models import PeriodicTask, CrontabSchedule
            from django_celery_beat.admin import PeriodicTaskAdmin, CrontabScheduleAdmin
            
            # Register only the models we use
            if PeriodicTask not in admin_site._registry:
                admin_site.register(PeriodicTask, PeriodicTaskAdmin)
            if CrontabSchedule not in admin_site._registry:
                admin_site.register(CrontabSchedule, CrontabScheduleAdmin)
            
            print(f"DEBUG: Registered celery beat models. Total models: {len(admin_site._registry)}")
        except ImportError as e:
            print(f"DEBUG: Could not import celery beat models: {e}")
        except AlreadyRegistered as e:
            print(f"DEBUG: Some celery beat models already registered: {e}")
        
        # Embedding registration is now handled in embeddings/admin.py automatically
        print(f"DEBUG: IngestConfig ready complete. Total models: {len(admin_site._registry)}")
