import os
from pathlib import Path
from datetime import timedelta

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-change-in-production')
DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '109.196.103.11,localhost,127.0.0.1').split(',')

INSTALLED_APPS = [
    'jazzmin',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'apps.users',
    'apps.analysis',
    'apps.core',
]

MIDDLEWARE = [
    'config.middleware.DatabaseRetryMiddleware',
    'config.middleware.RealClientIPMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('POSTGRES_DB', 'teledent'),
        'USER': os.environ.get('POSTGRES_USER', 'teledent_user'),
        'PASSWORD': os.environ.get('POSTGRES_PASSWORD', ''),
        'HOST': os.environ.get('POSTGRES_HOST', 'db'),
        'PORT': os.environ.get('POSTGRES_PORT', '5432'),
        # БД физически на другом сервере (RU). Если сеть на секунду пропадёт,
        # без таймаута psycopg2 ждёт неопределённо долго и блокирует gunicorn-воркер.
        # RTT KZ↔RU ~50-80 мс; 8 сек даёт запас, чтобы короткий провал маршрута
        # между ЦОДами (1-7 сек) проглотился на том же connect, а не превратился
        # в 500. Выше не ставим — иначе при настоящем длительном обрыве воркеры
        # будут блокироваться дольше.
        'OPTIONS': {
            'connect_timeout': 8,
            # TCP keepalive: NAT/файрволы между KZ и RU тихо рвут idle-сокет
            # через 5-15 минут. Без keepalive OS думает что коннект жив и
            # следующий SELECT висит до общесистемного таймаута (~часы),
            # gunicorn-воркер блокируется и админка отдаёт 500.
            # С этими настройками битый сокет детектится за ~30 секунд
            # (10 idle + 3*5 интервал), CONN_HEALTH_CHECKS его дропает
            # и Django сразу открывает свежий вместо hang'а на запросе.
            'keepalives': 1,
            'keepalives_idle': 10,
            'keepalives_interval': 5,
            'keepalives_count': 3,
        },
        # Переиспользуем соединение 5 минут — меньше TCP-handshake'ов через границу.
        # CONN_HEALTH_CHECKS пингует перед каждым запросом, мёртвую — переоткрывает.
        'CONN_MAX_AGE': 300,
        'CONN_HEALTH_CHECKS': True,
    }
}

AUTH_USER_MODEL = 'users.User'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
     'OPTIONS': {'user_attributes': ('email', 'name'), 'max_similarity': 0.7}},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
     'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'ru-ru'
# Храним всё в UTC (USE_TZ=True), но в админке и шаблонах показываем московское
# время — сервис российский, клиент ожидает МСК. На само хранение не влияет,
# только на отображение (admin list, поля даты, шаблоны).
TIME_ZONE = 'Europe/Moscow'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'static'
STATICFILES_DIRS = [BASE_DIR / 'static_src']
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# --- Хранилище фото на РФ (152-ФЗ) ---
# Фото анализов = медицинские ПД граждан РФ → должны храниться на сервере в РФ.
# Приложение на KZ, поэтому фото пишутся в MinIO (S3) на РФ-сервере, минуя диск KZ.
# Подключается только к фото-полям через apps.analysis.storages.photo_storage().
# PDF-документы (не ПД) остаются на локальном диске.
USE_S3_PHOTOS = os.environ.get('USE_S3_PHOTOS', 'false').lower() == 'true'
AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID', '')
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY', '')
AWS_STORAGE_BUCKET_NAME = os.environ.get('AWS_STORAGE_BUCKET_NAME', 'teledent-photos')
# Публичный HTTPS-эндпоинт MinIO (медиа-поддомен на РФ). Им же KZ-бэкенд заливает
# фото (PUT) и по нему же генерируются presigned-ссылки для браузера.
AWS_S3_ENDPOINT_URL = os.environ.get('AWS_S3_ENDPOINT_URL', '')
AWS_S3_REGION_NAME = os.environ.get('AWS_S3_REGION_NAME', 'us-east-1')
# Сколько секунд живёт presigned-ссылка. 7 дней (максимум для AWS SigV4) — чтобы
# ссылка на фото не протухала, пока пользователь/админ листает историю или держит
# вкладку открытой. Раньше был 1 час: открытая дольше часа история показывала
# «битые» фото до перезагрузки страницы.
AWS_QUERYSTRING_EXPIRE = int(os.environ.get('AWS_QUERYSTRING_EXPIRE', str(7 * 24 * 3600)))

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB

