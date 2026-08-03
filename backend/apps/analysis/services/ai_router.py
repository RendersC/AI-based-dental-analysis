from typing import List, Tuple
from apps.core.models import SystemSettings
from apps.analysis.models import AGE_GROUP_TO_PROMPT_KEY
from . import gemini, qwen, gigachat


# Дефолтные модели по провайдеру. Если admin задал ai_model в SystemSettings,
# берём оттуда; иначе используем дефолт из этой таблицы.
_DEFAULT_MODEL = {
    'gemini': 'gemini-2.5-flash',
    'qwen': 'qwen/qwen3-vl-235b-a22b-instruct',
    'gigachat': 'GigaChat-2-Max',
}

# Сколько последних валидных анализов пациента подмешивать в промт.
HISTORY_LIMIT = 5

# Пороги для вывода балла гигиены (1-10) из суммарной площади налёта (%).
# Список пар (верхняя_граница_процента, балл) по возрастанию процента: берём первый
# балл, у которого total <= граница. Всё, что выше последней границы, получает 1.
# Сетка задана заказчиком (зелёная/синяя/жёлтая/красная зоны гигиены):
#   0-5%→10, 6-15%→9, 16-24%→8, 25-33%→7, 34-44%→6,
#   45-55%→5, 56-66%→4, 67-77%→3, 78-88%→2, 89-100%→1.
_SCORE_BANDS = [
    (5, 10),
    (15, 9),
    (24, 8),
    (33, 7),
    (44, 6),
    (55, 5),
    (66, 4),
    (77, 3),
    (88, 2),
]


def derive_score(fresh_percent, old_percent):
    """Детерминированно выводит балл гигиены 1-10 из измеренного процента налёта.

    Раньше балл ставила сама модель «на глаз», и он не коррелировал с процентом:
    одна и та же «7» выставлялась и на 5%, и на 40% налёта, а явно грязные фото
    получали 6 вместо 2-3 (жалоба заказчика). Теперь балл однозначно следует за
    суммарной площадью налёта (свежий + старый): одинаковый ввод всегда даёт
    одинаковый балл, и более грязное фото никогда не получит балл выше, чем более
    чистое. Процент налёта по-прежнему оценивает модель — мы лишь убрали её
    «интуитивную» оценку как источник нестабильности.

    Возвращает int 1-10, либо None если оба процента не заданы (невалидное фото)."""
    if fresh_percent is None and old_percent is None:
        return None
    total = (fresh_percent or 0) + (old_percent or 0)
    total = max(0.0, min(100.0, total))
    for threshold, score in _SCORE_BANDS:
        if total <= threshold:
            return score
    return 1


def get_prompt_for_age_group(age_group: str) -> str:
    """Возвращает промпт по возрастной группе из SystemSettings.
    Фолбэк — общий prompt_text если ключа группы нет."""
    key = AGE_GROUP_TO_PROMPT_KEY.get(age_group)
    if key:
        text = SystemSettings.get(key, default=None)
        if text:
            return text
    return SystemSettings.get('prompt_text', default='')


def build_history_context(user, limit: int = HISTORY_LIMIT) -> str:
    """Собирает блок с историей последних N валидных анализов пациента
    для подмешивания в начало промта. Если истории нет — возвращает пустую строку.

    История содержит только проблемные зоны и рекомендации — без оценок и процентов,
    чтобы модель не якорилась на прошлые числа при оценке текущего фото.
    Идентичные фото обрабатываются кэшем по хэшу, поэтому числовые показатели
    в истории избыточны.
    Используется чтобы ИИ не повторял рекомендации, которые уже были даны раньше
    (фича «ИИ-память»)."""
    from apps.analysis.models import Analysis, KIND_INDICATOR

    # Только анализы с индикатором: у экспресс-оценки нет ни зон, ни измерений,
    # подмешивать её в историю нечем и незачем.
    prev = (
        Analysis.objects
        .filter(user=user, kind=KIND_INDICATOR, is_valid=True)
        .exclude(score__isnull=True)
        .order_by('-created_at')[:limit]
    )
    if not prev:
        return ''

    lines = ['ИСТОРИЯ ПРЕДЫДУЩИХ АНАЛИЗОВ ЭТОГО ПАЦИЕНТА (от свежего к старому):\n']
    for i, a in enumerate(prev, 1):
        date = a.created_at.strftime('%d.%m.%Y')
        zones = ', '.join(a.problem_zones) if a.problem_zones else 'не выявлены'
        recs = '; '.join(a.recommendations) if a.recommendations else 'не было'
        lines.append(
            f'{i}. Анализ от {date}. Проблемные зоны: {zones}. Рекомендации: {recs}.'
        )
    lines.append(
        '\nКак использовать историю:\n'
        '- ВАЖНО: оценка, проценты налёта и проблемные зоны определяются ТОЛЬКО тем, '
        'что реально видно на текущем фото. История НЕ влияет на эти поля и не повод '
        'искать новые зоны или менять оценку.\n'
        '- История нужна только для текста рекомендаций: не повторяй прошлые '
        'рекомендации слово в слово — переформулируй или предложи другой подход, '
        'но только если состояние реально изменилось.\n'
        '- Если одна и та же проблемная зона видна на фото 2+ анализа подряд, '
        'явно отметь это в рекомендациях (например «межзубные промежутки нижних '
        'резцов остаются проблемными третий анализ подряд»)\n'
        '- ДИНАМИКУ НЕ ОЦЕНИВАЙ: не пиши в рекомендациях про улучшение, ухудшение, '
        'прогресс или регресс по сравнению с прошлыми анализами. Сравнение оценок '
        'система делает автоматически и показывает пациенту отдельной строкой. '
        'Твои рекомендации — только про текущее состояние и технику ухода.\n'
    )
    return '\n'.join(lines) + '\n\n'


