from django.apps import AppConfig


class DocumentsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ingest.apps.documents'
    verbose_name = 'اسناد حقوقی'
    
    def ready(self):
        """Import unified signals when the app is ready."""
        # Import unified signal module (combines signals.py and signals_complete.py)
        import ingest.apps.documents.signals_unified  # noqa: F401
