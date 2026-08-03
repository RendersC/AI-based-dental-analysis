from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0002_user_date_of_birth'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='survey_completed_version',
            field=models.PositiveIntegerField(default=0),
        ),
    ]
