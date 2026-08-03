import json
import logging
import base64
from typing import List, Tuple, Union
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

# Slug'и можно посмотреть актуальные через GET https://openrouter.ai/api/v1/models
# (с фильтром ?output_modalities=text и поиском по qwen-vl).
# Эти три — текущие vision-варианты Qwen на OpenRouter; админ выбирает в SystemSettings.ai_model.
AVAILABLE_MODELS = [
    'qwen/qwen3-vl-235b-a22b-instruct',
    'qwen/qwen3-vl-30b-a3b-instruct',
    'qwen/qwen2.5-vl-72b-instruct',
]

_OPENROUTER_URL = 'https://openrouter.ai/api/v1/chat/completions'

# Фиксированный seed для воспроизводимости на похожих фото. OpenRouter форсит
# детерминированный сэмплинг при одинаковом seed (определённость не гарантируется
# для всех моделей, но снижает разброс).
GENERATION_SEED = 20260610

# Если ИИ вернул мусор, отдаём is_valid=false и фронт показывает «Фото не подходит»
# вместо 500. Тот же контракт что в gemini.py.
_INVALID_RESULT = {
    'is_valid': False,
    'score': None,
    'fresh_plaque_percent': None,
    'old_plaque_percent': None,
    'problem_zones': [],
    'recommendations': [],
}


def _strip_markdown_fence(text: str) -> str:
    """Qwen иногда оборачивает JSON в ```json ... ``` — снимаем обёртку."""
    raw = text.strip()
    if raw.startswith('```'):
        raw = raw.split('```')[1]
        if raw.startswith('json'):
            raw = raw[4:]
        raw = raw.strip()
    return raw


def analyze(
    photos: Union[bytes, List[bytes]],
    prompt: str,
    model: str = 'qwen/qwen3-vl-235b-a22b-instruct',
) -> Tuple[dict, str]:
    """Шлёт фото в Qwen-VL через OpenRouter (OpenAI-совместимый endpoint).

    Принимает legacy bytes или list[bytes]. 2 попытки на JSONDecodeError.
    """
    if isinstance(photos, (bytes, bytearray)):
        photos = [bytes(photos)]
    if not photos:
        raise ValueError('Список фото пустой')

    api_key = getattr(settings, 'OPENROUTER_API_KEY', '')
    if not api_key:
        raise RuntimeError('OPENROUTER_API_KEY не настроен в .env')

    text_part = prompt
    if len(photos) > 1:
        text_part += (
            f'\n\nВажно: пациент прислал {len(photos)} фотографий за один анализ. '
            'Сделай вывод по совокупности всех изображений, не возвращай отдельные результаты '
            'по каждой фотографии — только один итоговый JSON по всему набору.'
        )

    # OpenRouter рекомендует текст ДО картинок для оптимального парсинга
    # (см. https://openrouter.ai/docs/guides/overview/multimodal/image-understanding).
    content = [{'type': 'text', 'text': text_part}]
    for img in photos:
        image_b64 = base64.b64encode(img).decode('utf-8')
        content.append({
            'type': 'image_url',
            'image_url': {'url': f'data:image/jpeg;base64,{image_b64}'},
        })

    payload = {
        'model': model,
        'messages': [{'role': 'user', 'content': content}],
        'temperature': 0,
        'seed': GENERATION_SEED,
        'max_tokens': 2000,
        # response_format поддерживается OpenRouter и форсит валидный JSON
        # у моделей которые это умеют (Qwen3-VL умеет).
        'response_format': {'type': 'json_object'},
    }

    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }
    # Опциональные атрибуционные заголовки — OpenRouter использует их для статистики
    # сайтов, не обязательны, но если выставлены — приложение попадёт в публичный рейтинг.
    referer = getattr(settings, 'OPENROUTER_APP_URL', '')
    title = getattr(settings, 'OPENROUTER_APP_TITLE', '')
    if referer:
        headers['HTTP-Referer'] = referer
    if title:
        headers['X-Title'] = title

    for attempt in range(2):
        try:
            resp = requests.post(_OPENROUTER_URL, json=payload, headers=headers, timeout=60)
            resp.raise_for_status()
        except requests.HTTPError as e:
            logger.error(
                'OpenRouter HTTP error (attempt %d): %s body=%r',
                attempt + 1, e, getattr(e.response, 'text', '')[:500],
            )
            raise
        except requests.RequestException as e:
            logger.error('OpenRouter network error (attempt %d): %s', attempt + 1, e)
            raise

        try:
            data = resp.json()
            raw_text = data['choices'][0]['message']['content']
        except (KeyError, IndexError, ValueError) as e:
            logger.error('OpenRouter unexpected response shape: %s body=%r', e, resp.text[:500])
            raise RuntimeError('OpenRouter: неожиданная структура ответа')

        if not raw_text or not raw_text.strip():
            logger.warning('OpenRouter empty response (attempt %d)', attempt + 1)
            return _INVALID_RESULT, '[empty response]'

        raw = _strip_markdown_fence(raw_text)
        try:
            result = json.loads(raw)
            return result, raw_text
        except json.JSONDecodeError as e:
            logger.warning(
                'OpenRouter JSON parse error (attempt %d): %s; raw[:200]=%r',
                attempt + 1, e, raw_text[:200],
            )
            if attempt == 1:
                return _INVALID_RESULT, raw_text

    return _INVALID_RESULT, ''
