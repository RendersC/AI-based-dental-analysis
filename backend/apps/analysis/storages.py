"""Хранилище фото анализов.

По 152-ФЗ персональные данные граждан РФ (фото зубов = медицинские ПД) должны
храниться на серверах в РФ. Приложение крутится на KZ-сервере, поэтому фото
пишутся потоком в объектное хранилище MinIO (S3-совместимое) на РФ-сервере, минуя
диск KZ. Раздаются браузеру временными подписанными ссылками (presigned) через
медиа-поддомен на РФ.

PDF-документы (инструкция, юр-доки) — НЕ ПД, остаются на локальном диске KZ,
поэтому S3 подключается только к двум фото-полям через колбэк photo_storage(),
а не глобально через DEFAULT_FILE_STORAGE.
"""
from django.conf import settings
from django.core.files.storage import default_storage


def _build_s3_storage():
    """Создаёт S3Storage, настроенный под MinIO на РФ. Импорт storages внутри,
    чтобы зависимость требовалась только когда S3 реально включён."""
    from storages.backends.s3 import S3Storage

    return S3Storage(
        bucket_name=settings.AWS_STORAGE_BUCKET_NAME,
        endpoint_url=settings.AWS_S3_ENDPOINT_URL,
        access_key=settings.AWS_ACCESS_KEY_ID,
        secret_key=settings.AWS_SECRET_ACCESS_KEY,
        # region_name обязателен вместе с endpoint_url, иначе boto3 кидает
        # AuthorizationQueryParametersError при подписи. MinIO по умолчанию us-east-1.
        region_name=settings.AWS_S3_REGION_NAME,
        # path-style: https://endpoint/<bucket>/<key>. MinIO не умеет virtual-host
        # стиль без wildcard-DNS, поэтому только path.
        addressing_style='path',
        signature_version='s3v4',
        # presigned-ссылки с TTL — фото медицинские, постоянный публичный доступ нельзя.
        querystring_auth=True,
        querystring_expire=settings.AWS_QUERYSTRING_EXPIRE,
        # приватный бакет
        default_acl=None,
        # имена файлов у нас уникальны (analysis_<id>_...), перезапись безопасна и
        # сохраняет детерминированный ключ (важно для миграции старых файлов).
        file_overwrite=True,
    )


def photo_storage():
    """Колбэк выбора хранилища для фото-полей.

    Module-level функция — Django сериализует её в миграции по import-пути, поэтому
    переключение USE_S3_PHOTOS через env НЕ требует новой миграции. Когда S3 выключен
    (локальная разработка, тесты) — обычный FileSystemStorage.
    """
    if getattr(settings, 'USE_S3_PHOTOS', False):
        return _build_s3_storage()
    return default_storage
