import os
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver


def instruction_upload_path(instance, filename):
    return 'instruction/instruction.pdf'


class Instruction(models.Model):
    pdf = models.FileField(upload_to=instruction_upload_path)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Инструкция'
        verbose_name_plural = 'Инструкция'

    def __str__(self):
        return 'Инструкция (PDF)'

    def save(self, *args, **kwargs):
        # Singleton: всегда pk=1, при замене удаляем старый файл
        self.pk = 1
        if self.pk and Instruction.objects.filter(pk=1).exists():
            old = Instruction.objects.get(pk=1)
            if old.pdf and old.pdf.name != self.pdf.name and os.path.isfile(old.pdf.path):
                try:
                    os.remove(old.pdf.path)
                except OSError:
                    pass
        super().save(*args, **kwargs)

    @classmethod
    def get_current(cls):
        return cls.objects.filter(pk=1).first()


class SystemSettings(models.Model):
    key = models.CharField(max_length=100, unique=True)
    value = models.TextField()

    class Meta:
        verbose_name = 'Настройка'
        verbose_name_plural = 'Настройки системы'

    def __str__(self):
        return f"{self.key}: {self.value[:50]}"

    @classmethod
    def get(cls, key, default=None):
        try:
            return cls.objects.get(key=key).value
        except cls.DoesNotExist:
            return default

    @classmethod
    def survey_version(cls):
        """Текущая версия анкеты (целое, >=1). Битое/пустое значение трактуем как 1."""
        try:
            return max(1, int(cls.get('survey_version', '1') or '1'))
        except (TypeError, ValueError):
            return 1


def legal_pdf_upload_path(instance, filename):
    # Перезаписываем PDF при загрузке нового — один слот, одно имя.
    return f'legal/{instance.slug}.pdf'


class LegalDocument(models.Model):
    """Правовые документы: соглашения, политики, согласия. По одному слоту на каждый.
    Админ загружает PDF — он отдаётся при клике, либо если PDF нет — рендерится text_html."""

    SLUG_CHOICES = [
        ('terms', 'Пользовательское соглашение'),
        ('privacy', 'Политика конфиденциальности'),
        ('personal-data-consent', 'Согласие на обработку персональных данных (152-ФЗ)'),
        ('health-data-consent', 'Согласие на обработку данных о здоровье'),
        ('child-consent', 'Согласие на обработку данных ребёнка'),
        ('cross-border-consent', 'Согласие на трансграничную передачу'),
        ('cookie-policy', 'Политика использования файлов cookie'),
    ]

    slug = models.CharField(max_length=64, unique=True, choices=SLUG_CHOICES, verbose_name='Документ')
    pdf = models.FileField(
        upload_to=legal_pdf_upload_path, blank=True, null=True, verbose_name='PDF-файл',
        help_text='Если загружен — открывается вместо текста. Перезаписывается при загрузке нового.',
    )
    text_html = models.TextField(
        blank=True, verbose_name='Текст HTML (резерв)',
        # ВНИМАНИЕ: Django рендерит help_text в админке как HTML (без экранирования).
        # Поэтому теги пишем сущностями (&lt;p&gt;), иначе сырые <ul><li>/<p> ломают
        # вёрстку страницы и «съедают» кнопку «Сохранить» внизу формы.
        help_text='Используется только если PDF не загружен. Допустимы абзацы &lt;p&gt;, '
                  'заголовки &lt;h2&gt;, списки &lt;ul&gt;&lt;li&gt;. Без &lt;script&gt;.',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Правовой документ'
        verbose_name_plural = 'Правовые документы'

    def __str__(self):
        return dict(self.SLUG_CHOICES).get(self.slug, self.slug)

    @property
    def title(self) -> str:
        return dict(self.SLUG_CHOICES).get(self.slug, self.slug)


class OfficialDocument(models.Model):
    """Скан официального документа проекта (свидетельство Роспатента и т.п.)
    для блока «Официальный статус проекта» на лендинге.

    Это не персональные данные, поэтому файлы лежат на локальном диске в MEDIA
    (как PDF инструкции и правовых документов) и отдаются nginx'ом публично —
    presigned-ссылки MinIO тут не нужны, лендинг открыт без авторизации.
    """

    image = models.ImageField(
        upload_to='official-docs/', verbose_name='Скан документа',
        help_text='Картинка JPG или PNG. На сайте показывается миниатюрой, '
                  'по клику открывается на весь экран.',
    )
    caption = models.CharField(
        max_length=200, verbose_name='Подпись',
        help_text='Короткий заголовок под картинкой, например '
                  '«Свидетельство Роспатента на программу для ЭВМ».',
    )
    is_visible = models.BooleanField(
        default=True, verbose_name='Показывать на сайте',
        help_text='Снимите галочку, чтобы временно убрать документ с лендинга, не удаляя его.',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Добавлен')

    class Meta:
        verbose_name = 'Официальный документ'
        verbose_name_plural = 'Официальные документы (лендинг)'
        # Ручной сортировки по ТЗ нет, поэтому порядок фиксируем от старых к новым:
        # уже опубликованные карточки остаются на своих местах, новый документ
        # добавляется в конец сетки. Без явного ordering порядок задавала бы БД
        # и блок мог бы перетасовываться между запросами.
        ordering = ['created_at', 'id']

    def __str__(self):
        return self.caption or f'Документ #{self.pk}'


@receiver(post_delete, sender=OfficialDocument)
def _delete_official_document_file(sender, instance, **kwargs):
    """Удаляем картинку с диска вместе с записью.

    Django сам файлы не трогает, а /media/ отдаётся nginx'ом напрямую: без этого
    убранный из админки скан продолжал бы открываться по прямой ссылке и копиться
    на диске. save=False обязателен — строки в БД уже нет."""
    if instance.image:
        instance.image.delete(save=False)
