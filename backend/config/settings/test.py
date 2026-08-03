"""Настройки для автотестов: локальный SQLite вместо боевого Postgres на РФ
и LocMem вместо Redis. Так тесты гоняются где угодно (CI / контейнер) без сети
до RU-сервера. Прод использует config.settings.base."""
from .base import *  # noqa: F401,F403

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}

# Фото в тестах не уходят в MinIO.
USE_S3_PHOTOS = False
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
