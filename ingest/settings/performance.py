"""
Performance-optimized settings for Django application
تنظیمات بهینه‌سازی شده برای عملکرد بهتر
"""

from .base import *
import os

# =======================
# Database Optimizations
# =======================

# Increase connection pooling
DATABASES['default'].update({
    'CONN_MAX_AGE': 600,  # Keep connections alive for 10 minutes
    'CONN_HEALTH_CHECKS': True,  # Django 4.1+ feature for connection health
    'OPTIONS': {
        'connect_timeout': 10,
        'options': '-c statement_timeout=30000',  # 30 second statement timeout
        'keepalives': 1,
        'keepalives_idle': 30,
        'keepalives_interval': 10,
        'keepalives_count': 5,
    },
    'ATOMIC_REQUESTS': False,  # Don't wrap every request in transaction
})

# =======================
# Cache Configuration
# =======================

# Multi-tier caching strategy
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': os.getenv('REDIS_URL', 'redis://redis:6379/1'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            # HiredisParser removed - not compatible with redis-py >= 5.0
            'CONNECTION_POOL_CLASS': 'redis.BlockingConnectionPool',
            'CONNECTION_POOL_CLASS_KWARGS': {
                'max_connections': 50,
                'timeout': 20,
            },
            'KEEPALIVE_OPTIONS': {
                'keepalives': 1,
                'keepalives_idle': 30,
                'keepalives_interval': 5,
                'keepalives_count': 3,
            },
            'PICKLE_VERSION': -1,
            'COMPRESSOR': 'django_redis.compressors.zlib.ZlibCompressor',  # Compress cached data
        },
        'KEY_PREFIX': 'ingest',
        'TIMEOUT': 300,
    },
    # Session cache
    'sessions': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': os.getenv('REDIS_URL', 'redis://redis:6379/2'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        },
        'KEY_PREFIX': 'session',
        'TIMEOUT': 86400,  # 24 hours for sessions
    },
    # Template cache
    'templates': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'template-cache',
        'OPTIONS': {
            'MAX_ENTRIES': 100,
        },
        'TIMEOUT': 3600,  # 1 hour
    },
}

# Use Redis for sessions
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'sessions'
SESSION_COOKIE_AGE = 86400  # 24 hours
SESSION_SAVE_EVERY_REQUEST = False  # Only save session when modified

# =======================
# Query Optimization
# =======================

# Debug toolbar settings (only in development)
if DEBUG:
    DEBUG_TOOLBAR_CONFIG = {
        'SHOW_TOOLBAR_CALLBACK': lambda request: DEBUG,
        'SHOW_COLLAPSED': True,
        'SQL_WARNING_THRESHOLD': 100,   # milliseconds
    }

# =======================
# Middleware Optimization
# =======================

# Optimized middleware order (most used first)
MIDDLEWARE = [
    'django.middleware.cache.UpdateCacheMiddleware',  # Cache pages
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'simple_history.middleware.HistoryRequestMiddleware',
    'django.middleware.cache.FetchFromCacheMiddleware',  # Serve from cache
]

# Cache middleware settings
CACHE_MIDDLEWARE_ALIAS = 'default'
CACHE_MIDDLEWARE_SECONDS = 600  # 10 minutes
CACHE_MIDDLEWARE_KEY_PREFIX = 'page'

# =======================
# Template Optimization
# =======================

# Cache template loading
if not DEBUG:
    # When using loaders, APP_DIRS must be False
    TEMPLATES[0]['APP_DIRS'] = False
    TEMPLATES[0]['OPTIONS']['loaders'] = [
        ('django.template.loaders.cached.Loader', [
            'django.template.loaders.filesystem.Loader',
            'django.template.loaders.app_directories.Loader',
        ]),
    ]
    # Remove debug context processor in production
    if 'django.template.context_processors.debug' in TEMPLATES[0]['OPTIONS']['context_processors']:
        TEMPLATES[0]['OPTIONS']['context_processors'].remove(
            'django.template.context_processors.debug'
        )

# =======================
# Static Files Optimization
# =======================

# WhiteNoise configuration for static files
WHITENOISE_USE_FINDERS = True
WHITENOISE_AUTOREFRESH = DEBUG
WHITENOISE_SKIP_COMPRESS_EXTENSIONS = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'zip', 'gz', 'tgz', 'bz2', 'tbz', 'xz', 'br']

# Compress static files
WHITENOISE_COMPRESS_OFFLINE = not DEBUG
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# =======================
# REST Framework Optimization
# =======================

REST_FRAMEWORK.update({
    # Pagination
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    
    # Throttling
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle'
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',
        'user': '1000/hour'
    },
    
    # Renderer (remove browsable API in production)
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
    ) if not DEBUG else (
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ),
    
    # Parser (optimize for JSON only if not needed)
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
    ],
})

# =======================
# Celery Optimization
# =======================

# Celery performance settings
CELERY_TASK_SOFT_TIME_LIMIT = 55 * 60  # 55 minutes
CELERY_TASK_TIME_LIMIT = 60 * 60  # 60 minutes hard limit
CELERY_WORKER_PREFETCH_MULTIPLIER = 4
CELERY_WORKER_MAX_TASKS_PER_CHILD = 1000  # Restart worker after 1000 tasks to prevent memory leaks

# Result backend optimization
CELERY_RESULT_BACKEND_TRANSPORT_OPTIONS = {
    'master_name': 'mymaster',
    'socket_keepalive': True,
    'socket_keepalive_options': {
        1: 1,   # TCP_KEEPIDLE
        2: 15,  # TCP_KEEPINTVL  
        3: 3,   # TCP_KEEPCNT
    },
}

# =======================
# Logging Optimization
# =======================

LOGGING['handlers'].update({
    'file': {
        'level': 'ERROR',
        'class': 'logging.handlers.RotatingFileHandler',
        'filename': '/app/logs/django.log',
        'maxBytes': 1024 * 1024 * 100,  # 100 MB
        'backupCount': 10,
        'formatter': 'verbose',
    },
})

# Reduce logging in production
if not DEBUG:
    LOGGING['loggers']['django']['level'] = 'WARNING'
    LOGGING['loggers']['ingest']['level'] = 'INFO'

# =======================
# File Upload Optimization
# =======================

# Increase file upload limits
DATA_UPLOAD_MAX_MEMORY_SIZE = 10485760  # 10MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 10485760  # 10MB
DATA_UPLOAD_MAX_NUMBER_FIELDS = 10000

# =======================
# Security Headers (also improve caching)
# =======================

if not DEBUG:
    # Security headers that also help with caching
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
    
    # HSTS
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# =======================
# Application-specific Optimizations
# =======================

# Embedding service optimizations
EMBEDDING_BATCH_SIZE = 32  # Increase batch size for better GPU utilization
EMBEDDING_MAX_WORKERS = 4  # Parallel processing workers
EMBEDDING_CACHE_TTL = 3600  # Cache embeddings for 1 hour

# Chunking optimizations
DEFAULT_CHUNK_SIZE = 500  # Slightly larger chunks
DEFAULT_CHUNK_OVERLAP = 50  # Maintain overlap

# =======================
# Memory Management
# =======================

# Garbage collection tuning
import gc
gc.set_threshold(700, 10, 10)  # Tune garbage collection

# =======================
# Export Settings
# =======================

# This file should be imported in production as:
# from .performance import *
