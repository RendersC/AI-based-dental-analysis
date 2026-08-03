from django.db import models
from django.conf import settings

from .storages import photo_storage


AGE_GROUP_CHOICES = [
    ('milk', 'Молочный прикус (3–5 лет)'),
    ('mixed', 'Сменный прикус (6–11 лет)'),
    ('permanent_teen', 'Постоянный прикус, подростки (12–17 лет)'),
    ('permanent_adult', 'Постоянный прикус, взрослые (18+)'),
]

AGE_GROUP_TO_PROMPT_KEY = {
    'milk': 'prompt_milk',
    'mixed': 'prompt_mixed',
    'permanent_teen': 'prompt_permanent',
    'permanent_adult': 'prompt_permanent',
}

CONSENT_TEXT_VERSION = 'child_consent_v1_2026_06'

# Тип анализа. Ключи ТЕХНИЧЕСКИЕ и не завязаны на витринное название:
# заказчик может переименовать «Экспресс-оценку» в интерфейсе, не трогая БД.
#   indicator — полный анализ по фото с индикатором налёта: даёт балл, проценты,
#               зоны, участвует в динамике. Это ядро продукта.
#   express   — экспресс-оценка по одному фото БЕЗ индикатора: только качественные
#               наблюдения текстом. Ни балла, ни процентов — без индикатора мерить
#               нечего, а просить цифры у модели значит получить выдуманные.
KIND_INDICATOR = 'indicator'
KIND_EXPRESS = 'express'
KIND_CHOICES = [
    (KIND_INDICATOR, 'Анализ с индикатором'),
    (KIND_EXPRESS, 'Экспресс-оценка'),
]


class Analysis(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='analyses',
    )
    kind = models.CharField(
        max_length=20,
        choices=KIND_CHOICES,
        default=KIND_INDICATOR,
        db_index=True,
        verbose_name='Тип анализа',
    )
    # legacy single photo (старые записи); новые анализы используют related AnalysisPhoto
    photo_url = models.ImageField(upload_to='photos/%Y/%m/', blank=True, storage=photo_storage)
    age_group = models.CharField(max_length=20, choices=AGE_GROUP_CHOICES, blank=True)
    legal_rep_consent = models.BooleanField(default=False)
    consent_ip = models.CharField(max_length=45, blank=True)
    consent_datetime = models.DateTimeField(null=True, blank=True)
    consent_text_version = models.CharField(max_length=50, blank=True)
    score = models.FloatField(null=True, blank=True)
    fresh_plaque_percent = models.FloatField(null=True, blank=True)
    old_plaque_percent = models.FloatField(null=True, blank=True)
    problem_zones = models.JSONField(default=list, blank=True)
    # Качественные наблюдения экспресс-оценки (список строк). Только для kind=express:
    # у полного анализа роль «что видно» играют problem_zones вместе с процентами.
    observations = models.JSONField(default=list, blank=True, verbose_name='Наблюдения (экспресс-оценка)')
    recommendations = models.JSONField(default=list, blank=True)
    dynamics_text = models.TextField(blank=True)
    # Свободная заметка пользователя к анализу (например, что изменилось в уходе
    # с прошлого раза). Не уходит в промт ИИ — это личная пометка для истории.
    note = models.TextField(blank=True, default='', verbose_name='Заметка пользователя')
    doctor_comment = models.TextField(blank=True)
    ai_model = models.CharField(max_length=100, blank=True)
    raw_response = models.TextField(blank=True)
    # sha256 от набора фото (детерминированный по содержимому, не по порядку) —
    # для кэша результата при повторной загрузке тех же фото.
    photos_hash = models.CharField(max_length=64, blank=True, default='', db_index=True)
    # sha256 от базового промта на момент анализа — кэш учитывает версию промта,
    # чтобы обновление промта инвалидировало старые закэшированные результаты.
    prompt_hash = models.CharField(max_length=64, blank=True, default='', db_index=True)
    # Проценты налёта ИЗМЕРЕНЫ CV-скриптом (а не оценены нейросетью). Участвует
    # в ключе кэша: результат с измеренными цифрами нельзя переиспользовать,
    # когда скрипт выключен, и наоборот.
    cv_measured = models.BooleanField(default=False, verbose_name='Проценты измерены скриптом')
    is_valid = models.BooleanField(default=True)
    attempt_deducted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Анализ'
        verbose_name_plural = 'Анализы'
        ordering = ['-created_at']
        # Отдельное право на выгрузку в CSV/Excel: НЕ входит в группу «Эксперт»
        # (см. permissions_setup.EXPERT_PERMS) — по умолчанию есть только у
        # суперпользователя, конкретному эксперту выдаётся вручную через
        # user_permissions на странице пользователя.
        permissions = [
            ('export_analysis', 'Может выгружать анализы в CSV/Excel'),
        ]

    def __str__(self):
        return f"{self.get_kind_display()} {self.user.name} от {self.created_at.strftime('%d.%m.%Y')}"

    @property
    def is_express(self):
        return self.kind == KIND_EXPRESS

    @property
    def all_photos(self):
        photos = list(self.photos.all())
        if photos:
            return photos
        if self.photo_url:
            return [type('LegacyPhoto', (), {'photo': self.photo_url, 'order': 0})()]
        return []


class AnalysisPhoto(models.Model):
    analysis = models.ForeignKey(
        Analysis,
        on_delete=models.CASCADE,
        related_name='photos',
    )
    photo = models.ImageField(upload_to='photos/%Y/%m/', storage=photo_storage)
    # Фото с подсветкой зон налёта от CV-скрипта. Есть только у анализов,
    # где скрипт был включён и смог измерить: нет измерения — нет подсветки.
    overlay = models.ImageField(
        upload_to='photos/%Y/%m/', storage=photo_storage,
        null=True, blank=True, verbose_name='Подсветка налёта',
    )
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = 'Фото анализа'
        verbose_name_plural = 'Фото анализов'
        ordering = ['analysis', 'order']

    def __str__(self):
        return f"Фото #{self.order} анализа {self.analysis_id}"
