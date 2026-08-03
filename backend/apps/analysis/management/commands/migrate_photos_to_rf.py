"""Перенос существующих фото анализов с локального диска KZ в MinIO на РФ.

По 152-ФЗ фото (медицинские ПД граждан РФ) должны лежать на РФ. Старые фото лежат
на диске KZ в MEDIA_ROOT/photos/. Команда читает каждый файл из локального хранилища
и заливает в S3 (MinIO на РФ) под тем же ключом (.name), что записан в БД, поэтому
строки в БД менять не нужно — ссылки продолжают резолвиться, только уже из S3.

Порядок безопасного боевого прогона:
  1. python manage.py migrate_photos_to_rf --dry-run      # посмотреть что будет
  2. python manage.py migrate_photos_to_rf                # залить в S3 (без удаления)
  3. убедиться что фото открываются в приложении/админке
  4. python manage.py migrate_photos_to_rf --delete-local # удалить копии с диска KZ

Требует USE_S3_PHOTOS=true и настроенные AWS_* — иначе фото-поля используют локальное
хранилище и заливать некуда.
"""
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from django.core.management.base import BaseCommand, CommandError

from apps.analysis.models import Analysis, AnalysisPhoto
from apps.analysis.storages import _build_s3_storage


class Command(BaseCommand):
    help = 'Переносит фото анализов с локального диска в MinIO (S3) на РФ-сервере.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Только показать, что будет перенесено, ничего не заливать.',
        )
        parser.add_argument(
            '--delete-local', action='store_true',
            help='После успешной заливки удалить локальные файлы с диска KZ.',
        )

    def handle(self, *args, **opts):
        dry_run = opts['dry_run']
        delete_local = opts['delete_local']

        if not settings.USE_S3_PHOTOS:
            raise CommandError(
                'USE_S3_PHOTOS=false — фото-поля используют локальное хранилище. '
                'Включите S3 (USE_S3_PHOTOS=true + AWS_*) перед переносом.'
            )

        local = FileSystemStorage(location=settings.MEDIA_ROOT)
        s3 = _build_s3_storage()

        # Собираем уникальные имена файлов из обеих моделей.
        names = []
        for p in AnalysisPhoto.objects.exclude(photo='').iterator():
            if p.photo:
                names.append(p.photo.name)
        for a in Analysis.objects.exclude(photo_url='').iterator():
            if a.photo_url:
                names.append(a.photo_url.name)
        # dict.fromkeys сохраняет порядок и убирает дубли.
        names = list(dict.fromkeys(names))

        self.stdout.write(f'Найдено файлов для переноса: {len(names)}')

        uploaded = skipped_missing = already = deleted = errors = 0

        for name in names:
            if not local.exists(name):
                self.stdout.write(self.style.WARNING(f'  НЕТ на диске: {name}'))
                skipped_missing += 1
                continue

            try:
                with local.open(name, 'rb') as fh:
                    data = fh.read()
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  Ошибка чтения {name}: {e}'))
                errors += 1
                continue

            if s3.exists(name):
                already += 1
                action = 'уже в S3 (перезалью для надёжности)'
            else:
                action = 'заливаю'

            self.stdout.write(f'  {action}: {name} ({len(data)} байт)')

            if dry_run:
                continue

            try:
                # file_overwrite=True → save вернёт тот же ключ, без суффикса.
                s3.save(name, ContentFile(data))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  Ошибка заливки {name}: {e}'))
                errors += 1
                continue

            # Проверяем, что объект на месте и размер совпадает.
            try:
                remote_size = s3.size(name)
            except Exception:
                remote_size = None
            if remote_size is not None and remote_size != len(data):
                self.stdout.write(self.style.ERROR(
                    f'  РАЗМЕР НЕ СОВПАЛ {name}: локально {len(data)}, в S3 {remote_size}'
                ))
                errors += 1
                continue

            uploaded += 1

            if delete_local:
                try:
                    local.delete(name)
                    deleted += 1
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f'  Не удалил локально {name}: {e}'))

        self.stdout.write('')
        if dry_run:
            self.stdout.write(self.style.SUCCESS(
                f'DRY-RUN: к переносу {len(names)}, нет на диске {skipped_missing}, '
                f'уже в S3 {already}.'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'Готово. Залито: {uploaded}, удалено локально: {deleted}, '
                f'нет на диске: {skipped_missing}, ошибок: {errors}.'
            ))
        if errors:
            raise CommandError(f'Завершено с ошибками: {errors}. См. лог выше.')
