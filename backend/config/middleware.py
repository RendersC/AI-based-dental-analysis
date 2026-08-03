from django.db import OperationalError, connection


class RealClientIPMiddleware:
    """За nginx-прокси REMOTE_ADDR равен IP nginx, а не клиента. Берём первый IP
    из X-Forwarded-For (он пришёл от nginx, мы ему доверяем) и кладём в REMOTE_ADDR.
    Если заголовка нет — REMOTE_ADDR остаётся как есть."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
        if xff:
            request.META['REMOTE_ADDR'] = xff.split(',')[0].strip()
        return self.get_response(request)


class DatabaseRetryMiddleware:
    """Cross-DC TCP к RU postgres иногда отмирает между запросами и connect_timeout=5
    не успевает поднять свежий — пользователь видит 500. Здесь ловим OperationalError,
    закрываем мёртвую коннекцию и для идемпотентных методов делаем один повтор
    (свежий handshake уже инициирован и обычно успевает за второй попыткой).
    Non-idempotent (POST/PUT/PATCH/DELETE) не повторяем — риск дубля side-effects."""

    SAFE_METHODS = frozenset({'GET', 'HEAD', 'OPTIONS'})

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            return self.get_response(request)
        except OperationalError:
            connection.close()
            if request.method in self.SAFE_METHODS:
                return self.get_response(request)
            raise
