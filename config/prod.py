# Production configuration
import os
import dj_database_url
from config import *

# Production settings overrides
DEBUG = False

# Load ALLOWED_HOSTS from env (split by commas) or default to any host in Railway
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', '*').split(',')

# Secret key override (highly recommended to set this in Railway config)
if os.getenv('SECRET_KEY'):
    SECRET_KEY = os.getenv('SECRET_KEY')

# Database configuration: parse DATABASE_URL if provided
db_url = os.getenv('DATABASE_URL')
if db_url:
    DATABASES['default'] = dj_database_url.config(
        conn_max_age=600,
        conn_health_checks=True,
    )

# Static files and middleware for serving static assets via WhiteNoise
if 'whitenoise.middleware.WhiteNoiseMiddleware' not in MIDDLEWARE:
    try:
        security_index = MIDDLEWARE.index('django.middleware.security.SecurityMiddleware')
        MIDDLEWARE.insert(security_index + 1, 'whitenoise.middleware.WhiteNoiseMiddleware')
    except ValueError:
        MIDDLEWARE.insert(0, 'whitenoise.middleware.WhiteNoiseMiddleware')

# Configure static assets path and WhiteNoise storage
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
