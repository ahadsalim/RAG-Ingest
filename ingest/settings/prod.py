"""Production settings for ingest project."""

from .base import *

# Helper function for parsing comma-separated environment variables
def csv_env(name, default=""):
    """Parse comma-separated env var, strip whitespace, ignore blanks."""
    return [x.strip() for x in os.getenv(name, default).split(",") if x.strip()]

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'

# Parse ALLOWED_HOSTS from environment
ALLOWED_HOSTS = csv_env('ALLOWED_HOSTS', 'localhost,127.0.0.1')

# Parse CSRF_TRUSTED_ORIGINS from environment
CSRF_TRUSTED_ORIGINS = csv_env('CSRF_TRUSTED_ORIGINS', '')

# Proxy settings
USE_X_FORWARDED_HOST = os.getenv('USE_X_FORWARDED_HOST', 'True').lower() == 'true'

# SECURE_PROXY_SSL_HEADER configuration
hdr = os.getenv('SECURE_PROXY_SSL_HEADER', '')
if hdr:
    parts = hdr.split(',', 1)
    if len(parts) == 2:
        SECURE_PROXY_SSL_HEADER = (parts[0].strip(), parts[1].strip())
    else:
        SECURE_PROXY_SSL_HEADER = None
else:
    SECURE_PROXY_SSL_HEADER = None

# SSL/Security settings - read from environment
SECURE_SSL_REDIRECT = os.getenv('SECURE_SSL_REDIRECT', 'True').lower() == 'true'
SESSION_COOKIE_SECURE = os.getenv('SESSION_COOKIE_SECURE', 'True').lower() == 'true'
CSRF_COOKIE_SECURE = os.getenv('CSRF_COOKIE_SECURE', 'True').lower() == 'true'

# HSTS settings
SECURE_HSTS_SECONDS = int(os.getenv('SECURE_HSTS_SECONDS', '31536000'))
SECURE_HSTS_INCLUDE_SUBDOMAINS = os.getenv('SECURE_HSTS_INCLUDE_SUBDOMAINS', 'true').lower() == 'true'
SECURE_HSTS_PRELOAD = os.getenv('SECURE_HSTS_PRELOAD', 'true').lower() == 'true'

# Database connection pooling for production
DATABASES['default'].update({
    'CONN_MAX_AGE': 60,  # Keep connections alive for 1 minute
})

# Static files with Whitenoise but WITHOUT aggressive caching
# Use CompressedStaticFilesStorage for serving but with short cache time
STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'

# Short cache time (10 minutes instead of 1 year)
WHITENOISE_MAX_AGE = 600

# Force Django to serve static files in production
STATIC_URL = '/static/'
STATIC_ROOT = '/app/staticfiles'

# Whitenoise is already in base.py MIDDLEWARE, no need to insert again

# Email settings
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.getenv('EMAIL_HOST')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')

# MinIO settings for production
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID', 'minioadmin')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY', 'minioadmin')
AWS_STORAGE_BUCKET_NAME = os.getenv('AWS_STORAGE_BUCKET_NAME', 'advisor-docs')
AWS_S3_ENDPOINT_URL = os.getenv('AWS_S3_ENDPOINT_URL', 'http://localhost:9000')
AWS_S3_USE_SSL = os.getenv('MINIO_USE_SSL', 'False').lower() == 'true'
AWS_S3_FILE_OVERWRITE = False
AWS_DEFAULT_ACL = None
AWS_QUERYSTRING_AUTH = True
AWS_S3_OBJECT_PARAMETERS = {
    'CacheControl': 'max-age=86400',
}

# Use MinIO for file storage by default
DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'

# Public URL for MinIO files (used for generating download links)
MINIO_STORAGE_MEDIA_URL = f"{AWS_S3_ENDPOINT_URL}/{AWS_STORAGE_BUCKET_NAME}/"

# Logging for production (console only for Docker)
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
            'level': 'INFO',
            'propagate': False,
        },
        'ingest': {
            'handlers': ['console'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
    },
}
