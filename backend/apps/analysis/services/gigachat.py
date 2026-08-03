import io
import json
import logging
from typing import List, Tuple, Union

from django.conf import settings

logger = logging.getLogger(__name__)

# Vision-способные модели GigaChat (распознают изображения). Lite-модели зрение
# не поддерживают, поэтому в список не включены — админ выбирает в SystemSettings.ai_model.
# Актуальные слаги: https://developers.sber.ru/docs/ru/gigachat/models
AVAILABLE_MODELS = [
    'GigaChat-2-Max',
    'GigaChat-2-Pro',
    'GigaChat-2',
    'GigaChat-Max',
    'GigaChat-Pro',
]

# GigaChat не поддерживает seed, а temperature должна быть строго > 0 (0 отвергается
# валидацией API). Берём минимально возможную, чтобы ответ был максимально стабильным.
# Сам балл всё равно выводится детерминированно из % налёта (ai_router.derive_score),
# поэтому небольшой разброс перцепции некритичен.
GENERATION_TEMPERATURE = 0.1

# Жёсткий таймаут одного HTTP-запроса (сек), чтобы worker не висел на сетевых проблемах.
GIGACHAT_HTTP_TIMEOUT = 60

# Тот же контракт, что в gemini.py / qwen.py: на мусорный/пустой ответ отдаём
# is_valid=false, и фронт показывает «Фото не подходит» вместо 500.
_INVALID_RESULT = {
    'is_valid': False,
    'score': None,
    'fresh_plaque_percent': None,
    'old_plaque_percent': None,
    'problem_zones': [],
    'recommendations': [],
}


def _strip_markdown_fence(text: str) -> str:
    """GigaChat иногда оборачивает JSON в ```json ... ``` — снимаем обёртку."""
    raw = text.strip()
    if raw.startswith('```'):
        raw = raw.split('```')[1]
        if raw.startswith('json'):
            raw = raw[4:]
        raw = raw.strip()
    return raw


def _build_client():
    """Создаёт клиент GigaChat из настроек.

    Авторизация — по ключу авторизации (credentials, base64 client_id:secret) и scope
    (GIGACHAT_API_PERS для физлиц / GIGACHAT_API_B2B|CORP для бизнеса). SDK сам
    получает и обновляет access-token (живёт ~30 мин).

    TLS: цепочка GigaChat подписана «Russian Trusted Root CA», которой нет в обычных
    бандлах. Поэтому либо указываем путь к CA-бандлу (GIGACHAT_CA_BUNDLE), либо
    отключаем проверку (GIGACHAT_VERIFY_SSL=false, дефолт). base_url можно
    переопределить (GIGACHAT_BASE_URL) — например чтобы ходить через прокси на РФ,
    если API недоступен с IP сервера.
    """
    from gigachat import GigaChat

    credentials = getattr(settings, 'GIGACHAT_CREDENTIALS', '')
    if not credentials:
        raise RuntimeError('GIGACHAT_CREDENTIALS не настроен в .env')

    kwargs = {
        'credentials': credentials,
        'scope': getattr(settings, 'GIGACHAT_SCOPE', 'GIGACHAT_API_PERS'),
        'timeout': GIGACHAT_HTTP_TIMEOUT,
    }
    base_url = getattr(settings, 'GIGACHAT_BASE_URL', '')
    if base_url:
        kwargs['base_url'] = base_url

    ca_bundle = getattr(settings, 'GIGACHAT_CA_BUNDLE', '')
    if ca_bundle:
        kwargs['ca_bundle_file'] = ca_bundle
        kwargs['verify_ssl_certs'] = True
    else:
        kwargs['verify_ssl_certs'] = getattr(settings, 'GIGACHAT_VERIFY_SSL', False)

    return GigaChat(**kwargs)


def analyze(
    photos: Union[bytes, List[bytes]],
    prompt: str,
    model: str = 'GigaChat-2-Max',
) -> Tuple[dict, str]:
    """Шлёт фото в GigaChat (Сбер), возвращает (parsed_json, raw).

    Фото загружаются через upload_file (получаем id каждого), затем подмешиваются
    в сообщение как attachments. Принимает legacy bytes или list[bytes].
    2 попытки на JSONDecodeError, тот же контракт что у gemini/qwen.
    """
    from gigachat.models import Chat, Messages, MessagesRole

    if isinstance(photos, (bytes, bytearray)):
        photos = [bytes(photos)]
    if not photos:
        raise ValueError('Список фото пустой')

    # Защита от рассинхрона провайдер/модель: если в ai_model осталась модель другой
    # сети (например gemini-2.5-flash), берём дефолтную vision-модель GigaChat.
    if not model or not model.startswith('GigaChat'):
        model = AVAILABLE_MODELS[0]

    text_part = prompt
    if len(photos) > 1:
        text_part += (
            f'\n\nВажно: пациент прислал {len(photos)} фотографий за один анализ. '
            'Сделай вывод по совокупности всех изображений, не возвращай отдельные результаты '
            'по каждой фотографии — только один итоговый JSON по всему набору.'
        )

    for attempt in range(2):
        try:
            with _build_client() as client:
                attachments = []
                for idx, img in enumerate(photos):
                    uploaded = client.upload_file(
                        (f'photo_{idx}.jpg', io.BytesIO(img), 'image/jpeg')
                    )
                    file_id = getattr(uploaded, 'id_', None) or getattr(uploaded, 'id', None)
                    if file_id:
                        attachments.append(file_id)

                chat = Chat(
                    model=model,
                    temperature=GENERATION_TEMPERATURE,
                    messages=[
                        Messages(
                            role=MessagesRole.USER,
                            content=text_part,
                            attachments=attachments,
                        )
                    ],
                )
                response = client.chat(chat)
        except Exception as e:
            # Сетевые/авторизационные/серверные ошибки — это «сервис недоступен»,
            # пробрасываем: views.py вернёт 503 и НЕ спишет попытку.
            logger.error('GigaChat API error (attempt %d): %s', attempt + 1, e)
            raise

        try:
            raw_text = response.choices[0].message.content
        except (AttributeError, IndexError, TypeError) as e:
            logger.error('GigaChat unexpected response shape: %s', e)
            raise RuntimeError('GigaChat: неожиданная структура ответа')

        if not raw_text or not raw_text.strip():
            logger.warning('GigaChat empty response (attempt %d)', attempt + 1)
            return _INVALID_RESULT, '[empty response]'

        raw = _strip_markdown_fence(raw_text)
        try:
            result = json.loads(raw)
            return result, raw_text
        except json.JSONDecodeError as e:
            logger.warning(
                'GigaChat JSON parse error (attempt %d): %s; raw[:200]=%r',
                attempt + 1, e, raw_text[:200],
            )
            if attempt == 1:
                return _INVALID_RESULT, raw_text

    return _INVALID_RESULT, ''
