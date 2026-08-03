from django.db import migrations

DEFAULT_EXPRESS_ATTEMPTS = 3


def backfill(apps, schema_editor):
    """Выдаём бесплатные экспресс-оценки тем, кто зарегистрировался ДО появления фичи.

    Новым аккаунтам счётчик проставляет регистрация. Без этой миграции все текущие
    пользователи (включая тестировщиков клиники) получили бы 0 и не увидели бы новый
    режим вообще. Количество берём из настройки initial_express_attempts, чтобы оно
    совпадало с тем, что получают новички.
    """
    User = apps.get_model('users', 'User')
    SystemSettings = apps.get_model('core', 'SystemSettings')

    amount = DEFAULT_EXPRESS_ATTEMPTS
    row = SystemSettings.objects.filter(key='initial_express_attempts').first()
    if row is not None:
        try:
            amount = int(str(row.value).strip())
        except (TypeError, ValueError):
            amount = DEFAULT_EXPRESS_ATTEMPTS

    # Только тем, у кого счётчик нулевой — чтобы повторный прогон миграции
    # не «доливал» попытки тем, кто их уже потратил.
    User.objects.filter(express_attempts_left=0).update(express_attempts_left=amount)


def noop(apps, schema_editor):
    """Откат не отбирает попытки обратно: поле всё равно удаляется откатом 0005."""


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0005_user_express_attempts_left_alter_user_attempts_left'),
        # init_settings создаёт initial_express_attempts, но на чистой базе миграции
        # идут раньше него — зависимость нужна только чтобы модель SystemSettings
        # существовала на момент чтения.
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(backfill, noop),
    ]
