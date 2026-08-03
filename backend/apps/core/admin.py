from django import forms
from django.contrib import admin
from django.utils.html import format_html
from .models import Instruction, SystemSettings, LegalDocument, OfficialDocument
from apps.analysis.services.gemini import AVAILABLE_MODELS as GEMINI_MODELS
from apps.analysis.services.qwen import AVAILABLE_MODELS as QWEN_MODELS
from apps.analysis.services.gigachat import AVAILABLE_MODELS as GIGACHAT_MODELS

PROVIDER_CHOICES = [
    ('gemini', 'Gemini (Google)'),
    ('qwen', 'Qwen3-VL (через OpenRouter)'),
    ('gigachat', 'GigaChat (Сбер)'),
]

# Объединённый список доступных моделей для всех провайдеров.
# Админ выбирает любую — роутер по провайдеру направляет в нужную сеть
# (qwen/* → OpenRouter, GigaChat* → Сбер, остальное → Gemini).
ALL_MODEL_CHOICES = [(m, m) for m in GEMINI_MODELS + QWEN_MODELS + GIGACHAT_MODELS]

# Настройки экспресс-оценки допускают пустое значение = «как в основном анализе».
# Пустой вариант первым: по умолчанию режимы работают на одной сети, как раньше.
INHERIT_LABEL = '— как в основном анализе —'
PROVIDER_CHOICES_EXPRESS = [('', INHERIT_LABEL)] + PROVIDER_CHOICES
ALL_MODEL_CHOICES_EXPRESS = [('', INHERIT_LABEL)] + ALL_MODEL_CHOICES


# Понятные названия ключей — чтобы в списке настроек клиент видел человеческие
# подписи (например «Ссылка на анкету»), а не технические key вроде survey_url.
SETTINGS_LABELS = {
    'ai_provider': 'Активная нейросеть (анализ с индикатором)',
    'ai_model': 'Модель нейросети (анализ с индикатором)',
    'ai_provider_express': 'Активная нейросеть (экспресс-оценка)',
    'ai_model_express': 'Модель нейросети (экспресс-оценка)',
    'cv_plaque_enabled': 'Скрипт измерения налёта (вкл/выкл)',
    'survey_url': 'Ссылка на анкету (опрос)',
    'survey_version': 'Версия анкеты (служебное)',
    'initial_attempts': 'Анализов с индикатором при регистрации',
    'initial_express_attempts': 'Экспресс-оценок при регистрации',
    'prompt_text': 'Промпт: общий (анализ с индикатором)',
    'prompt_milk': 'Промпт: молочный прикус',
    'prompt_mixed': 'Промпт: сменный прикус',
    'prompt_permanent': 'Промпт: постоянный прикус',
    'prompt_express': 'Промпт: экспресс-оценка (без индикатора)',
}


@admin.register(SystemSettings)
class SystemSettingsAdmin(admin.ModelAdmin):
    list_display = ['key_label', 'key', 'value_preview']
    search_fields = ['key']
    actions = ['reset_survey_completion']

    def key_label(self, obj):
        return SETTINGS_LABELS.get(obj.key, obj.key)
    key_label.short_description = 'Настройка'

    def value_preview(self, obj):
        return obj.value[:100] + '...' if len(obj.value) > 100 else obj.value
    value_preview.short_description = 'Значение'

    @admin.action(description='🔄 Предложить анкету заново всем пользователям (сброс прохождения)')
    def reset_survey_completion(self, request, queryset):
        """Увеличивает survey_version на 1 — после этого анкета снова начинает
        предлагаться всем, в том числе тем, кто уже прошёл предыдущую версию.
        Выделение строк роли не играет — действие всегда работает с survey_version."""
        obj, _ = SystemSettings.objects.get_or_create(key='survey_version', defaults={'value': '1'})
        try:
            new_version = int(obj.value) + 1
        except (TypeError, ValueError):
            new_version = 2
        obj.value = str(new_version)
        obj.save()
        self.message_user(
            request,
            f'Готово. Анкета (версия {new_version}) снова будет предлагаться всем пользователям.',
        )

    def get_form(self, request, obj=None, **kwargs):
        """Для ключей ai_provider / ai_model подменяем textarea на выпадающий список —
        чтобы клиент в админке мог переключать сеть и модель кликом, не угадывая имя."""
        form = super().get_form(request, obj, **kwargs)
        if obj is None:
            return form

        if obj.key == 'survey_url':
            class SurveyUrlForm(form):
                value = forms.URLField(
                    required=False,
                    label='Ссылка на анкету (Яндекс.Формы)',
                    help_text='Вставьте ссылку на форму. Пусто — анкета нигде не показывается. '
                              'Если поменяли вопросы в форме — выберите любую строку и примените '
                              'действие «Предложить анкету заново всем».',
                )
            return SurveyUrlForm

        if obj.key == 'ai_provider':
            class ProviderForm(form):
                value = forms.ChoiceField(
                    choices=PROVIDER_CHOICES,
                    label='Активная нейросеть (анализ с индикатором)',
                    help_text='Со следующего анализа запросы идут к выбранной сети. '
                              'Перезапуск не нужен. Экспресс-оценка настраивается отдельно.',
                )
            return ProviderForm

        if obj.key == 'ai_model':
            class ModelForm(form):
                value = forms.ChoiceField(
                    choices=ALL_MODEL_CHOICES,
                    label='Модель (анализ с индикатором)',
                    help_text='Список моделей всех сетей. Модель работает только когда выбран '
                              'её провайдер: gemini-* при провайдере Gemini, qwen/* при Qwen, '
                              'GigaChat* при GigaChat.',
                )
            return ModelForm

        if obj.key == 'cv_plaque_enabled':
            class CvEnabledForm(form):
                value = forms.ChoiceField(
                    choices=[
                        ('true', 'Включён — проценты налёта измеряет скрипт по пикселям красителя'),
                        ('false', 'Выключен — проценты оценивает нейросеть (как раньше)'),
                    ],
                    label='Скрипт измерения налёта',
                    help_text='Действует со следующего анализа с индикатором, перезапуск не нужен. '
                              'При включённом скрипте в личном кабинете появляется фото с подсветкой '
                              'зон налёта. Если скрипт не распознаёт зубы на конкретном фото, этот '
                              'анализ автоматически выполняется нейросетью, как при выключенном скрипте.',
                )
            return CvEnabledForm

        if obj.key == 'ai_provider_express':
            class ProviderExpressForm(form):
                value = forms.ChoiceField(
                    choices=PROVIDER_CHOICES_EXPRESS,
                    required=False,
                    label='Активная нейросеть (экспресс-оценка)',
                    help_text='Сеть только для экспресс-оценки. Оставьте «как в основном '
                              'анализе», чтобы оба режима работали на одной сети.',
                )
            return ProviderExpressForm

        if obj.key == 'ai_model_express':
            class ModelExpressForm(form):
                value = forms.ChoiceField(
                    choices=ALL_MODEL_CHOICES_EXPRESS,
                    required=False,
                    label='Модель (экспресс-оценка)',
                    help_text='Модель должна принадлежать сети, выбранной для экспресс-оценки. '
                              'Если оставить пусто, берётся модель по умолчанию для этой сети.',
                )
            return ModelExpressForm

        return form


