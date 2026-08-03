import json
import logging
from typing import List, Tuple, Union
from google import genai
from google.genai import types
from django.conf import settings

logger = logging.getLogger(__name__)

AVAILABLE_MODELS = [
    'gemini-2.5-flash',
    'gemini-2.5-pro',
    # Модели 3-го поколения. Проверены живым запросом к Vertex — отвечают.
    # Часть из них в статусе preview: Google может менять или отключать их без
    # предупреждения, поэтому рабочей моделью по умолчанию остаётся 2.5-flash,
    # а тройка доступна для сравнения через админку.
    'gemini-3-flash-preview',
    'gemini-3.1-pro-preview',
    'gemini-3.5-flash',
    'gemini-2.0-flash',
    'gemini-2.0-flash-lite',
    'gemini-1.5-flash',
]

# Регион Vertex для моделей 3-го поколения. Они опубликованы ТОЛЬКО в 'global':
# в обычном региональном эндпоинте (у нас us-central1) запрос к ним отдаёт
# 404 NOT_FOUND. Модели 2.x, наоборот, доступны в обоих, поэтому их не трогаем
# и оставляем в текущем регионе.
GLOBAL_ONLY_LOCATION = 'global'


def _needs_global_location(model: str) -> bool:
    return model.startswith('gemini-3')

# Жёсткий таймаут одного HTTP-запроса в Gemini/Vertex (мс).
# Чтобы worker не висел бесконечно при сетевых проблемах и не блокировал админку.
GEMINI_HTTP_TIMEOUT_MS = 45_000

# Фиксированный seed для воспроизводимости на похожих фото. Вместе с temperature=0
# даёт модели «best effort» одинаковый ответ на повторные запросы (см. GenerateContentConfig.seed).
GENERATION_SEED = 20260610

# Сигнальный JSON, который возвращаем при невалидном/пустом ответе AI,
# чтобы не делать лишние retry на ту же картинку без зубов.
_INVALID_RESULT = {
    'is_valid': False,
    'score': None,
    'fresh_plaque_percent': None,
    'old_plaque_percent': None,
    'problem_zones': [],
    'recommendations': [],
}


def _build_client(model: str = ''):
    """Создаёт клиента genai в одном из двух режимов:

    - Vertex AI (USE_VERTEX_AI=true): аутентификация через service account JSON
      по пути GOOGLE_APPLICATION_CREDENTIALS, project и location из настроек.
      Используется для обхода IP-блокировки бесплатного Gemini API.
    - Direct API (по умолчанию): через GEMINI_API_KEY.

    Локация зависит от модели: gemini-3* опубликованы только в 'global' (см.
    GLOBAL_ONLY_LOCATION), остальные идут в регион из настроек.
    """
    http_options = types.HttpOptions(timeout=GEMINI_HTTP_TIMEOUT_MS)
    if getattr(settings, 'USE_VERTEX_AI', False):
        project = getattr(settings, 'GCP_PROJECT_ID', '')
        location = getattr(settings, 'GCP_LOCATION', 'us-central1')
        if not project:
            raise RuntimeError('USE_VERTEX_AI=true, но GCP_PROJECT_ID не задан в .env')
        if _needs_global_location(model):
            location = GLOBAL_ONLY_LOCATION
        logger.info('Gemini client: Vertex AI mode (project=%s, location=%s, model=%s)',
                    project, location, model or '—')
        return genai.Client(vertexai=True, project=project, location=location, http_options=http_options)
    return genai.Client(api_key=settings.GEMINI_API_KEY, http_options=http_options)


def analyze(
    photos: Union[bytes, List[bytes]],
    prompt: str,
    model: str = 'gemini-2.5-flash',
) -> Tuple[dict, str]:
    """Шлёт фото (одно или несколько) в Gemini одним запросом, возвращает (parsed_json, raw).
    Принимает либо bytes (legacy), либо list[bytes]. Retry до 2 раз на ошибке парсинга."""
    if isinstance(photos, (bytes, bytearray)):
        photos = [bytes(photos)]
    if not photos:
        raise ValueError('Список фото пустой')

    multi_hint = ''
    if len(photos) > 1:
        multi_hint = (
            f'\n\nВажно: пациент прислал {len(photos)} фотографий за один анализ. '
            'Сделай вывод по совокупности всех изображений, не возвращай отдельные результаты '
            'по каждой фотографии — только один итоговый JSON по всему набору.'
        )

    full_prompt = prompt + multi_hint

    client = _build_client(model)

    contents = [full_prompt]
    for img in photos:
        contents.append(types.Part.from_bytes(data=img, mime_type='image/jpeg'))

    # Максимум 2 попытки: лишний retry на фото без зубов раньше блокировал
    # gunicorn-worker и валил всю админку по 504.
    for attempt in range(2):
        try:
            response = client.models.generate_content(
                model=model,
                contents=contents,
                config=types.GenerateContentConfig(
                    response_mime_type='application/json',
                    temperature=0,
                    seed=GENERATION_SEED,
                ),
            )
        except Exception as e:
            logger.error('Gemini API error (attempt %d): %s', attempt + 1, e)
            raise

        # Модель отказалась отвечать (safety/recitation/empty) — это не "сервер упал",
        # а сигнал "фото не подошло". Возвращаем is_valid=false без retry.
        finish_reason = None
        try:
            cand = (response.candidates or [None])[0]
            finish_reason = getattr(cand, 'finish_reason', None) if cand else None
        except Exception:
            pass

        try:
            raw_text = (response.text or '').strip()
        except Exception:
            # У некоторых версий SDK .text бросает, если ответ пустой/заблокирован
            raw_text = ''
        if not raw_text:
            logger.warning('Gemini empty response (attempt %d, finish_reason=%s)', attempt + 1, finish_reason)
            return _INVALID_RESULT, f'[empty response, finish_reason={finish_reason}]'

        raw = raw_text
        if raw.startswith('```'):
            raw = raw.split('```')[1]
            if raw.startswith('json'):
                raw = raw[4:]
        try:
            result = json.loads(raw)
            return result, raw_text
        except json.JSONDecodeError as e:
            logger.warning('Gemini JSON parse error (attempt %d): %s; raw[:200]=%r', attempt + 1, e, raw_text[:200])
            if attempt == 1:
                # Не падаем — отдаём is_valid=false, фронт покажет «Фото не подходит».
                return _INVALID_RESULT, raw_text

    return _INVALID_RESULT, ''
