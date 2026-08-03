from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0003_user_survey_completed_version'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='role',
            field=models.CharField(
                choices=[
                    ('patient', 'Пациент'),
                    ('doctor', 'Врач'),
                    ('admin', 'Администратор'),
                    ('expert', 'Эксперт (ограниченный администратор)'),
                ],
                default='patient',
                max_length=10,
            ),
        ),
    ]
