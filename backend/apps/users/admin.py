from datetime import datetime

from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserChangeForm
from django.contrib.auth.models import Group, Permission
from django.utils.safestring import mark_safe
from django.utils.html import escape

from apps.analysis.dynamics import build_dynamics
from .models import User
from .permissions_setup import EXPERT_GROUP_NAME, ensure_expert_group

# Право на выгрузку анализов в CSV/Excel (определено в apps.analysis.models).
# Живёт на пользователе индивидуально (user_permissions), а не в группе «Эксперт»,
# поэтому по умолчанию у экспертов его нет — выдаётся поштучно галочкой ниже.
EXPORT_PERM_CODENAME = 'export_analysis'
EXPORT_PERM_APP_LABEL = 'analysis'


def _export_permission():
    return Permission.objects.filter(
        content_type__app_label=EXPORT_PERM_APP_LABEL,
        codename=EXPORT_PERM_CODENAME,
    ).first()


class UserAdminForm(UserChangeForm):
    """Форма пользователя с одной доп. галочкой — разрешением на выгрузку анализов.
    Галочка не поле модели: она отражает наличие индивидуального права
    export_analysis и при сохранении выдаёт/снимает его (см. UserAdmin.save_related)."""

    can_export_analyses = forms.BooleanField(
        required=False,
        label='Разрешить выгрузку анализов в CSV/Excel',
        help_text='Даёт этому эксперту кнопку выгрузки в разделе «Анализы». '
                  'У главного администратора выгрузка есть всегда. '
                  'По умолчанию у экспертов выключено.',
    )

    class Meta(UserChangeForm.Meta):
        model = User
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        inst = getattr(self, 'instance', None)
        if inst is not None and inst.pk:
            self.fields['can_export_analyses'].initial = inst.user_permissions.filter(
                content_type__app_label=EXPORT_PERM_APP_LABEL,
                codename=EXPORT_PERM_CODENAME,
            ).exists()

# Геометрия SVG-графика в админке (координаты viewBox).
_CW, _CH = 640, 260
_PAD_L, _PAD_R, _PAD_T, _PAD_B = 40, 16, 16, 34
_PLOT_W = _CW - _PAD_L - _PAD_R
_PLOT_H = _CH - _PAD_T - _PAD_B
_BRAND = '#00548d'


