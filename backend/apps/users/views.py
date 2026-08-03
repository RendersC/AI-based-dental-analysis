import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.decorators import method_decorator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django_ratelimit.decorators import ratelimit
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.models import SystemSettings
from .serializers import (
    RegisterSerializer, UserProfileSerializer,
    PasswordResetRequestSerializer, PasswordResetConfirmSerializer,
)

logger = logging.getLogger(__name__)

User = get_user_model()


def _reset_email_key(group, request):
    """Ключ rate-limit по email — чтобы нельзя было завалить чужой ящик письмами."""
    return (request.data.get('email') or '').lower()


def send_password_reset_email(user):
    """Шлёт письмо со ссылкой на сброс пароля. uid+token — стандартный
    одноразовый механизм Django: токен становится невалидным после смены пароля
    или истечения PASSWORD_RESET_TIMEOUT (по умолчанию 3 дня)."""
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    reset_url = f"{settings.FRONTEND_URL}/reset-password/{uid}/{token}"
    context = {'user': user, 'reset_url': reset_url}
    text_body = render_to_string('emails/password_reset.txt', context)
    html_body = render_to_string('emails/password_reset.html', context)
    msg = EmailMultiAlternatives(
        subject='Восстановление пароля — Радуга Улыбок',
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    msg.attach_alternative(html_body, 'text/html')
    msg.send(fail_silently=False)


@method_decorator(ratelimit(key='ip', rate='5/h', method='POST', block=True), name='create')
class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(UserProfileSerializer(user).data, status=status.HTTP_201_CREATED)


class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class DeleteAccountView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request):
        user = request.user
        user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class SurveyCompleteView(APIView):
    """Пользователь нажал «Пройти» в карточке анкеты — помечаем текущую версию
    анкеты как пройденную, чтобы больше не предлагать (до следующего сброса версии)."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        user.survey_completed_version = SystemSettings.survey_version()
        user.save(update_fields=['survey_completed_version'])
        return Response(status=status.HTTP_204_NO_CONTENT)


# Защита от перебора email'ов (5/час с IP) и от заваливания одного ящика (3/час на email).
@method_decorator(ratelimit(key='ip', rate='5/h', method='POST', block=True), name='post')
@method_decorator(ratelimit(key=_reset_email_key, rate='3/h', method='POST', block=True), name='post')
class PasswordResetRequestView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        user = User.objects.filter(email=email, is_active=True).first()
        if user:
            try:
                send_password_reset_email(user)
            except Exception:
                # Не валим запрос из-за сбоя SMTP и не раскрываем это наружу —
                # просто логируем, ответ для всех одинаковый.
                logger.exception('Не удалось отправить письмо восстановления пароля')
        # Один и тот же ответ, есть такой email или нет — не раскрываем базу пользователей.
        return Response(
            {'detail': 'Если такой email зарегистрирован, мы отправили на него письмо '
                       'со ссылкой для восстановления пароля. Проверьте папку «Спам».'},
            status=status.HTTP_200_OK,
        )


@method_decorator(ratelimit(key='ip', rate='10/h', method='POST', block=True), name='post')
class PasswordResetConfirmView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {'detail': 'Пароль изменён. Теперь войдите с новым паролем.'},
            status=status.HTTP_200_OK,
        )
