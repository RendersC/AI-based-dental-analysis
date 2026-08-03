"""Тесты регистрации с обязательной датой рождения и валидацией 14+."""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import status
from rest_framework.test import APIClient

from apps.core.models import SystemSettings
from apps.users.serializers import calc_age, MIN_REGISTRATION_AGE

User = get_user_model()


class CalcAgeTests(TestCase):
    """Утилита расчёта возраста по дате рождения."""

    def test_exactly_birthday_today(self):
        today = date.today()
        born = date(today.year - 20, today.month, today.day)
        self.assertEqual(calc_age(born, today=today), 20)

    def test_day_before_birthday(self):
        today = date(2026, 6, 4)
        born = date(2010, 6, 5)
        self.assertEqual(calc_age(born, today=today), 15)

    def test_day_after_birthday(self):
        today = date(2026, 6, 5)
        born = date(2010, 6, 4)
        self.assertEqual(calc_age(born, today=today), 16)

    def test_thirteen_y_364d(self):
        today = date(2026, 6, 4)
        born = date(2012, 6, 5)
        self.assertEqual(calc_age(born, today=today), 13)

    def test_exactly_14_today(self):
        today = date(2026, 6, 4)
        born = date(2012, 6, 4)
        self.assertEqual(calc_age(born, today=today), 14)


