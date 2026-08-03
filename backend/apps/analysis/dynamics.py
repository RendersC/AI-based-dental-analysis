"""График динамики оценок гигиены. Единый источник данных для ЛК (API) и админки.

Берём валидные анализы пользователя с проставленной оценкой по возрастанию даты
и считаем сводку. Оценка — по 10-балльной шкале (Analysis.score, 0..10).
Невалидные анализы и записи без оценки в график не попадают — иначе ломается
шкала и линия прыгает на пустых точках."""
from __future__ import annotations


def get_score_series(user):
    """Валидные анализы пользователя с оценкой, по возрастанию даты.

    Только анализы с индикатором: экспресс-оценка балла не имеет и в динамику
    не попадает (фильтр по kind избыточен рядом со score__isnull=False, но держим
    его явно — динамика не должна зависеть от того, что где-то проставился балл)."""
    from .models import KIND_INDICATOR

    return list(
        user.analyses
        .filter(kind=KIND_INDICATOR, is_valid=True, score__isnull=False)
        .order_by('created_at')
        .values('id', 'created_at', 'score')
    )


def build_dynamics(user):
    """Точки графика + сводка. Структура:

    {
      'points': [{'id', 'date' (ISO), 'score'}, ...],   # по возрастанию даты
      'summary': {
        'count', 'first', 'last', 'best', 'average', 'change',
        'trend': 'up' | 'down' | 'flat' | 'none',
      },
    }
    """
    rows = get_score_series(user)
    points = [
        {
            'id': r['id'],
            'date': r['created_at'].isoformat(),
            'score': round(r['score'], 1),
        }
        for r in rows
    ]
    scores = [p['score'] for p in points]

    if not scores:
        summary = {
            'count': 0, 'first': None, 'last': None, 'best': None,
            'average': None, 'change': None, 'trend': 'none',
        }
        return {'points': points, 'summary': summary}

    first, last = scores[0], scores[-1]
    change = round(last - first, 1)
    if len(scores) < 2 or change == 0:
        trend = 'flat'
    elif change > 0:
        trend = 'up'
    else:
        trend = 'down'

    summary = {
        'count': len(scores),
        'first': first,
        'last': last,
        'best': max(scores),
        'average': round(sum(scores) / len(scores), 1),
        'change': change,
        'trend': trend,
    }
    return {'points': points, 'summary': summary}
