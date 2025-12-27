"""
Django settings for ingest project.
Base settings shared across all environments.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Load environment variables (optional .env file)
try:
    load_dotenv(BASE_DIR / '.env')
except (FileNotFoundError, PermissionError):
    # .env file not found or no permission - use environment variables directly
    pass

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-change-me-in-production')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

# Hosts / CSRF / CORS
ALLOWED_HOSTS = [h.strip() for h in os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1,localhost:8000").split(",") if h.strip()]

# If behind a proxy or using HTTPS offload
USE_X_FORWARDED_HOST = os.getenv("USE_X_FORWARDED_HOST", "false").lower() == "true"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https") if os.getenv("PROXIED_SSL", "false").lower() == "true" else None

# CSRF trusted origins: full scheme+host (no trailing slash)
CSRF_TRUSTED_ORIGINS = [o.strip() for o in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()]

# CORS (if django-cors-headers is installed)
CORS_ALLOWED_ORIGINS = [o.strip() for o in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",") if o.strip()]
CORS_ALLOW_CREDENTIALS = os.getenv("CORS_ALLOW_CREDENTIALS", "true").lower() == "true"

# Application definition
DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

THIRD_PARTY_APPS = [
    'rest_framework',
    'corsheaders',
    'simple_history',
    'mptt',
    'django_celery_beat',
    'storages',
]

LOCAL_APPS = [
    'ingest.core',  # Core utilities including Jalali support
    'ingest.apps.accounts',
    'ingest.apps.masterdata',
    'ingest.apps.documents',
    'ingest.apps.embeddings.apps.EmbeddingsConfig',
    'ingest.app_config.IngestConfig',  # Main app - registers celery beat models in IngestConfig.ready()
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# Custom admin site
ADMIN_SITE_HEADER = 'سیستم مدیریت اسناد حقوقی'

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'simple_history.middleware.HistoryRequestMiddleware',
]

# Session Configuration - Use Redis for sessions
SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"

ROOT_URLCONF = 'ingest.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            BASE_DIR / 'templates',  # project templates dir
            BASE_DIR / 'ingest' / 'templates'  # legacy templates dir
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'ingest.core.context_processors.jalali_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'ingest.wsgi.application'

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('POSTGRES_DB', 'ingest'),
        'USER': os.getenv('POSTGRES_USER', 'ingest'),
        'PASSWORD': os.getenv('POSTGRES_PASSWORD', 'ingest123'),
        'HOST': os.getenv('POSTGRES_HOST', 'db'),
        'PORT': '5432',  # Internal Docker port
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization - Persian Only
LANGUAGE_CODE = 'fa'
TIME_ZONE = 'UTC'  # Database/internal timezone (always UTC)
USE_I18N = True   # Enable internationalization for translations
USE_L10N = True   # Keep localization for Persian formatting

# Languages
LANGUAGES = [
    ('fa', 'فارسی'),
    ('en', 'English'),
]

# Locale paths
LOCALE_PATHS = [
    BASE_DIR / 'ingest' / 'locale',
]
USE_TZ = True

# Display timezone and locale settings
DISPLAY_TIME_ZONE = os.getenv("DISPLAY_TIME_ZONE", "Asia/Tehran")
DISPLAY_LOCALE = os.getenv("DISPLAY_LOCALE", "fa_IR")
DISPLAY_CALENDAR = "jalali"

# Static files (CSS, JavaScript, Images)
STATIC_URL = os.getenv("STATIC_URL", "/static/")
STATIC_ROOT = os.getenv("STATIC_ROOT", str(BASE_DIR / "staticfiles"))
MEDIA_URL = os.getenv("MEDIA_URL", "/media/")
MEDIA_ROOT = os.getenv("MEDIA_ROOT", str(BASE_DIR / "media"))

# Optional script prefix if app is mounted under a subpath (e.g., /app)
FORCE_SCRIPT_NAME = os.getenv("FORCE_SCRIPT_NAME", None)
if FORCE_SCRIPT_NAME:
    STATIC_URL = FORCE_SCRIPT_NAME.rstrip("/") + STATIC_URL
    MEDIA_URL = FORCE_SCRIPT_NAME.rstrip("/") + MEDIA_URL

# Additional static files directories
STATICFILES_DIRS = []

# Static files finders
STATICFILES_FINDERS = [
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
]

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Django REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
}

# MinIO Storage Settings
DEFAULT_FILE_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_STORAGE_BUCKET_NAME = os.getenv("AWS_STORAGE_BUCKET_NAME")
AWS_S3_ENDPOINT_URL = os.getenv("AWS_S3_ENDPOINT_URL", "http://minio:9000")  # Local MinIO
AWS_S3_REGION_NAME = "us-east-1"
AWS_S3_SIGNATURE_VERSION = "s3v4"
AWS_S3_ADDRESSING_STYLE = "path"
AWS_S3_VERIFY = False
AWS_S3_USE_SSL = False

# S3 Connection and Timeout Settings
AWS_S3_CONNECTION_TIMEOUT = 300  # 5 minutes
AWS_S3_READ_TIMEOUT = 300  # 5 minutes
AWS_S3_MAX_POOL_CONNECTIONS = 50
AWS_S3_RETRIES = {
    'max_attempts': 3,
    'mode': 'adaptive'
}

# Media URL configuration
MEDIA_URL = f"{AWS_S3_ENDPOINT_URL}/{AWS_STORAGE_BUCKET_NAME}/"

# Cache Configuration (Redis)
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': os.getenv('REDIS_URL', 'redis://redis:6379/1'),  # DB 1 for cache
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'PICKLE_VERSION': -1,
        },
        'KEY_PREFIX': 'ingest',
        'TIMEOUT': 300,  # 5 minutes default
    }
}

# Celery Configuration (Redis)
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://redis:6379/0')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://redis:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_SOFT_TIME_LIMIT = 55 * 60  # 55 minutes
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_BROKER_CONNECTION_RETRY = True
CELERY_BROKER_CONNECTION_MAX_RETRIES = 10

# Celery Beat Schedule - Periodic Tasks
from celery.schedules import crontab
CELERY_BEAT_SCHEDULE = {
    'check-missing-embeddings-hourly': {
        'task': 'embeddings.check_missing_embeddings',
        'schedule': crontab(minute=0),  # Every hour
    },
    'cleanup-orphaned-embeddings-daily': {
        'task': 'embeddings.cleanup_orphaned_embeddings',
        'schedule': crontab(hour=3, minute=0),  # Daily at 3 AM
    },
    # Core Sync Tasks
    'auto-sync-new-embeddings': {
        'task': 'ingest.apps.embeddings.tasks.auto_sync_new_embeddings',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
    },
    'sync-metadata-changes': {
        'task': 'ingest.apps.embeddings.tasks.sync_changed_metadata',
        'schedule': crontab(minute='*/15'),  # Every 15 minutes
    },
    'cleanup-orphaned-nodes': {
        'task': 'ingest.apps.embeddings.tasks.cleanup_orphaned_nodes',
        'schedule': crontab(hour=2, minute=30),  # Daily at 2:30 AM
    },
    'cleanup-old-logs-daily': {
        'task': 'system.cleanup_old_logs',
        'schedule': crontab(hour=4, minute=0),  # Daily at 4 AM
    },
}

# Core Service Integration
# Note: Core API connection is configured via CoreConfig model in database
# Access via Admin Panel: /admin/embeddings/coreconfig/
CORE_BASE_URL = os.getenv('CORE_BASE_URL', 'http://localhost:8000')

# Chunking Settings
DEFAULT_CHUNK_SIZE = int(os.getenv('DEFAULT_CHUNK_SIZE', '450'))
DEFAULT_CHUNK_OVERLAP = int(os.getenv('DEFAULT_CHUNK_OVERLAP', '50'))

# Embedding Settings - E5 Multilingual Backend Configuration
EMBEDDING_PROVIDER = os.getenv('EMBEDDING_PROVIDER', 'e5').lower()
EMBEDDING_MODEL_ID = os.getenv('EMBEDDING_MODEL_ID', '')  # Auto-detected if empty
EMBEDDING_DIMENSION = int(os.getenv('EMBEDDING_DIMENSION', '0')) if os.getenv('EMBEDDING_DIMENSION', '').strip() else None  # Auto-detected if None
EMBEDDING_BATCH_SIZE = int(os.getenv('EMBEDDING_BATCH_SIZE', '16'))
EMBEDDING_TIMEOUT = int(os.getenv('EMBEDDING_TIMEOUT', '60'))
EMBEDDING_MAX_RETRIES = int(os.getenv('EMBEDDING_MAX_RETRIES', '3'))

# E5 Multilingual Backend Configuration
EMBEDDING_E5_MODEL_NAME = os.getenv('EMBEDDING_E5_MODEL_NAME', 'intfloat/multilingual-e5-large')
EMBEDDING_DEVICE = os.getenv('EMBEDDING_DEVICE', 'cuda' if 'cuda' in str(os.getenv('EMBEDDING_DEVICE', '')) else 'cpu')
EMBEDDING_MAX_SEQ_LENGTH = int(os.getenv('EMBEDDING_MAX_SEQ_LENGTH', '512'))
EMBEDDING_MODEL_CACHE_DIR = os.getenv('EMBEDDING_MODEL_CACHE_DIR', '/app/models')

# Feature Flags
EMBEDDINGS_READ_MODEL_ID = os.getenv('EMBEDDINGS_READ_MODEL_ID', '')  # Blue/green deployment support

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': os.getenv('DJANGO_LOG_LEVEL', 'INFO'),
            'propagate': False,
        },
        'ingest': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}

# Security Settings
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# Production security toggles (enabled when DEBUG=False)
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "0"))  # set >0 when ready
    SECURE_HSTS_INCLUDE_SUBDOMAINS = os.getenv("SECURE_HSTS_INCLUDE_SUBDOMAINS", "false").lower() == "true"
    SECURE_HSTS_PRELOAD = os.getenv("SECURE_HSTS_PRELOAD", "false").lower() == "true"
    SECURE_SSL_REDIRECT = os.getenv("SECURE_SSL_REDIRECT", "true").lower() == "true"

# File Upload Settings
FILE_UPLOAD_MAX_MEMORY_SIZE = 50 * 1024 * 1024  # 50MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 50 * 1024 * 1024  # 50MB

# Embedding Settings
EMBEDDINGS_ENABLED = os.getenv('EMBEDDINGS_ENABLED', 'true').lower() == 'true'

# Bale Messenger OTP Authentication (Safir API)
BALE_API_URL = os.getenv('BALE_API_URL', 'https://safir.bale.ai/api/v2')
BALE_CLIENT_ID = os.getenv('BALE_CLIENT_ID', '')
BALE_CLIENT_SECRET = os.getenv('BALE_CLIENT_SECRET', '')

# Jalali Date Settings
JALALI_DATE_DEFAULTS = {
    "STATIC_HOST": "/static/",
    "DATE_FORMAT": "YYYY/MM/DD",
    "SHOW_TODAY_BUTTON": True,
}

# Custom date format for Persian display
USE_L10N = True
DATE_FORMAT = 'Y/m/d'
DATETIME_FORMAT = 'Y/m/d H:i'
SHORT_DATE_FORMAT = 'Y/m/d'
SHORT_DATETIME_FORMAT = 'Y/m/d H:i'