# Кеш — нужен django-ratelimit. LocMem НЕ ПОДХОДИТ для multi-worker gunicorn,
# счётчик у каждого воркера свой → rate-limit можно обойти раз в N (N=workers).
# Redis даёт общий счётчик на все воркеры. Redis уже в docker-compose как сервис 'redis'.
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': os.environ.get('REDIS_URL', 'redis://redis:6379/1'),
    },
}

# django-ratelimit берёт IP из REMOTE_ADDR. За nginx это адрес прокси, не клиента.
# Поэтому добавляем middleware, которая в самом начале pipeline'а кладёт
# первый IP из X-Forwarded-For в REMOTE_ADDR. Если заголовка нет — REMOTE_ADDR не трогаем.

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'EXCEPTION_HANDLER': 'config.exceptions.ratelimit_aware_exception_handler',
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(
        minutes=int(os.environ.get('JWT_ACCESS_LIFETIME_MINUTES', 30))
    ),
    'REFRESH_TOKEN_LIFETIME': timedelta(
        days=int(os.environ.get('JWT_REFRESH_LIFETIME_DAYS', 7))
    ),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    'TOKEN_OBTAIN_SERIALIZER': 'apps.users.serializers.CustomTokenObtainPairSerializer',
}

CORS_ALLOWED_ORIGINS = os.environ.get(
    'CORS_ALLOWED_ORIGINS',
    'http://109.196.103.11,http://localhost:5173,http://localhost:3000'
).split(',')
CORS_ALLOW_CREDENTIALS = True

# CSRF: нужен для admin/login и любого POST с HTTPS-домена.
# Принимает scheme://host без слешей в конце, через запятую.
CSRF_TRUSTED_ORIGINS = [
    o.strip() for o in os.environ.get(
        'CSRF_TRUSTED_ORIGINS',
        'http://localhost,http://127.0.0.1'
    ).split(',') if o.strip()
]

# Если стоим за обратным прокси (nginx) с HTTPS-терминацией — доверяем X-Forwarded-Proto.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True

JAZZMIN_SETTINGS = {
    "site_title": "Радуга Улыбок",
    "site_header": "Радуга Улыбок",
    "site_brand": "Радуга Улыбок",
    "site_logo": "branding/logo-mark.svg",
    "site_logo_classes": "",
    "login_logo": "branding/logo-mark.svg",
    "site_icon": "branding/logo-mark.svg",
    "custom_css": "branding/admin.css",
    "welcome_sign": "Добро пожаловать в панель управления",
    "copyright": "Радуга Улыбок",
    "search_model": ["users.User", "analysis.Analysis"],
    "topmenu_links": [
        {"name": "Сайт", "url": "/", "new_window": True},
        {"model": "users.User"},
        {"model": "analysis.Analysis"},
    ],
    "usermenu_links": [],
    "show_sidebar": True,
    "navigation_expanded": True,
    "hide_apps": [],
    "hide_models": [],
    "icons": {
        "auth": "fas fa-users-cog",
        "users.User": "fas fa-user",
        "analysis.Analysis": "fas fa-tooth",
        "core.SystemSettings": "fas fa-cog",
        "core.OfficialDocument": "fas fa-certificate",
        "token_blacklist.BlacklistedToken": "fas fa-ban",
        "token_blacklist.OutstandingToken": "fas fa-key",
    },
    "default_icon_parents": "fas fa-chevron-circle-right",
    "default_icon_children": "fas fa-circle",
    "related_modal_active": True,
    "custom_css": None,
    "custom_js": None,
    "use_google_fonts_cdn": False,
    "show_ui_builder": False,
    "changeform_format": "horizontal_tabs",
    "language_chooser": False,
}

