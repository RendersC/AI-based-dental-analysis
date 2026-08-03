# Доработка «Измерение налёта CV-скриптом»: флаг измеренных процентов на анализе
# (участвует в ключе кэша) + фото с подсветкой зон налёта у каждого снимка.

import apps.analysis.storages
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('analysis', '0007_analysis_kind_analysis_observations'),
    ]

    operations = [
        migrations.AddField(
            model_name='analysis',
            name='cv_measured',
            field=models.BooleanField(default=False, verbose_name='Проценты измерены скриптом'),
        ),
        migrations.AddField(
            model_name='analysisphoto',
            name='overlay',
            field=models.ImageField(
                blank=True, null=True,
                storage=apps.analysis.storages.photo_storage,
                upload_to='photos/%Y/%m/',
                verbose_name='Подсветка налёта',
            ),
        ),
    ]
