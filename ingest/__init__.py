# This will make sure the app is always imported when
# Django starts so that shared_task will use this app.
from .celery import app as celery_app
from .app_config import IngestConfig

__all__ = ('celery_app', 'IngestConfig')

# Default app config - tells Django to use IngestConfig from app_config.py
default_app_config = 'ingest.app_config.IngestConfig'

# Embedding registration is now handled in embeddings/admin.py automatically