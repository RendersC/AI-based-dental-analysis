import csv

from django.contrib import admin, messages
from django.http import HttpResponse
from django.utils import timezone
from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe
from .models import Analysis, AnalysisPhoto

# Право на выгрузку. Есть у суперпользователя всегда; эксперту выдаётся
# поштучно галочкой на его странице (см. apps/users/admin.py) — в группу
# «Эксперт» это право НЕ входит, поэтому по умолчанию у экспертов его нет.
EXPORT_PERM = 'analysis.export_analysis'


def _join_list(value):
    """JSON-списки (зоны/наблюдения/рекомендации) в одну ячейку CSV."""
    if isinstance(value, (list, tuple)):
        return '; '.join(str(v) for v in value)
    return '' if value is None else str(value)


def _yes_no(value):
    return 'Да' if value else 'Нет'


class AnalysisPhotoInline(admin.TabularInline):
    model = AnalysisPhoto
    extra = 0
    readonly_fields = ['preview', 'order']
    fields = ['preview', 'photo', 'order']

    def preview(self, obj):
        if obj.photo:
            return format_html(
                '<a href="{0}" target="_blank" rel="noopener">'
                '<img src="{0}" style="max-height:120px;max-width:120px;border:1px solid #ddd;border-radius:4px"/></a>',
                obj.photo.url,
            )
        return '—'
    preview.short_description = 'Превью'

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Analysis)
class AnalysisAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'kind_badge', 'age_group_badge', 'consent_badge', 'photos_thumbs',
        'score_display', 'is_valid', 'attempt_deducted', 'created_at',
    ]
    # «Тип анализа» — первым: клиент смотрит списки отдельно по экспресс-оценкам
    # и отдельно по анализам с индикатором, вперемешку они не нужны.
    list_filter = ['kind', 'age_group', 'legal_rep_consent', 'is_valid', 'attempt_deducted']
    search_fields = ['user__email', 'user__name']
    readonly_fields = [
        'user', 'kind', 'photo_url', 'photos_full', 'age_group', 'legal_rep_consent',
        'consent_ip', 'consent_datetime', 'consent_text_version',
        'score', 'fresh_plaque_percent', 'old_plaque_percent',
        'problem_zones', 'observations', 'recommendations', 'dynamics_text', 'note', 'ai_model',
        'raw_response', 'is_valid', 'attempt_deducted', 'created_at',
    ]
    ordering = ['-created_at']
    inlines = [AnalysisPhotoInline]
    actions = ['export_as_csv']

    # Колонки выгрузки: (заголовок, функция извлечения значения из анализа).
    EXPORT_COLUMNS = [
        ('ID', lambda a: a.id),
        ('Дата', lambda a: timezone.localtime(a.created_at).strftime('%d.%m.%Y %H:%M')),
        ('Email пользователя', lambda a: a.user.email),
        ('Имя пользователя', lambda a: a.user.name),
        ('Тип анализа', lambda a: a.get_kind_display()),
        ('Возрастная группа', lambda a: a.get_age_group_display() if a.age_group else ''),
        ('Балл', lambda a: '' if a.score is None else a.score),
        ('Свежий налёт, %', lambda a: '' if a.fresh_plaque_percent is None else a.fresh_plaque_percent),
        ('Зрелый налёт, %', lambda a: '' if a.old_plaque_percent is None else a.old_plaque_percent),
        ('Проценты измерены скриптом', lambda a: _yes_no(a.cv_measured)),
        ('Наблюдения', lambda a: _join_list(a.observations)),
        ('Проблемные зоны', lambda a: _join_list(a.problem_zones)),
        ('Рекомендации', lambda a: _join_list(a.recommendations)),
        ('Заметка пользователя', lambda a: a.note),
        ('Комментарий эксперта', lambda a: a.doctor_comment),
        ('Валидное фото', lambda a: _yes_no(a.is_valid)),
        ('Попытка списана', lambda a: _yes_no(a.attempt_deducted)),
    ]

    def get_actions(self, request):
        """Экшн выгрузки показываем только тем, у кого есть право export_analysis
        (главный админ — всегда; эксперт — если галочка выдана). У остальных
        экспертов действия «Выгрузить в CSV» в списке даже не будет."""
        actions = super().get_actions(request)
        if not request.user.has_perm(EXPORT_PERM):
            actions.pop('export_as_csv', None)
        return actions

    @admin.action(description='Выгрузить выбранные в CSV (Excel)')
    def export_as_csv(self, request, queryset):
        # Страховка поверх get_actions: даже при прямом POST без права — отказ.
        if not request.user.has_perm(EXPORT_PERM):
            self.message_user(request, 'Недостаточно прав для выгрузки данных.',
                              level=messages.ERROR)
            return

        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="analyses.csv"'
        # BOM — чтобы Excel открыл кириллицу без «крякозябр». Разделитель «;» —
        # русский Excel по умолчанию разносит по столбцам именно по нему.
        response.write('﻿')
        writer = csv.writer(response, delimiter=';')
        writer.writerow([title for title, _ in self.EXPORT_COLUMNS])

        qs = queryset.select_related('user').order_by('-created_at')
        for a in qs:
            writer.writerow([extract(a) for _, extract in self.EXPORT_COLUMNS])

        self.message_user(request, f'Выгружено анализов: {qs.count()}.',
                          level=messages.SUCCESS)
        return response

    fieldsets = (
        ('Пользователь', {'fields': ('user', 'kind', 'created_at', 'note')}),
        ('Возрастная группа и согласие', {
            'fields': (
                'age_group', 'legal_rep_consent', 'consent_ip',
                'consent_datetime', 'consent_text_version',
            ),
        }),
        ('Результат ИИ', {
            'fields': (
                'score', 'fresh_plaque_percent', 'old_plaque_percent',
                'problem_zones', 'observations', 'recommendations', 'dynamics_text', 'is_valid',
            ),
            'description': 'У экспресс-оценки нет балла и процентов налёта — без индикатора '
                           'их не измерить. Там заполнено поле «Наблюдения».',
        }),
        ('Комментарий эксперта', {'fields': ('doctor_comment',)}),
        ('Техническое', {
            'fields': ('photos_full', 'photo_url', 'ai_model', 'raw_response', 'attempt_deducted'),
        }),
    )

    def kind_badge(self, obj):
        return obj.get_kind_display()
    kind_badge.short_description = 'Тип'
    kind_badge.admin_order_field = 'kind'

    def score_display(self, obj):
        """У экспресс-оценки балла нет by design — показываем прочерк, а не пустоту,
        чтобы это не читалось как «анализ сломался»."""
        if obj.score is None:
            return '—'
        return obj.score
    score_display.short_description = 'Оценка'
    score_display.admin_order_field = 'score'

    def age_group_badge(self, obj):
        if not obj.age_group:
            return '—'
        return obj.get_age_group_display()
    age_group_badge.short_description = 'Группа'
    # Клик по заголовку колонки сортирует список по возрастной группе.
    age_group_badge.admin_order_field = 'age_group'

    def consent_badge(self, obj):
        if obj.age_group in ('milk', 'mixed', 'permanent_teen'):
            return '✓ согласие' if obj.legal_rep_consent else '✗ нет'
        return '—'
    consent_badge.short_description = 'Согласие зак. пр.'

    def photos_thumbs(self, obj):
        photos = list(obj.photos.all()[:5])
        if not photos and obj.photo_url:
            return format_html(
                '<a href="{0}" target="_blank" rel="noopener">'
                '<img src="{0}" style="height:40px;border:1px solid #ddd;border-radius:3px;margin-right:2px"/></a>',
                obj.photo_url.url,
            )
        if not photos:
            return '—'
        return format_html_join(
            '',
            '<a href="{0}" target="_blank" rel="noopener"><img src="{0}" style="height:40px;border:1px solid #ddd;border-radius:3px;margin-right:2px"/></a>',
            ((p.photo.url,) for p in photos),
        )
    photos_thumbs.short_description = 'Фото'

    def photos_full(self, obj):
        photos = list(obj.photos.all())
        if not photos:
            return '—'
        # Рядом с оригиналом показываем подсветку зон налёта от CV-скрипта,
        # если она есть (скрипт был включён и смог измерить это фото).
        img_tpl = (
            '<a href="{0}" target="_blank" rel="noopener">'
            '<img src="{0}" style="max-width:400px;border:1px solid #ddd;'
            'border-radius:4px;margin-right:8px;vertical-align:top"/></a>'
        )
        parts = []
        for p in photos:
            block = format_html(img_tpl, p.photo.url)
            if p.overlay:
                block += format_html(img_tpl, p.overlay.url)
                block += format_html(
                    '<div style="color:#666;font-size:11px">справа — подсветка налёта '
                    '(розовый: свежий, синий: зрелый)</div>'
                )
            parts.append(format_html('<div style="margin-bottom:8px">{}</div>', block))
        return mark_safe(''.join(parts))
    photos_full.short_description = 'Все фото анализа'
