"""Группа прав «Эксперт» — ограниченный администратор.

Эксперта создаёт главный админ (суперпользователь), выбирая роль «Эксперт»
на странице пользователя. Такой аккаунт получает is_staff=True, но НЕ
суперпользователь, и входит в группу «Эксперт» с урезанным набором прав.

Что эксперту доступно (см. EXPERT_PERMS):
- смотреть пользователей и их статистику (график динамики на странице юзера);
- смотреть анализы и фото анализов;
- выдавать пользователям попытки (поле attempts_left — единственное редактируемое
  в UserAdmin для эксперта, остальное только для чтения, см. apps/users/admin.py);
- оставлять комментарий эксперта к анализу (doctor_comment — единственное
  редактируемое поле в AnalysisAdmin, всё прочее readonly).

Чего эксперт НЕ может: создавать/удалять пользователей, менять права и роли,
трогать настройки нейросети, промпты, правовые документы и инструкцию —
этих прав в группе нет, поэтому соответствующие разделы ему даже не показываются.

Отдельно: право на выгрузку анализов в CSV/Excel (analysis.export_analysis)
СОЗНАТЕЛЬНО не входит в группу — по умолчанию у экспертов выгрузки нет. Оно
выдаётся поштучно конкретному эксперту галочкой на его странице (индивидуальное
user_permissions, см. apps/users/admin.py), а не через группу.
"""
from django.contrib.auth.models import Group, Permission

EXPERT_GROUP_NAME = 'Эксперт'

# (app_label, codename) прав, которые получает группа «Эксперт».
# change_user выдаётся, чтобы открывалась форма редактирования пользователя,
# но реально редактируемое поле там одно — attempts_left (ограничение в admin.py).
# change_analysis выдаётся ради комментария эксперта (остальные поля readonly).
EXPERT_PERMS = [
    ('users', 'view_user'),
    ('users', 'change_user'),
    ('analysis', 'view_analysis'),
    ('analysis', 'change_analysis'),
    ('analysis', 'view_analysisphoto'),
]


def ensure_expert_group():
    """Идемпотентно создаёт/обновляет группу «Эксперт» с нужным набором прав.

    Вызывается из init_settings (старт контейнера) и из UserAdmin.save_model
    (при назначении роли «Эксперт»), чтобы группа гарантированно существовала.
    """
    group, _ = Group.objects.get_or_create(name=EXPERT_GROUP_NAME)
    perms = []
    for app_label, codename in EXPERT_PERMS:
        perm = Permission.objects.filter(
            content_type__app_label=app_label, codename=codename,
        ).first()
        if perm is not None:
            perms.append(perm)
    group.permissions.set(perms)
    return group
