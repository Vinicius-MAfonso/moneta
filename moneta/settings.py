import os
from pathlib import Path

import environ

if os.name == 'nt':
    NPM_BIN_PATH = r"C:\Program Files\nodejs\npm.cmd"

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env()

environ.Env.read_env(BASE_DIR / '.env')

DEBUG = env.bool('DEBUG', default=False)
SECRET_KEY = env('SECRET_KEY', default='django-insecure-moneta-production-change-me')
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['*'])
if 'testserver' not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append('testserver')
CSRF_TRUSTED_ORIGINS = env.list('CSRF_TRUSTED_ORIGINS', default=['https://*.run.app', 'https://*.a.run.app'])

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'axes',
    'planning',
    'transactions',
    'users',
    'wallets',
    'django_q',
    'tailwind',
    'theme',
    'anymail',
]

TAILWIND_APP_NAME = 'theme'
INTERNAL_IPS = ["127.0.0.1"]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'moneta.middleware.SecurityHeadersMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'axes.middleware.AxesMiddleware',
]

AUTHENTICATION_BACKENDS = [
    'axes.backends.AxesBackend',
    'django.contrib.auth.backends.ModelBackend',
]

ROOT_URLCONF = 'moneta.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'moneta.wsgi.application'


DATABASES = {
    'default': env.db('DATABASE_URL', default=f'sqlite:///{BASE_DIR / "db.sqlite3"}')
}

LANGUAGE_CODE = 'pt-br'

TIME_ZONE = 'America/Sao_Paulo'

USE_I18N = True

USE_TZ = True

USE_THOUSAND_SEPARATOR = True


STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

if not DEBUG:
    STORAGES = {
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        },
    }

VAPID_PUBLIC_KEY = env('VAPID_PUBLIC_KEY', default='')
VAPID_PRIVATE_KEY = env('VAPID_PRIVATE_KEY', default='')
VAPID_ADMIN_EMAIL = env('VAPID_ADMIN_EMAIL', default='')

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = env.bool('SECURE_SSL_REDIRECT', default=not DEBUG)
SESSION_COOKIE_SECURE = env.bool('SESSION_COOKIE_SECURE', default=not DEBUG)
CSRF_COOKIE_SECURE = env.bool('CSRF_COOKIE_SECURE', default=not DEBUG)
SECURE_HSTS_SECONDS = env.int('SECURE_HSTS_SECONDS', default=31536000 if not DEBUG else 0)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool('SECURE_HSTS_INCLUDE_SUBDOMAINS', default=not DEBUG)
SECURE_HSTS_PRELOAD = env.bool('SECURE_HSTS_PRELOAD', default=not DEBUG)
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'
X_FRAME_OPTIONS = 'DENY'

DEFAULT_CSP_POLICY = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://unpkg.com https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com; "
    "img-src 'self' data: blob:; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'; "
    "object-src 'none'"
)
CONTENT_SECURITY_POLICY = env('CONTENT_SECURITY_POLICY', default=DEFAULT_CSP_POLICY)

DEFAULT_PERMISSIONS_POLICY = (
    "camera=(), "
    "microphone=(), "
    "geolocation=(), "
    "payment=(), "
    "usb=(), "
    "accelerometer=(), "
    "gyroscope=(), "
    "magnetometer=(), "
    "display-capture=()"
)
PERMISSIONS_POLICY = env('PERMISSIONS_POLICY', default=DEFAULT_PERMISSIONS_POLICY)

AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = 1

Q_CLUSTER = {
    'name': 'moneta_cluster',
    'workers': 1,
    'recycle': 500,
    'timeout': 60,
    'compress': True,
    'save_limit': 250,
    'queue_limit': 500,
    'cpu_affinity': 1,
    'label': 'Django Q',
    'orm': 'default',
    'sync': True,
}

EMAIL_BACKEND = (
    'django.core.mail.backends.console.EmailBackend' if DEBUG else 'anymail.backends.brevo.EmailBackend'
)
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', default='Moneta <noreply@moneta.app>')
SITE_URL = env('SITE_URL', default='http://localhost:8000')
ANYMAIL = {'BREVO_API_KEY': env('BREVO_API_KEY', default='')}

# Secret token for the Google Cloud Scheduler cron wake endpoint (/internal/cron/wake/).
# Generate with: openssl rand -hex 32
# Set this as a GitHub Actions secret (CRON_SECRET) and in Cloud Scheduler's Authorization header.
CRON_SECRET = env('CRON_SECRET', default='')