def resolve_ai_target(express: bool = False) -> Tuple[str, str]:
    """Возвращает (провайдер, модель) для режима.

    У экспресс-оценки своя пара настроек — ai_provider_express / ai_model_express.
    Пустое значение означает «как в основном анализе»: так админ может держать на
    экспрессе модель попроще (задача легче), не трогая настроенный анализ с
    индикатором, а на старых инсталляциях, где новых ключей нет, всё работает
    ровно как раньше.
    """
    base_provider = SystemSettings.get('ai_provider', default='gemini') or 'gemini'
    base_model = (
        SystemSettings.get('ai_model', default='')
        or _DEFAULT_MODEL.get(base_provider, _DEFAULT_MODEL['gemini'])
    )
    if not express:
        return base_provider, base_model

    provider = (SystemSettings.get('ai_provider_express', default='') or '').strip()
    model = (SystemSettings.get('ai_model_express', default='') or '').strip()

    if not provider:
        return base_provider, (model or base_model)

    if not model:
        # Сеть выбрана, модель нет: подставлять base_model нельзя — у другой сети
        # это имя не существует (например gemini-2.5-flash при провайдере GigaChat).
        model = (
            base_model if provider == base_provider
            else _DEFAULT_MODEL.get(provider, _DEFAULT_MODEL['gemini'])
        )
    return provider, model


def _dispatch(photos: List[bytes], prompt: str, express: bool = False) -> Tuple[dict, str]:
    """Отправляет фото в активную нейросеть из SystemSettings.
    Новые провайдеры добавляются здесь, без изменения вызывающего кода."""
    if not photos:
        raise ValueError('Список фото пустой')

    provider, model = resolve_ai_target(express=express)

    if provider == 'qwen':
        return qwen.analyze(photos, prompt, model=model)
    if provider == 'gigachat':
        return gigachat.analyze(photos, prompt, model=model)
    return gemini.analyze(photos, prompt, model=model)


def analyze(photos: List[bytes], prompt: str, measured: Tuple[float, float] = None) -> Tuple[dict, str]:
    """Полный анализ по фото с индикатором. Возвращает (parsed_json, raw_response).

    measured — (fresh_percent, old_percent), измеренные CV-скриптом. Если переданы,
    они принудительно заменяют проценты из ответа модели: модель просят вернуть
    эти же числа (см. build_measured_block), но полагаться на её дисциплину нельзя.
    Валидация фото остаётся за моделью в обоих случаях: скрипт умеет считать
    пиксели, но не умеет понять, что на фото не зубы."""
    result, raw = _dispatch(photos, prompt)

    if result.get('is_valid', True):
        if measured is not None:
            result['fresh_plaque_percent'], result['old_plaque_percent'] = measured

        # Балл выводим из процентов налёта, а не из «интуиции» модели — иначе один и
        # тот же балл (обычно 6-7) липнет к разным фото независимо от процента.
        derived = derive_score(
            result.get('fresh_plaque_percent'),
            result.get('old_plaque_percent'),
        )
        if derived is not None:
            result['score'] = derived

    return result, raw


def _clean_text_list(value, limit: int) -> List[str]:
    """Приводит поле ответа модели к списку непустых строк (не длиннее limit).
    Модель может вернуть строку вместо массива или подсунуть null — не доверяем."""
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    out = []
    for item in value:
        if not isinstance(item, str):
            continue
        text = item.strip()
        if text:
            out.append(text)
    return out[:limit]


def analyze_express(photos: List[bytes], prompt: str) -> Tuple[dict, str]:
    """Экспресс-оценка по фото БЕЗ индикатора: только качественные наблюдения.

    Возвращает {'is_valid', 'observations', 'recommendations'} и raw-ответ.

    Балл и проценты здесь не вычисляются и не сохраняются ОСОЗНАННО: без окрашивания
    налёт не измерить, а модель, если её попросить, выдаёт правдоподобные, но выдуманные
    числа (проверено на реальных фото прода — чистые зубы получали «20-40% налёта»).
    Поэтому числовые поля вырезаются, даже если модель прислала их по своей инициативе:
    точные метрики остаются исключительно за анализом с индикатором.
    """
    result, raw = _dispatch(photos, prompt, express=True)

    is_valid = bool(result.get('is_valid', True))
    observations = _clean_text_list(result.get('observations'), limit=4)
    recommendations = _clean_text_list(result.get('recommendations'), limit=3)

    # Модель сказала «фото годное», но не описала ничего — доверять нечему.
    if is_valid and not observations:
        is_valid = False

    if not is_valid:
        observations, recommendations = [], []

    return {
        'is_valid': is_valid,
        'observations': observations,
        'recommendations': recommendations,
    }, raw
