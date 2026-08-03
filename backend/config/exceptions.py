from django_ratelimit.exceptions import Ratelimited
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler


def ratelimit_aware_exception_handler(exc, context):
    if isinstance(exc, Ratelimited):
        return Response(
            {'detail': 'Слишком много попыток. Попробуйте позже.'},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )
    return exception_handler(exc, context)
