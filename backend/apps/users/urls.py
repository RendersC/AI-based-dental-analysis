from django.urls import path
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from rest_framework_simplejwt.views import (
    TokenRefreshView, TokenVerifyView, TokenObtainPairView, TokenBlacklistView,
)
from .serializers import CustomTokenObtainPairSerializer
from .views import (
    RegisterView, MeView, DeleteAccountView, SurveyCompleteView,
    PasswordResetRequestView, PasswordResetConfirmView,
)


def _login_email_key(group, request):
    """Ключ для rate-limit по email (защита от перебора пароля для одного email
    с разных IP). email не из POST'а напрямую — нормализуем регистр чтобы
    test@x.ru и Test@x.ru считались одинаково."""
    return (request.data.get('email') or '').lower()


@method_decorator(ratelimit(key='ip', rate='10/5m', method='POST', block=True), name='post')
@method_decorator(ratelimit(key=_login_email_key, rate='10/h', method='POST', block=True), name='post')
class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


urlpatterns = [
    path('register/', RegisterView.as_view(), name='auth-register'),
    path('login/', CustomTokenObtainPairView.as_view(), name='auth-login'),
    path('logout/', TokenBlacklistView.as_view(), name='auth-logout'),
    path('token/refresh/', TokenRefreshView.as_view(), name='auth-token-refresh'),
    path('token/verify/', TokenVerifyView.as_view(), name='auth-token-verify'),
    path('me/', MeView.as_view(), name='auth-me'),
    path('delete/', DeleteAccountView.as_view(), name='auth-delete'),
    path('survey/complete/', SurveyCompleteView.as_view(), name='auth-survey-complete'),
    path('password-reset/', PasswordResetRequestView.as_view(), name='auth-password-reset'),
    path('password-reset/confirm/', PasswordResetConfirmView.as_view(), name='auth-password-reset-confirm'),
]
