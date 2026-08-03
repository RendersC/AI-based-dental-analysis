from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('analysis', '0002_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='analysis',
            name='age_group',
            field=models.CharField(
                blank=True,
                choices=[
                    ('milk', 'Молочный прикус (3–5 лет)'),
                    ('mixed', 'Сменный прикус (6–11 лет)'),
                    ('permanent_teen', 'Постоянный прикус, подростки (12–17 лет)'),
                    ('permanent_adult', 'Постоянный прикус, взрослые (18+)'),
                ],
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='analysis',
            name='legal_rep_consent',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='analysis',
            name='consent_ip',
            field=models.CharField(blank=True, max_length=45),
        ),
        migrations.AddField(
            model_name='analysis',
            name='consent_datetime',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='analysis',
            name='consent_text_version',
            field=models.CharField(blank=True, max_length=50),
        ),
        migrations.CreateModel(
            name='AnalysisPhoto',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('photo', models.ImageField(upload_to='photos/%Y/%m/')),
                ('order', models.PositiveSmallIntegerField(default=0)),
                ('analysis', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='photos',
                    to='analysis.analysis',
                )),
            ],
            options={
                'verbose_name': 'Фото анализа',
                'verbose_name_plural': 'Фото анализов',
                'ordering': ['analysis', 'order'],
            },
        ),
    ]
