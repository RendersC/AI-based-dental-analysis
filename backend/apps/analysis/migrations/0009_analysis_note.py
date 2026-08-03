# Заметка пользователя к анализу (доп. задача, оплачена 2026-07-20): свободный
# текст, который пациент оставляет при создании анализа — виден в истории ЛК
# и в админке. В промт ИИ не подмешивается.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('analysis', '0008_cv_measured_overlay'),
    ]

    operations = [
        migrations.AddField(
            model_name='analysis',
            name='note',
            field=models.TextField(blank=True, default='', verbose_name='Заметка пользователя'),
        ),
    ]
