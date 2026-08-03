from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_alter_legaldocument_text_html_help'),
    ]

    operations = [
        migrations.CreateModel(
            name='OfficialDocument',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image', models.ImageField(
                    help_text='Картинка JPG или PNG. На сайте показывается миниатюрой, по клику открывается на весь экран.',
                    upload_to='official-docs/', verbose_name='Скан документа')),
                ('caption', models.CharField(
                    help_text='Короткий заголовок под картинкой, например «Свидетельство Роспатента на программу для ЭВМ».',
                    max_length=200, verbose_name='Подпись')),
                ('is_visible', models.BooleanField(
                    default=True,
                    help_text='Снимите галочку, чтобы временно убрать документ с лендинга, не удаляя его.',
                    verbose_name='Показывать на сайте')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Добавлен')),
            ],
            options={
                'verbose_name': 'Официальный документ',
                'verbose_name_plural': 'Официальные документы (лендинг)',
                'ordering': ['created_at', 'id'],
            },
        ),
    ]