def _render_dynamics_svg(data) -> str:
    """Серверный SVG графика динамики для страницы пользователя в админке.
    Значения — числа и даты (контролируемые), но подписи всё равно экранируем."""
    points = data['points']
    s = data['summary']

    if not points:
        return ('<div style="color:#6E7785;font-size:13px;padding:8px 0;">'
                'Нет завершённых анализов с оценкой — график появится после первого '
                'валидного анализа.</div>')

    n = len(points)

    def px(i):
        if n == 1:
            return _PAD_L + _PLOT_W / 2
        return _PAD_L + _PLOT_W * i / (n - 1)

    def py(score):
        return _PAD_T + _PLOT_H * (1 - score / 10)

    # Сетка + подписи Y
    grid = []
    for t in (0, 2, 4, 6, 8, 10):
        yt = py(t)
        grid.append(
            f'<line x1="{_PAD_L}" y1="{yt:.1f}" x2="{_CW - _PAD_R}" y2="{yt:.1f}" '
            f'stroke="#E2E8F0" stroke-width="1"/>'
            f'<text x="{_PAD_L - 8}" y="{yt + 4:.1f}" text-anchor="end" '
            f'font-size="11" fill="#9aa3b2" font-family="system-ui">{t}</text>'
        )

    # Линия + заливка
    line_cmds = []
    for i, p in enumerate(points):
        cmd = 'M' if i == 0 else 'L'
        line_cmds.append(f'{cmd} {px(i):.1f} {py(p["score"]):.1f}')
    line_path = ' '.join(line_cmds)
    area_path = (f'{line_path} L {px(n - 1):.1f} {_PAD_T + _PLOT_H:.1f} '
                 f'L {px(0):.1f} {_PAD_T + _PLOT_H:.1f} Z')

    # Точки + подписи дат (у первой, последней и при <=8 точках у всех)
    dots = []
    for i, p in enumerate(points):
        cx, cy = px(i), py(p['score'])
        dots.append(
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="3.5" fill="#fff" '
            f'stroke="{_BRAND}" stroke-width="2"/>'
            f'<text x="{cx:.1f}" y="{cy - 8:.1f}" text-anchor="middle" font-size="10" '
            f'fill="{_BRAND}" font-family="system-ui" font-weight="600">{escape(str(p["score"]))}</text>'
        )
        if n <= 8 or i in (0, n - 1):
            try:
                d = datetime.fromisoformat(p['date'])
                label = escape(d.strftime('%d.%m.%y'))
            except (ValueError, TypeError):
                label = ''
            dots.append(
                f'<text x="{cx:.1f}" y="{_CH - 10}" text-anchor="middle" font-size="9" '
                f'fill="#9aa3b2" font-family="system-ui">{label}</text>'
            )

    change = s['change']
    if change is None or s['trend'] == 'none':
        trend_html = ''
    else:
        if s['trend'] == 'flat':
            tc, tlabel = '#6E7785', 'без изменений'
        elif s['trend'] == 'up':
            tc, tlabel = '#1f8a4c', f'+{change} балла'
        else:
            tc, tlabel = '#ba1a1a', f'{change} балла'
        trend_html = (f'<span style="color:{tc};background:{tc}14;font-weight:600;'
                      f'padding:2px 8px;border-radius:6px;font-size:12px;">{escape(tlabel)}</span>')

    def chip(label, value):
        v = '—' if value is None else escape(str(value))
        return (f'<div style="background:#f2f4f6;border:1px solid #E2E8F0;border-radius:8px;'
                f'padding:6px 12px;text-align:center;min-width:64px;">'
                f'<div style="font-size:10px;letter-spacing:.05em;color:#6E7785;'
                f'text-transform:uppercase;">{escape(label)}</div>'
                f'<div style="font-size:18px;font-weight:700;color:{_BRAND};">{v}</div></div>')

    summary_html = (
        f'<div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:12px;">'
        f'{chip("Анализов", s["count"])}{chip("Сейчас", s["last"])}'
        f'{chip("Лучший", s["best"])}{chip("Средний", s["average"])}'
        f'<span style="margin-left:4px;">{trend_html}</span></div>'
    )

    svg = (
        f'<svg viewBox="0 0 {_CW} {_CH}" style="width:100%;max-width:680px;height:auto;" '
        f'role="img" aria-label="График динамики оценок">'
        f'<defs><linearGradient id="dynAreaAdmin" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0%" stop-color="{_BRAND}" stop-opacity="0.20"/>'
        f'<stop offset="100%" stop-color="{_BRAND}" stop-opacity="0"/></linearGradient></defs>'
        f'{"".join(grid)}'
        f'<path d="{area_path}" fill="url(#dynAreaAdmin)"/>'
        f'<path d="{line_path}" fill="none" stroke="{_BRAND}" stroke-width="2.5" '
        f'stroke-linejoin="round" stroke-linecap="round"/>'
        f'{"".join(dots)}</svg>'
    )

    return (f'<div style="padding:4px 0;">{summary_html}{svg}'
            f'<div style="font-size:11px;color:#9aa3b2;margin-top:6px;">'
            f'Оценка по 10-балльной шкале. Учитываются только завершённые (валидные) анализы.</div></div>')


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = UserAdminForm
    list_display = ['email', 'name', 'role', 'attempts_left', 'express_attempts_left',
                    'is_active', 'created_at']
    list_filter = ['role', 'is_active', 'is_staff']
    search_fields = ['email', 'name']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'consent_date',
                       'consent_terms', 'consent_privacy',
                       'consent_personal_data', 'consent_health_data', 'consent_cross_border',
                       'hygiene_dynamics']

    # Два независимых счётчика: попытки полных анализов и попытки экспресс-оценки.
    # Выдаются и обнуляются по отдельности — экспресс не расходует платный баланс.
    ATTEMPTS_SECTION = ('Роль и попытки', {
        'fields': ('role', 'attempts_left', 'express_attempts_left'),
        'description': '«Анализов с индикатором» — основной (платный) баланс. '
                       '«Экспресс-оценок» — отдельный бесплатный счётчик, основной не тратит.',
    })

    # Раздел показываем только главному админу (в expert_fieldsets его нет),
    # поэтому эксперт не может выдать право на выгрузку сам себе или коллеге.
    EXPORT_SECTION = ('Выгрузка данных', {
        'fields': ('can_export_analyses',),
        'description': 'Разрешение на выгрузку списка анализов в CSV/Excel. '
                       'Ставится поштучно конкретному эксперту; у главного '
                       'администратора выгрузка есть всегда.',
    })

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Личные данные', {'fields': ('name',)}),
        ATTEMPTS_SECTION,
        EXPORT_SECTION,
        ('Динамика гигиены', {'fields': ('hygiene_dynamics',)}),
        ('Согласия (152-ФЗ)', {'fields': ('consent_terms', 'consent_privacy',
                                          'consent_personal_data', 'consent_health_data',
                                          'consent_cross_border', 'consent_date')}),
        ('Права', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Даты', {'fields': ('last_login', 'created_at')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'name', 'role', 'attempts_left', 'express_attempts_left',
                       'password1', 'password2'),
        }),
    )

    # Что видит ограниченный эксперт на странице пользователя: без блока «Права»
    # (группы, права, is_superuser/is_staff) и без поля пароля. Редактировать можно
    # только счётчики попыток, всё остальное — только просмотр.
    expert_fieldsets = (
        (None, {'fields': ('email',)}),
        ('Личные данные', {'fields': ('name',)}),
        ATTEMPTS_SECTION,
        ('Динамика гигиены', {'fields': ('hygiene_dynamics',)}),
        ('Согласия (152-ФЗ)', {'fields': ('consent_terms', 'consent_privacy',
                                          'consent_personal_data', 'consent_health_data',
                                          'consent_cross_border', 'consent_date')}),
        ('Даты', {'fields': ('last_login', 'created_at')}),
    )
    # Для эксперта всё в его форме только для чтения, КРОМЕ обоих счётчиков попыток
    # (attempts_left и express_attempts_left) — выдавать попытки это его работа.
    expert_readonly_fields = ['email', 'name', 'role', 'last_login', 'created_at',
                              'consent_terms', 'consent_privacy', 'consent_personal_data',
                              'consent_health_data', 'consent_cross_border', 'consent_date',
                              'hygiene_dynamics']

    @staticmethod
    def _is_limited_expert(request):
        """True для вошедшего пользователя-эксперта (не суперпользователь, в группе «Эксперт»).
        Суперпользователь всегда видит полную админку."""
        u = request.user
        return (not u.is_superuser) and u.groups.filter(name=EXPERT_GROUP_NAME).exists()

    def get_fieldsets(self, request, obj=None):
        if obj is not None and self._is_limited_expert(request):
            return self.expert_fieldsets
        return super().get_fieldsets(request, obj)

    def get_readonly_fields(self, request, obj=None):
        if obj is not None and self._is_limited_expert(request):
            return self.expert_readonly_fields
        return super().get_readonly_fields(request, obj)

    def has_add_permission(self, request):
        # Создавать пользователей может только главный админ, эксперт — нет.
        if self._is_limited_expert(request):
            return False
        return super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        # Удалять пользователей эксперту нельзя (страховка поверх отсутствия права delete_user).
        if self._is_limited_expert(request):
            return False
        return super().has_delete_permission(request, obj)

    def save_model(self, request, obj, form, change):
        """Синхронизируем служебные флаги по выбранной роли.
        Роль «Эксперт» → is_staff=True, НЕ суперпользователь.
        Привязку к группе делаем в save_related (ниже) — иначе её затирает form.save_m2m()."""
        super().save_model(request, obj, form, change)
        if obj.role == 'expert':
            updates = []
            if not obj.is_staff:
                obj.is_staff = True
                updates.append('is_staff')
            if obj.is_superuser:
                obj.is_superuser = False
                updates.append('is_superuser')
            if updates:
                obj.save(update_fields=updates)

    def save_related(self, request, form, formsets, change):
        """Привязку к группе «Эксперт» делаем ИМЕННО здесь, после form.save_m2m().
        Если делать это в save_model, то сохранение M2M-поля «Группы» из формы
        (главный админ его вручную не трогает) затирает нашу привязку, и эксперт
        остаётся без прав → пустая админка. Здесь форма уже сохранила свои M2M,
        поэтому add/remove группы закрепляется окончательно."""
        super().save_related(request, form, formsets, change)
        obj = form.instance
        if obj.role == 'expert':
            obj.groups.add(ensure_expert_group())
        else:
            group = Group.objects.filter(name=EXPERT_GROUP_NAME).first()
            if group is not None:
                obj.groups.remove(group)

        # Разрешение на выгрузку меняем только когда сохраняет главный админ и
        # галочка реально была в форме. Эксперт этим правом управлять не может;
        # при add-потоке и в служебных сохранениях поля нет — тогда не трогаем.
        if not self._is_limited_expert(request):
            cleaned = getattr(form, 'cleaned_data', {})
            if 'can_export_analyses' in cleaned:
                perm = _export_permission()
                if perm is not None:
                    if cleaned['can_export_analyses']:
                        obj.user_permissions.add(perm)
                    else:
                        obj.user_permissions.remove(perm)

    def hygiene_dynamics(self, obj):
        """График динамики оценок пользователя на странице редактирования.
        Данные берём из того же модуля, что и API ЛК, — цифры совпадают."""
        if obj is None or obj.pk is None:
            return '—'
        return mark_safe(_render_dynamics_svg(build_dynamics(obj)))
    hygiene_dynamics.short_description = 'График динамики оценок'
