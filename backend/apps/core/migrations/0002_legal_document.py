from django.db import migrations, models
import apps.core.models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='LegalDocument',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('slug', models.CharField(
                    choices=[
                        ('terms', 'Пользовательское соглашение'),
                        ('privacy', 'Политика конфиденциальности'),
                        ('personal-data-consent', 'Согласие на обработку персональных данных (152-ФЗ)'),
                        ('health-data-consent', 'Согласие на обработку данных о здоровье'),
                        ('child-consent', 'Согласие на обработку данных ребёнка'),
                        ('cross-border-consent', 'Согласие на трансграничную передачу'),
                    ],
                    max_length=64, unique=True, verbose_name='Документ',
                )),
                ('pdf', models.FileField(
                    blank=True, null=True,
                    upload_to=apps.core.models.legal_pdf_upload_path,
                    verbose_name='PDF-файл',
                    help_text='Если загружен — открывается вместо текста. Перезаписывается при загрузке нового.',
                )),
                ('text_html', models.TextField(
                    blank=True, verbose_name='Текст HTML (резерв)',
                    help_text='Используется только если PDF не загружен. Допустимы абзацы <p>, '
                              'заголовки <h2>, списки <ul><li>. Без <script>.',
                )),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Правовой документ',
                'verbose_name_plural': 'Правовые документы',
            },
        ),
    ]
