from django.apps import AppConfig


class DocumentsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ingest.apps.documents'
    verbose_name = 'اسناد حقوقی'
    
    def ready(self):
        """Import signals when the app is ready."""
        # Import both signal modules
        import ingest.apps.documents.signals  # noqa: F401
        import ingest.apps.documents.signals_complete  # noqa: F401
