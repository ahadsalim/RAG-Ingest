from django.apps import AppConfig


class EmbeddingsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ingest.apps.embeddings'
    verbose_name = 'جاسازی‌ها'
    
    def ready(self):
        """App is ready."""
        # Import admin to register models
        from . import admin
        
        # Import tasks to ensure they are registered with Celery
        try:
            from . import tasks
        except ImportError:
            pass  # Tasks might not be available in all environments
        
        # Import signals for change tracking
        try:
            from . import signals
        except ImportError:
            pass
