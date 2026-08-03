from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_legaldocument_cookie_policy_slug'),
    ]

    operations = [
        migrations.AlterField(
            model_name='legaldocument',
            name='text_html',
            field=models.TextField(
                blank=True,
                help_text='Используется только если PDF не загружен. Допустимы абзацы &lt;p&gt;, '
                          'заголовки &lt;h2&gt;, списки &lt;ul&gt;&lt;li&gt;. Без &lt;script&gt;.',
                verbose_name='Текст HTML (резерв)',
            ),
        ),
    ]
