"""
Core app configuration for unified Jalali date handling.
"""
from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ingest.core'
    verbose_name = 'Core Utilities'
    
    def ready(self):
        """
        Initialize core functionality when Django starts.
        """
        # Import here to avoid circular imports
        pass