class RegisterEndpointTests(TestCase):
    """API регистрации: дата рождения обязательна, возраст 14+ строгий."""

    def setUp(self):
        from django.core.cache import cache
        cache.clear()  # rate-limit считается в Redis-кеше, переживает re-create test DB
        SystemSettings.objects.get_or_create(key='initial_attempts', defaults={'value': '3'})
        self.client = APIClient()
        self.url = reverse('auth-register')
        self.base_payload = {
            'email': 'test@example.com',
            'name': 'Test',
            'password': 'StrongPass1',
            'password2': 'StrongPass1',
            'consent_terms': True,
            'consent_privacy': True,
            'consent_personal_data': True,
            'consent_health_data': True,
            'consent_cross_border': True,
        }

    def _dob_for_age(self, years):
        today = date.today()
        try:
            return today.replace(year=today.year - years)
        except ValueError:
            return today.replace(year=today.year - years, day=28)

    def test_register_18_years_old_succeeds(self):
        payload = {**self.base_payload, 'date_of_birth': self._dob_for_age(18).isoformat()}
        resp = self.client.post(self.url, payload, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        user = User.objects.get(email='test@example.com')
        self.assertEqual(user.date_of_birth, self._dob_for_age(18))
        self.assertEqual(user.attempts_left, 3)

    def test_register_exactly_14_succeeds(self):
        payload = {**self.base_payload, 'date_of_birth': self._dob_for_age(14).isoformat()}
        resp = self.client.post(self.url, payload, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)

    def test_register_13_years_blocked(self):
        payload = {**self.base_payload, 'date_of_birth': self._dob_for_age(13).isoformat()}
        resp = self.client.post(self.url, payload, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('date_of_birth', resp.data)

    def test_register_13y_364d_blocked(self):
        """Граничный случай: за день до 14-летия — блок."""
        tomorrow = date.today() + timedelta(days=1)
        try:
            born = tomorrow.replace(year=tomorrow.year - 14)
        except ValueError:
            born = tomorrow.replace(year=tomorrow.year - 14, day=28)
        payload = {**self.base_payload, 'date_of_birth': born.isoformat()}
        resp = self.client.post(self.url, payload, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('date_of_birth', resp.data)

    def test_register_missing_dob_fails(self):
        payload = dict(self.base_payload)
        resp = self.client.post(self.url, payload, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('date_of_birth', resp.data)

    def test_register_future_dob_fails(self):
        future = (date.today() + timedelta(days=1)).isoformat()
        payload = {**self.base_payload, 'date_of_birth': future}
        resp = self.client.post(self.url, payload, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('date_of_birth', resp.data)

    def test_min_registration_age_constant(self):
        self.assertEqual(MIN_REGISTRATION_AGE, 14)


class PasswordValidationTests(TestCase):
    """Этап 3 «Безопасность»: усиление паролей при регистрации."""

    def setUp(self):
        from django.core.cache import cache
        cache.clear()  # rate-limit считается в кеше — без очистки IP исчерпается за тест
        SystemSettings.objects.get_or_create(key='initial_attempts', defaults={'value': '3'})
        self.client = APIClient()
        self.url = reverse('auth-register')
        self.base = {
            'email': 'p@example.com', 'name': 'P',
            'date_of_birth': date(2000, 1, 1).isoformat(),
            'consent_terms': True, 'consent_privacy': True,
            'consent_personal_data': True, 'consent_health_data': True,
            'consent_cross_border': True,
        }

    def _post(self, password, password2=None):
        payload = {**self.base, 'password': password, 'password2': password2 or password}
        return self.client.post(self.url, payload, format='json')

    def test_short_password_rejected(self):
        resp = self._post('Abc12')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('password', resp.data)

    def test_numeric_only_password_rejected(self):
        resp = self._post('12345678')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('password', resp.data)

    def test_letters_only_password_rejected(self):
        """Должен содержать и буквы, и цифры."""
        resp = self._post('abcdefgh')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('password', resp.data)

    def test_common_password_rejected(self):
        """password1 — из встроенного списка топ-100k слабых."""
        resp = self._post('password1')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('password', resp.data)

    def test_password_similar_to_email_rejected(self):
        """UserAttributeSimilarity: пароль 'pexample1' слишком похож на email 'p@example.com'."""
        payload = {**self.base, 'password': 'pexample1', 'password2': 'pexample1'}
        resp = self.client.post(self.url, payload, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('password', resp.data)

    def test_strong_password_accepted(self):
        resp = self._post('StrongPass1!')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)


class SurveyTests(TestCase):
    """Анкета (Яндекс.Формы): показ раз в 3 анализа, отметка прохождения, сброс версии."""

    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.user = User.objects.create_user(email='s@x.ru', name='S', password='StrongPass1')
        self.client = APIClient()

    def _set(self, key, value):
        SystemSettings.objects.update_or_create(key=key, defaults={'value': value})

    def _make_analyses(self, n):
        from apps.analysis.models import Analysis
        for _ in range(n):
            Analysis.objects.create(user=self.user)

    def test_no_url_no_prompt(self):
        from apps.analysis.views import _survey_prompt
        self._make_analyses(3)
        show, url = _survey_prompt(self.user)
        self.assertFalse(show)
        self.assertEqual(url, '')

    def test_prompt_every_third_analysis(self):
        from apps.analysis.views import _survey_prompt
        self._set('survey_url', 'https://forms.yandex.ru/cloud/abc')
        self._make_analyses(2)
        self.assertFalse(_survey_prompt(self.user)[0])  # 2-й — не показываем
        self._make_analyses(1)
        self.assertTrue(_survey_prompt(self.user)[0])    # 3-й — показываем
        self._make_analyses(2)
        self.assertFalse(_survey_prompt(self.user)[0])  # 5-й — нет
        self._make_analyses(1)
        self.assertTrue(_survey_prompt(self.user)[0])    # 6-й — да

    def test_completed_version_suppresses_prompt(self):
        from apps.analysis.views import _survey_prompt
        self._set('survey_url', 'https://forms.yandex.ru/cloud/abc')
        self._make_analyses(3)
        self.user.survey_completed_version = 1  # текущая версия = 1
        self.user.save(update_fields=['survey_completed_version'])
        self.assertFalse(_survey_prompt(self.user)[0])

    def test_version_bump_reoffers(self):
        from apps.analysis.views import _survey_prompt
        self._set('survey_url', 'https://forms.yandex.ru/cloud/abc')
        self._make_analyses(3)
        self.user.survey_completed_version = 1
        self.user.save(update_fields=['survey_completed_version'])
        self._set('survey_version', '2')  # клиент сбросил — версия выросла
        self.assertTrue(_survey_prompt(self.user)[0])

    def test_survey_complete_marks_current_version(self):
        self._set('survey_version', '3')
        self.client.force_authenticate(self.user)
        resp = self.client.post(reverse('auth-survey-complete'))
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.user.refresh_from_db()
        self.assertEqual(self.user.survey_completed_version, 3)

    def test_public_settings_exposes_survey_url(self):
        self._set('survey_url', 'https://forms.yandex.ru/cloud/xyz')
        resp = self.client.get(reverse('settings'))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['survey_url'], 'https://forms.yandex.ru/cloud/xyz')


class RateLimitTests(TestCase):
    """Этап 3 «Безопасность»: rate-limit на регистрацию."""

    def setUp(self):
        SystemSettings.objects.get_or_create(key='initial_attempts', defaults={'value': '3'})
        from django.core.cache import cache
        cache.clear()
        self.client = APIClient()
        self.url = reverse('auth-register')

    def _payload(self, email):
        return {
            'email': email, 'name': 'P', 'password': 'StrongPass1', 'password2': 'StrongPass1',
            'date_of_birth': date(2000, 1, 1).isoformat(),
            'consent_terms': True, 'consent_privacy': True,
            'consent_personal_data': True, 'consent_health_data': True,
            'consent_cross_border': True,
        }

    def test_register_rate_limit_5_per_hour(self):
        """С одного IP можно сделать 5 регистраций в час, шестая блокируется."""
        for i in range(5):
            resp = self.client.post(self.url, self._payload(f'a{i}@x.ru'), format='json',
                                     HTTP_X_FORWARDED_FOR='198.51.100.1')
            self.assertEqual(resp.status_code, status.HTTP_201_CREATED, f'#{i}: {resp.data}')
        resp = self.client.post(self.url, self._payload('a5@x.ru'), format='json',
                                 HTTP_X_FORWARDED_FOR='198.51.100.1')
        self.assertEqual(resp.status_code, status.HTTP_429_TOO_MANY_REQUESTS, resp.data)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
                   FRONTEND_URL='https://radugaulybok-dent.ru')
class PasswordResetTests(TestCase):
    """Восстановление пароля по email: запрос ссылки + подтверждение с токеном."""

    def setUp(self):
        from django.core.cache import cache
        cache.clear()  # rate-limit в Redis — без очистки IP исчерпается между тестами
        self.user = User.objects.create_user(
            email='reset@x.ru', name='Reset', password='OldPass123',
        )
        self.client = APIClient()
        self.req_url = reverse('auth-password-reset')
        self.confirm_url = reverse('auth-password-reset-confirm')

    def _request(self, email, ip='203.0.113.5'):
        return self.client.post(self.req_url, {'email': email}, format='json',
                                HTTP_X_FORWARDED_FOR=ip)

    def _uid_token(self, user):
        return (urlsafe_base64_encode(force_bytes(user.pk)),
                default_token_generator.make_token(user))

    def test_request_existing_email_sends_one_letter(self):
        resp = self._request('reset@x.ru')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('reset@x.ru', mail.outbox[0].to)
        self.assertIn('/reset-password/', mail.outbox[0].body)

    def test_request_unknown_email_no_letter_same_response(self):
        """Не раскрываем, есть ли такой email: 200 и без письма."""
        resp = self._request('nobody@x.ru')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 0)

    def test_request_email_case_insensitive(self):
        resp = self._request('RESET@X.RU')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)

    def test_confirm_valid_token_changes_password(self):
        uid, token = self._uid_token(self.user)
        resp = self.client.post(self.confirm_url, {
            'uid': uid, 'token': token,
            'new_password': 'BrandNew123', 'new_password2': 'BrandNew123',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('BrandNew123'))

    def test_confirm_bad_token_rejected(self):
        uid, _ = self._uid_token(self.user)
        resp = self.client.post(self.confirm_url, {
            'uid': uid, 'token': 'bogus-token',
            'new_password': 'BrandNew123', 'new_password2': 'BrandNew123',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('token', resp.data)

    def test_confirm_token_single_use(self):
        """После смены пароля старый токен инвалидируется (хеш пароля поменялся)."""
        uid, token = self._uid_token(self.user)
        first = self.client.post(self.confirm_url, {
            'uid': uid, 'token': token,
            'new_password': 'BrandNew123', 'new_password2': 'BrandNew123',
        }, format='json')
        self.assertEqual(first.status_code, status.HTTP_200_OK)
        second = self.client.post(self.confirm_url, {
            'uid': uid, 'token': token,
            'new_password': 'Another123', 'new_password2': 'Another123',
        }, format='json')
        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST)

    def test_confirm_weak_password_rejected(self):
        uid, token = self._uid_token(self.user)
        resp = self.client.post(self.confirm_url, {
            'uid': uid, 'token': token,
            'new_password': '12345678', 'new_password2': '12345678',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('new_password', resp.data)

    def test_confirm_password_mismatch_rejected(self):
        uid, token = self._uid_token(self.user)
        resp = self.client.post(self.confirm_url, {
            'uid': uid, 'token': token,
            'new_password': 'BrandNew123', 'new_password2': 'Different123',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('new_password2', resp.data)

    def test_request_rate_limit_per_email(self):
        """С одного email можно запросить 3 письма в час, четвёртое блокируется.
        Меняем IP, чтобы упереться именно в лимит по email, а не по IP."""
        for i in range(3):
            resp = self._request('reset@x.ru', ip=f'203.0.113.{10 + i}')
            self.assertEqual(resp.status_code, status.HTTP_200_OK, f'#{i}')
        resp = self._request('reset@x.ru', ip='203.0.113.99')
        self.assertEqual(resp.status_code, status.HTTP_429_TOO_MANY_REQUESTS)


class ExpertRoleTests(TestCase):
    """Ограниченный администратор «Эксперт»: группа прав, синхронизация флагов
    по роли и ограничения редактирования в админке."""

    def setUp(self):
        from django.contrib.admin.sites import AdminSite
        from django.test import RequestFactory
        from apps.users.admin import UserAdmin
        from apps.users.permissions_setup import ensure_expert_group, EXPERT_GROUP_NAME

        self.ensure_expert_group = ensure_expert_group
        self.EXPERT_GROUP_NAME = EXPERT_GROUP_NAME
        self.factory = RequestFactory()
        self.admin = UserAdmin(User, AdminSite())

        self.superadmin = User.objects.create_superuser(
            email='boss@raduga.ru', name='Главный', password='x')
        self.patient = User.objects.create_user(
            email='p@raduga.ru', name='Пациент', password='x', attempts_left=1)

    def _request(self, user):
        req = self.factory.get('/admin/users/user/')
        req.user = user
        return req

    class _FakeForm:
        """Имитация админ-формы для save_related. save_m2m() при clears_groups=True
        очищает группы — так ведёт себя реальная форма, когда главный админ не выбрал
        группу «Эксперт» в виджете «Группы». Именно это раньше затирало привязку."""
        def __init__(self, instance, clears_groups=True):
            self.instance = instance
            self._clears = clears_groups

        def save_m2m(self):
            if self._clears:
                self.instance.groups.clear()

    def _admin_save(self, obj, change, clears_groups=True):
        """Полный поток сохранения в админке: save_model → save_related
        (внутри которого super() вызывает form.save_m2m())."""
        req = self._request(self.superadmin)
        self.admin.save_model(req, obj, form=None, change=change)
        form = self._FakeForm(obj, clears_groups=clears_groups)
        self.admin.save_related(req, form, [], change)

    def _make_expert(self):
        expert = User.objects.create_user(
            email='exp@raduga.ru', name='Эксперт', password='x', role='expert')
        self._admin_save(expert, change=True)
        return expert

    # --- группа прав ---

    def test_ensure_expert_group_creates_expected_perms(self):
        group = self.ensure_expert_group()
        codenames = set(group.permissions.values_list('codename', flat=True))
        self.assertEqual(codenames, {
            'view_user', 'change_user',
            'view_analysis', 'change_analysis', 'view_analysisphoto',
        })
        # Никаких прав на удаление/создание или на настройки/инструкцию/правовые доки.
        self.assertNotIn('delete_user', codenames)
        self.assertNotIn('add_user', codenames)
        self.assertNotIn('change_systemsettings', codenames)

    def test_ensure_expert_group_idempotent(self):
        g1 = self.ensure_expert_group()
        g2 = self.ensure_expert_group()
        self.assertEqual(g1.pk, g2.pk)
        self.assertEqual(g2.permissions.count(), 5)

    # --- синхронизация по роли через save_model + save_related ---

    def test_expert_role_sets_staff_and_group(self):
        expert = User(email='new-exp@raduga.ru', name='Нов', role='expert')
        expert.set_password('x')
        expert.save()
        self._admin_save(expert, change=True)
        expert.refresh_from_db()
        self.assertTrue(expert.is_staff)
        self.assertFalse(expert.is_superuser)
        self.assertTrue(expert.groups.filter(name=self.EXPERT_GROUP_NAME).exists())

    def test_group_survives_form_m2m_overwrite(self):
        """Регресс на баг «пустая админка»: даже когда форма сохраняет пустой
        список групп (главный админ не выбирал группу руками), привязка к группе
        «Эксперт» должна остаться, потому что мы вешаем её в save_related ПОСЛЕ
        form.save_m2m()."""
        expert = User(email='reg@raduga.ru', name='Рег', role='expert')
        expert.set_password('x')
        expert.save()
        # clears_groups=True => save_m2m очистит группы, как реальный виджет формы
        self._admin_save(expert, change=True, clears_groups=True)
        expert.refresh_from_db()
        self.assertTrue(
            expert.groups.filter(name=self.EXPERT_GROUP_NAME).exists(),
            'Группа «Эксперт» должна пережить form.save_m2m()')
        # И права через группу реально доступны.
        self.assertTrue(expert.has_perm('users.view_user'))
        self.assertTrue(expert.has_perm('users.change_user'))

    def test_demotion_removes_group(self):
        expert = self._make_expert()
        self.assertTrue(expert.groups.filter(name=self.EXPERT_GROUP_NAME).exists())
        expert.role = 'patient'
        self._admin_save(expert, change=True)
        self.assertFalse(expert.groups.filter(name=self.EXPERT_GROUP_NAME).exists())

    def test_expert_never_superuser(self):
        # Попытка протащить is_superuser вместе с ролью expert должна гаситься.
        expert = User(email='sneaky@raduga.ru', name='Х', role='expert', is_superuser=True)
        expert.set_password('x')
        expert.save()
        self._admin_save(expert, change=True)
        expert.refresh_from_db()
        self.assertFalse(expert.is_superuser)

    # --- определение эксперта ---

    def test_is_limited_expert_detection(self):
        expert = self._make_expert()
        self.assertTrue(self.admin._is_limited_expert(self._request(expert)))
        self.assertFalse(self.admin._is_limited_expert(self._request(self.superadmin)))

    # --- ограничения формы пользователя для эксперта ---

    def test_expert_can_edit_only_attempts(self):
        expert = self._make_expert()
        req = self._request(expert)
        ro = self.admin.get_readonly_fields(req, obj=self.patient)
        self.assertNotIn('attempts_left', ro)  # попытки редактируемы
        for f in ('email', 'name', 'role', 'consent_terms', 'created_at', 'hygiene_dynamics'):
            self.assertIn(f, ro)

    def test_expert_fieldsets_hide_permissions_and_password(self):
        expert = self._make_expert()
        req = self._request(expert)
        fieldsets = self.admin.get_fieldsets(req, obj=self.patient)
        all_fields = [f for _, opts in fieldsets for f in opts['fields']]
        self.assertNotIn('password', all_fields)
        self.assertNotIn('is_superuser', all_fields)
        self.assertNotIn('is_staff', all_fields)
        self.assertNotIn('groups', all_fields)
        self.assertNotIn('user_permissions', all_fields)
        self.assertIn('attempts_left', all_fields)

    def test_superuser_keeps_full_fieldsets(self):
        req = self._request(self.superadmin)
        fieldsets = self.admin.get_fieldsets(req, obj=self.patient)
        all_fields = [f for _, opts in fieldsets for f in opts['fields']]
        self.assertIn('is_superuser', all_fields)
        self.assertIn('groups', all_fields)

    def test_expert_cannot_add_or_delete_users(self):
        expert = self._make_expert()
        req = self._request(expert)
        self.assertFalse(self.admin.has_add_permission(req))
        self.assertFalse(self.admin.has_delete_permission(req, obj=self.patient))
        # А суперпользователь — может.
        sreq = self._request(self.superadmin)
        self.assertTrue(self.admin.has_add_permission(sreq))
        self.assertTrue(self.admin.has_delete_permission(sreq, obj=self.patient))


class ExpertAnalysisAdminTests(TestCase):
    """Эксперт в админке анализов: может оставить комментарий, но не правит результат ИИ."""

    def test_only_doctor_comment_is_editable(self):
        from django.contrib.admin.sites import AdminSite
        from apps.analysis.admin import AnalysisAdmin
        from apps.analysis.models import Analysis

        admin_obj = AnalysisAdmin(Analysis, AdminSite())
        readonly = set(admin_obj.readonly_fields)
        # Комментарий эксперта НЕ readonly — его можно заполнить.
        self.assertNotIn('doctor_comment', readonly)
        # Результаты ИИ и данные пользователя — только для чтения.
        for f in ('user', 'score', 'is_valid', 'raw_response', 'created_at'):
            self.assertIn(f, readonly)

    def test_expert_group_grants_change_analysis_not_delete(self):
        from apps.users.permissions_setup import ensure_expert_group
        group = ensure_expert_group()
        codenames = set(group.permissions.values_list('codename', flat=True))
        self.assertIn('change_analysis', codenames)
        self.assertNotIn('delete_analysis', codenames)
        self.assertNotIn('add_analysis', codenames)


class ExpertExportPermissionTests(TestCase):
    """Галочка «Разрешить выгрузку анализов» на странице пользователя: выдаёт и
    снимает индивидуальное право analysis.export_analysis. Управлять им может
    только главный админ, эксперт — нет."""

    def setUp(self):
        from django.contrib.admin.sites import AdminSite
        from django.test import RequestFactory
        from apps.users.admin import UserAdmin
        from apps.users.permissions_setup import ensure_expert_group

        self.factory = RequestFactory()
        self.admin = UserAdmin(User, AdminSite())
        self.superadmin = User.objects.create_superuser(
            email='boss@raduga.ru', name='Главный', password='x')
        self.expert = User.objects.create_user(
            email='exp@raduga.ru', name='Эксперт', password='x',
            role='expert', is_staff=True)
        self.expert.groups.add(ensure_expert_group())

    def _request(self, user):
        req = self.factory.get('/admin/users/user/')
        req.user = user
        return req

    class _Form:
        def __init__(self, instance, cleaned):
            self.instance = instance
            self.cleaned_data = cleaned

        def save_m2m(self):
            pass

    def _save(self, actor, target, can_export):
        form = self._Form(target, {'can_export_analyses': can_export})
        self.admin.save_related(self._request(actor), form, [], change=True)

    def _has_export(self, user):
        return user.user_permissions.filter(
            content_type__app_label='analysis', codename='export_analysis').exists()

    def test_grant_adds_permission(self):
        self._save(self.superadmin, self.expert, True)
        self.assertTrue(self._has_export(self.expert))
        # has_perm видит право после свежей загрузки (сброс кэша прав).
        self.assertTrue(User.objects.get(pk=self.expert.pk).has_perm('analysis.export_analysis'))

    def test_revoke_removes_permission(self):
        self._save(self.superadmin, self.expert, True)
        self._save(self.superadmin, self.expert, False)
        self.assertFalse(self._has_export(self.expert))

    def test_limited_expert_cannot_revoke_export_perm(self):
        # Право выдано главным админом. Попытка самого эксперта «снять» галочкой
        # игнорируется — управление правом только у главного админа.
        self._save(self.superadmin, self.expert, True)
        self._save(self.expert, self.expert, False)
        self.assertTrue(self._has_export(self.expert))

    def test_form_initial_reflects_existing_grant(self):
        from apps.users.admin import UserAdminForm
        self._save(self.superadmin, self.expert, True)
        form = UserAdminForm(instance=User.objects.get(pk=self.expert.pk))
        self.assertTrue(form.fields['can_export_analyses'].initial)
        plain = User.objects.create_user(email='x@raduga.ru', name='X', password='x')
        self.assertFalse(UserAdminForm(instance=plain).fields['can_export_analyses'].initial)

    def test_export_section_hidden_from_expert_fieldsets(self):
        # В форме, которую видит ограниченный эксперт, раздела выгрузки нет.
        req = self._request(self.expert)
        flat = [f for _, opts in self.admin.get_fieldsets(req, obj=self.superadmin)
                for f in opts['fields']]
        self.assertNotIn('can_export_analyses', flat)
        # А главному админу раздел виден.
        req_admin = self._request(self.superadmin)
        flat_admin = [f for _, opts in self.admin.get_fieldsets(req_admin, obj=self.expert)
                      for f in opts['fields']]
        self.assertIn('can_export_analyses', flat_admin)