JAZZMIN_UI_TWEAKS = {
    "navbar_small_text": False,
    "footer_small_text": False,
    "body_small_text": False,
    "brand_small_text": False,
    "brand_colour": "navbar-primary",
    "accent": "accent-primary",
    "navbar": "navbar-dark",
    "no_navbar_border": True,
    "navbar_fixed": True,
    "layout_boxed": False,
    "footer_fixed": False,
    "sidebar_fixed": True,
    "sidebar": "sidebar-dark-primary",
    "sidebar_nav_small_text": False,
    "sidebar_disable_expand": False,
    "sidebar_nav_child_indent": True,
    "sidebar_nav_compact_style": False,
    "sidebar_nav_legacy_style": False,
    "sidebar_nav_flat_style": False,
    "theme": "default",
    "dark_mode_theme": None,
    "button_classes": {
        "primary": "btn-primary",
        "secondary": "btn-secondary",
        "info": "btn-info",
        "warning": "btn-warning",
        "danger": "btn-danger",
        "success": "btn-success",
    },
}

# --- Email (SMTP) — нужен для восстановления пароля ---
# По умолчанию письма пишутся в консоль (dev/тесты), на проде в .env ставится
# smtp.EmailBackend + креды почтового ящика reg.ru. Пароль ящика — только в .env, не в репо.
EMAIL_BACKEND = os.environ.get('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = os.environ.get('EMAIL_HOST', '')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '465'))
EMAIL_USE_SSL = os.environ.get('EMAIL_USE_SSL', 'true').lower() == 'true'
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'false').lower() == 'true'
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', EMAIL_HOST_USER or 'noreply@radugaulybok-dent.ru')
# Не блокируем gunicorn-воркер надолго, если SMTP-сервер тупит.
EMAIL_TIMEOUT = int(os.environ.get('EMAIL_TIMEOUT', '10'))

# Базовый URL фронта — из него строятся ссылки в письмах (сброс пароля).
FRONTEND_URL = os.environ.get('FRONTEND_URL', 'https://radugaulybok-dent.ru').rstrip('/')

GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')

# OpenRouter — шлюз к Qwen-VL и другим vision-моделям (вторая нейросеть).
# OPENROUTER_APP_URL/TITLE — опциональные атрибуционные заголовки для статистики OpenRouter.
OPENROUTER_API_KEY = os.environ.get('OPENROUTER_API_KEY', '')
OPENROUTER_APP_URL = os.environ.get('OPENROUTER_APP_URL', 'https://radugaulybok-dent.ru')
OPENROUTER_APP_TITLE = os.environ.get('OPENROUTER_APP_TITLE', 'Raduga Ulybok')

# Vertex AI (Google Cloud) — обход IP-блокировки Gemini API.
# Если USE_VERTEX_AI=true, gemini.py создаёт клиент в режиме Vertex и аутентифицируется
# через service account JSON по пути GOOGLE_APPLICATION_CREDENTIALS.
USE_VERTEX_AI = os.environ.get('USE_VERTEX_AI', 'false').lower() == 'true'
GCP_PROJECT_ID = os.environ.get('GCP_PROJECT_ID', '')
GCP_LOCATION = os.environ.get('GCP_LOCATION', 'us-central1')

# GigaChat (Сбер) — третья нейросеть. GIGACHAT_CREDENTIALS = ключ авторизации
# (base64 client_id:secret) из личного кабинета GigaChat; GIGACHAT_SCOPE —
# GIGACHAT_API_PERS (физлица) / GIGACHAT_API_B2B|CORP (бизнес).
# TLS GigaChat подписан «Russian Trusted Root CA»: либо укажите путь к CA-бандлу
# (GIGACHAT_CA_BUNDLE) и оставьте VERIFY_SSL=true, либо VERIFY_SSL=false (дефолт).
# GIGACHAT_BASE_URL — переопределение эндпоинта (например прокси на РФ при гео-блоке).
GIGACHAT_CREDENTIALS = os.environ.get('GIGACHAT_CREDENTIALS', '')
GIGACHAT_SCOPE = os.environ.get('GIGACHAT_SCOPE', 'GIGACHAT_API_PERS')
GIGACHAT_VERIFY_SSL = os.environ.get('GIGACHAT_VERIFY_SSL', 'false').lower() == 'true'
GIGACHAT_CA_BUNDLE = os.environ.get('GIGACHAT_CA_BUNDLE', '')
GIGACHAT_BASE_URL = os.environ.get('GIGACHAT_BASE_URL', '')

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {'console': {'class': 'logging.StreamHandler'}},
    'root': {'handlers': ['console'], 'level': 'INFO'},
}