@admin.register(LegalDocument)
class LegalDocumentAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'has_pdf', 'has_text', 'updated_at', 'public_link']
    readonly_fields = ['updated_at', 'public_link']
    fields = ['slug', 'pdf', 'text_html', 'public_link', 'updated_at']
    # Удалять нельзя — 6 слотов это фиксированный набор согласий, юристом утверждён.
    # Добавлять можно только пока не созданы все 6 (init_settings создаёт автоматически).

    def has_pdf(self, obj):
        return bool(obj.pdf)
    has_pdf.boolean = True
    has_pdf.short_description = 'PDF'

    def has_text(self, obj):
        return bool(obj.text_html.strip()) if obj.text_html else False
    has_text.boolean = True
    has_text.short_description = 'HTML текст'

    def public_link(self, obj):
        if not obj or not obj.pk:
            return '—'
        return format_html(
            '<a href="/docs/{}.html" target="_blank" rel="noopener">Открыть как видит пользователь</a>',
            obj.slug,
        )
    public_link.short_description = 'Просмотр'

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        # Разрешить добавление только если есть незанятые слаги
        used = set(LegalDocument.objects.values_list('slug', flat=True))
        return any(s not in used for s, _ in LegalDocument.SLUG_CHOICES)


@admin.register(OfficialDocument)
class OfficialDocumentAdmin(admin.ModelAdmin):
    """Блок «Официальный статус проекта» на лендинге: загрузка скана + подпись.

    Ручной сортировки нет по согласованному ТЗ — порядок на сайте от старых
    к новым (Meta.ordering), новый документ встаёт в конец сетки."""

    list_display = ['thumb', 'caption', 'is_visible', 'created_at']
    list_display_links = ['thumb', 'caption']
    list_editable = ['is_visible']
    list_filter = ['is_visible']
    search_fields = ['caption']
    readonly_fields = ['preview', 'created_at']
    fields = ['image', 'preview', 'caption', 'is_visible', 'created_at']

    def thumb(self, obj):
        if not obj.image:
            return '—'
        return format_html(
            '<img src="{}" style="height:56px;width:auto;border:1px solid #E2E8F0;'
            'border-radius:4px;background:#fff" />',
            obj.image.url,
        )
    thumb.short_description = 'Миниатюра'

    def preview(self, obj):
        if not obj or not obj.image:
            return 'Загрузите файл и сохраните — здесь появится предпросмотр.'
        return format_html(
            '<a href="{}" target="_blank" rel="noopener">'
            '<img src="{}" style="max-width:420px;height:auto;border:1px solid #E2E8F0;'
            'border-radius:6px;background:#fff" /></a>',
            obj.image.url, obj.image.url,
        )
    preview.short_description = 'Как выглядит скан'


@admin.register(Instruction)
class InstructionAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'current_link', 'updated_at']
    readonly_fields = ['updated_at', 'current_link']
    fields = ['pdf', 'current_link', 'updated_at']

    def current_link(self, obj):
        if obj and obj.pdf:
            # ?v=<updated_at> — обходит кеш браузера, иначе после замены файла
            # по той же ссылке открывается старая версия (имя файла фиксированное).
            url = f"{obj.pdf.url}?v={int(obj.updated_at.timestamp())}"
            return format_html('<a href="{}" target="_blank" rel="noopener">Открыть текущий PDF</a>', url)
        return '—'
    current_link.short_description = 'Текущий файл'

    def has_add_permission(self, request):
        # Singleton: добавлять можно только если ещё нет ни одной записи
        return not Instruction.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
