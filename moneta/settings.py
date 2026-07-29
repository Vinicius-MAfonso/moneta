from pathlib import Path
import environ

BASE_DIR = Path(__file__).resolve().parent.parent


def get_env_list(name, default):
    value = os.getenv(name)
    if value is None:
        return default

    value = value.strip()
    if not value:
        return default

    if value.startswith('[') and value.endswith(']'):
        value = value[1:-1]

    return [
        item.strip().strip('"').strip("'")
        for item in value.split(',')
        if item.strip()
    ]


SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key')

DEBUG = os.getenv('DEBUG', 'True') == 'True'

ALLOWED_HOSTS = get_env_list('ALLOWED_HOSTS', ['localhost', '127.0.0.1', '0.0.0.0', '[::1]'])
CSRF_TRUSTED_ORIGINS = get_env_list('CSRF_TRUSTED_ORIGINS', ['http://localhost:8000', 'http://127.0.0.1:8000'])


INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'investments',
    'planning',
    'transactions',
    'users',
    'wallets',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'moneta.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
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
    'default': f"postgresql://{env('POSTGRES_USER')}:{env('POSTGRES_PASSWORD')}@{env('DB_HOST')}:{env('DB_PORT')}/{env('POSTGRES_DB')}"
}


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


LANGUAGE_CODE = 'pt-br'

TIME_ZONE = 'America/Sao_Paulo'

USE_I18N = True

USE_TZ = True

AUTH_USER_MODEL = 'users.User'

STATIC_URL = 'static/'
