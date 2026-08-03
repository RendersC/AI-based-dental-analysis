"""Пересчёт балла гигиены у уже существующих анализов из сохранённого процента налёта.

Раньше балл выставляла модель «на глаз», и он не коррелировал с процентом
(одна и та же «7» на 5% и на 40% налёта). Фикс сделал балл детерминированной
функцией от процента (apps.analysis.services.ai_router.derive_score). Эта команда
применяет ту же функцию к старым записям, чтобы история и админка показывали
согласованные баллы, а не старые «интуитивные».

Процент налёта НЕ меняется — пересчитывается только score и зависящий от него
dynamics_text (строка сравнения с предыдущим анализом пациента).

  python manage.py recompute_scores --dry-run   # показать что изменится
  python manage.py recompute_scores             # применить
"""
from django.core.management.base import BaseCommand

from apps.analysis.models import Analysis
from apps.analysis.services.ai_router import derive_score


def _dynamics_text(curr_score, prev_score, prev_date):
    diff = round((curr_score or 0) - prev_score, 1)
    ds = prev_date.strftime('%d.%m.%Y')
    if diff > 0:
        return f'Улучшение: +{diff} балла по сравнению с анализом от {ds}'
    if diff < 0:
        return f'Ухудшение: {diff} балла по сравнению с анализом от {ds}'
    return f'Результат не изменился по сравнению с анализом от {ds}'


class Command(BaseCommand):
    help = 'Пересчитывает score (и dynamics_text) у существующих анализов из процента налёта.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Только показать изменения, ничего не сохранять.')

    def handle(self, *args, **opts):
        dry = opts['dry_run']

        changed_score = changed_dyn = 0
        # По каждому пользователю идём от старых к новым, чтобы корректно
        # пересобрать dynamics_text (сравнение с предыдущим валидным анализом).
        # set() вместо .distinct(): у модели задан Meta.ordering=['-created_at'],
        # и values_list(...).distinct() подмешал бы created_at в SELECT, сломав
        # уникальность по user_id (дубли → лишние проходы).
        user_ids = set(Analysis.objects.values_list('user_id', flat=True))

        for uid in user_ids:
            prev_score = None
            prev_date = None
            qs = Analysis.objects.filter(user_id=uid).order_by('created_at')
            for a in qs:
                if not a.is_valid:
                    continue
                new_score = derive_score(a.fresh_plaque_percent, a.old_plaque_percent)
                if new_score is None:
                    continue

                new_dyn = ''
                if prev_score is not None:
                    new_dyn = _dynamics_text(new_score, prev_score, prev_date)

                fields = []
                if a.score != new_score:
                    if dry:
                        self.stdout.write(
                            f'  #{a.id}: score {a.score} -> {new_score} '
                            f'(налёт {(a.fresh_plaque_percent or 0)+(a.old_plaque_percent or 0):.0f}%)'
                        )
                    a.score = new_score
                    fields.append('score')
                    changed_score += 1
                if a.dynamics_text != new_dyn:
                    a.dynamics_text = new_dyn
                    fields.append('dynamics_text')
                    changed_dyn += 1

                if fields and not dry:
                    a.save(update_fields=fields)

                prev_score = new_score
                prev_date = a.created_at

        verb = 'Будет изменено' if dry else 'Изменено'
        self.stdout.write(self.style.SUCCESS(
            f'{verb}: баллов {changed_score}, строк динамики {changed_dyn}.'
        ))
