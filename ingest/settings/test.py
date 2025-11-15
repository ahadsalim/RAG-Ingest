"""Test settings for the Ingest project."""
import os
from pathlib import Path

from .base import *  # noqa: F403

# Set the base directory
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'test-secret-key-1234567890'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

# Hosts/domain names that are valid for this site
ALLOWED_HOSTS = ['testserver', 'localhost', '127.0.0.1']

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# Cache
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
    }
}

# Email settings
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'

# File storage (use Django's default file system storage for tests)
DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'

# Celery Configuration
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_BROKER_URL = 'memory://'
CELERY_RESULT_BACKEND = 'cache+memory://'

# Testing
TEST_RUNNER = 'django.test.runner.DiscoverRunner'

# Disable password hashing for faster tests
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'CRITICAL',  # Reduce noise in test output
        },
        'ingest': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}

# Disable migrations for tests
class DisableMigrations(object):
    def __contains__(self, item):
        return True

    def __getitem__(self, item):
        return None

MIGRATION_MODULES = DisableMigrations()

# Test-specific settings
TESTING = True

# Disable throttling for tests
REST_FRAMEWORK['DEFAULT_THROTTLE_CLASSES'] = []  # noqa: F405
REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'] = {'user': None, 'anon': None}  # noqa: F405

# Use a simpler password hasher for faster tests
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

# Media files (for testing file uploads)
MEDIA_ROOT = os.path.join(BASE_DIR, 'test_media')
os.makedirs(MEDIA_ROOT, exist_ok=True)

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'

# Disable whitenoise for tests
MIDDLEWARE = [
    mw for mw in MIDDLEWARE  # noqa: F405
    if mw != 'whitenoise.middleware.WhiteNoiseMiddleware'
]

# Disable any external API calls
MOCK_EXTERNAL_APIS = True
