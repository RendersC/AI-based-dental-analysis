from datetime import date
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from django.utils.http import urlsafe_base64_decode
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from apps.core.models import SystemSettings

User = get_user_model()

MIN_REGISTRATION_AGE = 14


def _int_setting(key, fallback):
    """Числовая настройка из админки. Значения там — свободный текст, и опечатка
    («три» вместо «3») не должна ронять регистрацию: молча берём запасное значение."""
    try:
        return int(str(SystemSettings.get(key, default=fallback)).strip())
    except (TypeError, ValueError):
        return fallback


def calc_age(birth_date, today=None):
    today = today or date.today()
    years = today.year - birth_date.year
    if (today.month, today.day) < (birth_date.month, birth_date.day):
        years -= 1
    return years


def run_password_strength_checks(password, user, field='password'):
    """Единая проверка надёжности пароля — используется и при регистрации,
    и при сбросе пароля, чтобы правила были идентичны.
    AUTH_PASSWORD_VALIDATORS (MinimumLength, CommonPassword, NumericPassword,
    UserAttributeSimilarity) + наше доп.требование: и буквы, и цифры.
    Бросает serializers.ValidationError с ключом `field`."""
    try:
        validate_password(password, user=user)
    except DjangoValidationError as e:
        raise serializers.ValidationError({field: list(e.messages)})
    if not (any(c.isalpha() for c in password) and any(c.isdigit() for c in password)):
        raise serializers.ValidationError({field: ['Пароль должен содержать и буквы, и цифры']})


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['name'] = user.name
        token['email'] = user.email
        token['role'] = user.role
        token['attempts_left'] = user.attempts_left
        return token


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    password2 = serializers.CharField(write_only=True, label='Подтверждение пароля')
    date_of_birth = serializers.DateField()
    consent_terms = serializers.BooleanField()
    consent_privacy = serializers.BooleanField()
    consent_personal_data = serializers.BooleanField()
    consent_health_data = serializers.BooleanField()
    consent_cross_border = serializers.BooleanField()

    class Meta:
        model = User
        fields = ['email', 'name', 'password', 'password2', 'date_of_birth',
                  'consent_terms', 'consent_privacy',
                  'consent_personal_data', 'consent_health_data', 'consent_cross_border']

    def validate_email(self, value):
        if User.objects.filter(email=value.lower()).exists():
            raise serializers.ValidationError('Пользователь с таким email уже существует')
        return value.lower()

    def validate_date_of_birth(self, value):
        if value > date.today():
            raise serializers.ValidationError('Дата рождения не может быть в будущем')
        age = calc_age(value)
        if age < MIN_REGISTRATION_AGE:
            raise serializers.ValidationError(
                f'Регистрация доступна с {MIN_REGISTRATION_AGE} лет. '
                'Для младших пациентов сервисом пользуется законный представитель.'
            )
        if age > 120:
            raise serializers.ValidationError('Проверьте дату рождения')
        return value

    def validate(self, data):
        if data['password'] != data['password2']:
            raise serializers.ValidationError({'password2': 'Пароли не совпадают'})

        # Полная проверка пароля. similarity сравнивает с user.email/name,
        # поэтому пробрасываем «временного» юзера.
        user_for_check = User(email=data.get('email', ''), name=data.get('name', ''))
        run_password_strength_checks(data['password'], user_for_check)

        required_consents = (
            ('consent_terms', 'Необходимо принять Пользовательское соглашение'),
            ('consent_privacy', 'Необходимо принять Политику конфиденциальности'),
            ('consent_personal_data', 'Необходимо согласие на обработку персональных данных'),
            ('consent_health_data', 'Необходимо согласие на обработку данных о здоровье'),
            ('consent_cross_border', 'Необходимо согласие на трансграничную передачу данных'),
        )
        for field, msg in required_consents:
            if not data.get(field):
                raise serializers.ValidationError({field: msg})
        return data

    def create(self, validated_data):
        validated_data.pop('password2')
        initial_attempts = _int_setting('initial_attempts', 3)
        initial_express = _int_setting('initial_express_attempts', 3)
        return User.objects.create_user(
            **validated_data,
            attempts_left=initial_attempts,
            express_attempts_left=initial_express,
            consent_date=timezone.now(),
        )


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'name', 'role', 'attempts_left', 'express_attempts_left',
                  'created_at', 'date_of_birth',
                  'consent_terms', 'consent_privacy',
                  'consent_personal_data', 'consent_health_data', 'consent_cross_border']
        read_only_fields = ['id', 'email', 'role', 'attempts_left', 'express_attempts_left',
                            'created_at', 'date_of_birth',
                            'consent_terms', 'consent_privacy',
                            'consent_personal_data', 'consent_health_data', 'consent_cross_border']


class PasswordResetRequestSerializer(serializers.Serializer):
    """Запрос ссылки на сброс пароля — принимает только email."""
    email = serializers.EmailField()

    def validate_email(self, value):
        return value.lower()


class PasswordResetConfirmSerializer(serializers.Serializer):
    """Подтверждение сброса: uid+token из ссылки в письме и новый пароль."""
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, min_length=8)
    new_password2 = serializers.CharField(write_only=True)

    # Одинаковый текст и для битого uid, и для протухшего токена — чтобы не
    # подсказывать перебором, какие user_id существуют.
    INVALID_LINK = 'Ссылка недействительна или устарела. Запросите восстановление пароля заново.'

    def validate(self, data):
        try:
            uid = urlsafe_base64_decode(data['uid']).decode()
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            raise serializers.ValidationError({'token': self.INVALID_LINK})

        if not default_token_generator.check_token(user, data['token']):
            raise serializers.ValidationError({'token': self.INVALID_LINK})

        if data['new_password'] != data['new_password2']:
            raise serializers.ValidationError({'new_password2': 'Пароли не совпадают'})

        run_password_strength_checks(data['new_password'], user, field='new_password')
        data['user'] = user
        return data

    def save(self):
        user = self.validated_data['user']
        user.set_password(self.validated_data['new_password'])
        user.save(update_fields=['password'])
        return user
