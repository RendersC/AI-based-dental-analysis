from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_legal_document'),
    ]

    operations = [
        migrations.AlterField(
            model_name='legaldocument',
            name='slug',
            field=models.CharField(
                choices=[
                    ('terms', 'Пользовательское соглашение'),
                    ('privacy', 'Политика конфиденциальности'),
                    ('personal-data-consent', 'Согласие на обработку персональных данных (152-ФЗ)'),
                    ('health-data-consent', 'Согласие на обработку данных о здоровье'),
                    ('child-consent', 'Согласие на обработку данных ребёнка'),
                    ('cross-border-consent', 'Согласие на трансграничную передачу'),
                    ('cookie-policy', 'Политика использования файлов cookie'),
                ],
                max_length=64, unique=True, verbose_name='Документ',
            ),
        ),
    ]
