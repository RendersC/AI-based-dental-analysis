from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('analysis', '0009_analysis_note'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='analysis',
            options={
                'ordering': ['-created_at'],
                'permissions': [('export_analysis', 'Может выгружать анализы в CSV/Excel')],
                'verbose_name': 'Анализ',
                'verbose_name_plural': 'Анализы',
            },
        ),
    ]
