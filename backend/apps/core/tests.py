"""Тесты публичных настроек (ID Яндекс.Метрики), правового слота cookie-policy
и init_settings. Метрика поднимается на фронте только после согласия на cookie,
а её ID отдаётся публично — эти тесты фиксируют контракт эндпоинта."""
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.core.models import SystemSettings, LegalDocument, Instruction, OfficialDocument

User = get_user_model()


class PublicSettingsMetrikaTests(TestCase):
    """GET /api/settings/ без авторизации — отдаёт initial_attempts + yandex_metrika_id."""

    def setUp(self):
        self.client = APIClient()
        self.url = reverse('settings')

    def test_metrika_id_empty_by_default(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('yandex_metrika_id', resp.data)
        self.assertEqual(resp.data['yandex_metrika_id'], '')

    def test_returns_configured_metrika_id(self):
        SystemSettings.objects.create(key='yandex_metrika_id', value='99887766')
        resp = self.client.get(self.url)
        self.assertEqual(resp.data['yandex_metrika_id'], '99887766')

    def test_public_does_not_leak_admin_only_settings(self):
        SystemSettings.objects.create(key='prompt_text', value='секретный промт')
        resp = self.client.get(self.url)
        self.assertNotIn('prompt_text', resp.data)


class AdminSetMetrikaTests(TestCase):
    """Админ может задать ID счётчика через PATCH (на случай админ-панели поверх API)."""

    def setUp(self):
        self.client = APIClient()
        self.url = reverse('settings')
        self.admin = User.objects.create_user(
            email='admin@t.ru', name='Admin', password='x', role='admin',
        )

    def test_admin_can_patch_metrika_id(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.patch(self.url, {'yandex_metrika_id': '12345678'}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(SystemSettings.get('yandex_metrika_id'), '12345678')

    def test_patient_cannot_patch(self):
        patient = User.objects.create_user(email='p@t.ru', name='P', password='x')
        self.client.force_authenticate(patient)
        resp = self.client.patch(self.url, {'yandex_metrika_id': '666'}, format='json')
        self.assertEqual(resp.status_code, 403)


class CookiePolicyDocTests(TestCase):
    """Политика cookie — 7-й правовой слот, отдаётся через /docs/cookie-policy.html."""

    def test_cookie_policy_is_valid_slug(self):
        slugs = {s for s, _ in LegalDocument.SLUG_CHOICES}
        self.assertIn('cookie-policy', slugs)

    def test_cookie_policy_page_renders_placeholder(self):
        resp = self.client.get('/docs/cookie-policy.html')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('text/html', resp['Content-Type'])


class InstructionVersionedUrlTests(TestCase):
    """Имя файла инструкции фиксированное, поэтому URL без версии не меняется при
    замене PDF — браузер показывает старый из кеша. Эндпоинт должен возвращать
    ссылку с ?v=<updated_at>, чтобы при каждой загрузке нового файла она менялась."""

    def setUp(self):
        self.client = APIClient()
        self.url = reverse('instruction')
        self.user = User.objects.create_user(email='u@t.ru', name='U', password='x')

    def test_no_instruction_returns_null_url(self):
        self.client.force_authenticate(self.user)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.data['url'])

    def test_url_has_version_query(self):
        self.client.force_authenticate(self.user)
        Instruction.objects.create(
            pdf=SimpleUploadedFile('x.pdf', b'%PDF-1.4 first', content_type='application/pdf'),
        )
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('?v=', resp.data['url'])

    def test_version_reflects_updated_at(self):
        """Метка ?v= должна равняться updated_at — при замене PDF время меняется,
        значит и ссылка станет новой, и браузер сбросит кеш. .update() минует
        auto_now, чтобы зафиксировать точное время без зависимости от часов теста."""
        self.client.force_authenticate(self.user)
        Instruction.objects.create(
            pdf=SimpleUploadedFile('x.pdf', b'%PDF-1.4 first', content_type='application/pdf'),
        )
        from datetime import datetime, timezone as dt_timezone
        fixed = datetime(2026, 1, 2, 3, 4, 5, tzinfo=dt_timezone.utc)
        Instruction.objects.filter(pk=1).update(updated_at=fixed)
        url = self.client.get(self.url).data['url']
        self.assertIn(f"?v={int(fixed.timestamp())}", url)


class OfficialDocumentsApiTests(TestCase):
    """GET /api/settings/official-documents/ — публичный список сканов для блока
    «Официальный статус проекта» на лендинге. Лендинг открыт неавторизованным,
    поэтому эндпоинт обязан отвечать без токена. Скрытые галочкой документы
    отдаваться не должны, порядок — от старых к новым (ручной сортировки нет)."""

    def setUp(self):
        self.client = APIClient()
        self.url = reverse('official-documents')

    def _make(self, caption, is_visible=True):
        return OfficialDocument.objects.create(
            image=SimpleUploadedFile(f'{caption}.jpg', b'fake-jpeg', content_type='image/jpeg'),
            caption=caption,
            is_visible=is_visible,
        )

    def tearDown(self):
        # Тесты пишут реальные файлы в MEDIA_ROOT — убираем за собой.
        for doc in OfficialDocument.objects.all():
            doc.image.delete(save=False)

    def test_empty_by_default(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['results'], [])

    def test_public_access_without_auth(self):
        self._make('Свидетельство Роспатента')
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['results']), 1)

    def test_returns_caption_and_image_url(self):
        self._make('Свидетельство Роспатента')
        item = self.client.get(self.url).data['results'][0]
        self.assertEqual(item['caption'], 'Свидетельство Роспатента')
        self.assertIn('official-docs/', item['image_url'])
        self.assertTrue(item['image_url'].startswith('http'))

    def test_hidden_document_not_returned(self):
        self._make('Видимый')
        self._make('Скрытый', is_visible=False)
        captions = [d['caption'] for d in self.client.get(self.url).data['results']]
        self.assertEqual(captions, ['Видимый'])

    def test_file_removed_from_disk_on_delete(self):
        """Удалённый в админке скан не должен оставаться на диске: /media/ отдаётся
        nginx'ом напрямую, иначе документ открывался бы по прямой ссылке и после
        удаления."""
        from django.core.files.storage import default_storage
        doc = self._make('Удаляемый')
        name = doc.image.name
        self.assertTrue(default_storage.exists(name))
        doc.delete()
        self.assertFalse(default_storage.exists(name))

    def test_order_is_oldest_first(self):
        """Ручной сортировки в админке нет — порядок должен быть предсказуемым,
        новый документ встаёт в конец, уже опубликованные не перемешиваются."""
        self._make('Первый')
        self._make('Второй')
        self._make('Третий')
        captions = [d['caption'] for d in self.client.get(self.url).data['results']]
        self.assertEqual(captions, ['Первый', 'Второй', 'Третий'])


class InitSettingsCreatesNewSlotsTests(TestCase):
    """init_settings заводит настройку Метрики и слот cookie-policy идемпотентно."""

    def test_creates_metrika_setting_and_cookie_slot(self):
        call_command('init_settings')
        self.assertTrue(SystemSettings.objects.filter(key='yandex_metrika_id').exists())
        self.assertTrue(LegalDocument.objects.filter(slug='cookie-policy').exists())

    def test_idempotent(self):
        call_command('init_settings')
        call_command('init_settings')
        self.assertEqual(
            LegalDocument.objects.filter(slug='cookie-policy').count(), 1,
        )
