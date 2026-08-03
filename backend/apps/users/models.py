from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    def create_user(self, email, name, password=None, **extra_fields):
        if not email:
            raise ValueError('Email обязателен')
        email = self.normalize_email(email)
        extra_fields.setdefault('role', 'patient')
        user = self.model(email=email, name=name, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, name, password=None, **extra_fields):
        extra_fields.setdefault('role', 'admin')
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, name, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = [
        ('patient', 'Пациент'),
        ('doctor', 'Врач'),
        ('admin', 'Администратор'),
        # Ограниченный администратор. При выборе этой роли пользователь получает
        # is_staff=True и группу «Эксперт» (см. apps/users/permissions_setup.py).
        ('expert', 'Эксперт (ограниченный администратор)'),
    ]

    email = models.EmailField(unique=True)
    name = models.CharField(max_length=255)
    date_of_birth = models.DateField(null=True, blank=True)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='patient')
    attempts_left = models.PositiveIntegerField(
        default=0,
        verbose_name='Анализов с индикатором',
    )
    # Экспресс-оценка живёт на СВОЁМ счётчике и не трогает баланс полных анализов:
    # это ознакомительный режим (по умолчанию 3 бесплатные попытки), он ведёт
    # пользователя к платному анализу с индикатором, а не расходует его.
    express_attempts_left = models.PositiveIntegerField(
        default=0,
        verbose_name='Экспресс-оценок',
    )
    # Версия анкеты (Яндекс.Формы), которую пользователь уже прошёл. 0 — ещё не проходил.
    # Анкета предлагается, пока это значение меньше текущего survey_version в настройках.
    # Когда клиент меняет вопросы и увеличивает версию — анкета снова предлагается всем.
    survey_completed_version = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    # Согласия (обязательны при регистрации)
    consent_terms = models.BooleanField(default=False)
    consent_privacy = models.BooleanField(default=False)
    consent_personal_data = models.BooleanField(default=False)
    consent_health_data = models.BooleanField(default=False)
    consent_cross_border = models.BooleanField(default=False)
    consent_date = models.DateTimeField(null=True, blank=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['name']

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'

    def __str__(self):
        return f"{self.name} ({self.email})"
