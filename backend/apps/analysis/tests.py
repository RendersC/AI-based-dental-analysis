"""Тесты Доп ТЗ №1 ред. 2: возрастные группы, согласие, мульти-фото, выбор промпта."""
import json
from io import BytesIO
from unittest.mock import patch, MagicMock

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from PIL import Image
from rest_framework import status
from rest_framework.test import APIClient

from apps.analysis.services import qwen

from apps.analysis.models import (
    AGE_GROUP_TO_PROMPT_KEY,
    Analysis,
    AnalysisPhoto,
    CONSENT_TEXT_VERSION,
)
from apps.analysis.serializers import AnalysisCreateSerializer, MAX_PHOTOS, MAX_NOTE_LENGTH, UNDERAGE_GROUPS
from apps.analysis.services.ai_router import get_prompt_for_age_group
from apps.core.models import SystemSettings

User = get_user_model()

FAKE_AI_RESULT = {
    'is_valid': True,
    'score': 7,
    # 15+15=30% налёта → derive_score даёт 7 (сетка заказчика 25-33%→7), совпадает
    # со score модели выше: фейк внутренне согласован с выводом балла из процента.
    'fresh_plaque_percent': 15,
    'old_plaque_percent': 15,
    'problem_zones': ['зона 1'],
    'recommendations': ['rec 1', 'rec 2', 'rec 3'],
}
FAKE_AI_RAW = '{"is_valid": true, "score": 7}'


def make_jpeg(size=(64, 64)):
    """Сгенерировать валидный мини-JPEG в памяти."""
    buf = BytesIO()
    Image.new('RGB', size, color=(200, 100, 100)).save(buf, format='JPEG')
    buf.seek(0)
    return buf.getvalue()


def upload(name='p.jpg'):
    return SimpleUploadedFile(name, make_jpeg(), content_type='image/jpeg')


class AnalysisCreateSerializerValidationTests(TestCase):
    """Проверка сериализатора: для <18 групп обязательна галочка согласия."""

    def test_milk_without_consent_invalid(self):
        s = AnalysisCreateSerializer(data={'age_group': 'milk', 'legal_rep_consent': False})
        self.assertFalse(s.is_valid())
        self.assertIn('legal_rep_consent', s.errors)

    def test_mixed_without_consent_invalid(self):
        s = AnalysisCreateSerializer(data={'age_group': 'mixed'})
        self.assertFalse(s.is_valid())
        self.assertIn('legal_rep_consent', s.errors)

    def test_permanent_teen_without_consent_invalid(self):
        s = AnalysisCreateSerializer(data={'age_group': 'permanent_teen'})
        self.assertFalse(s.is_valid())
        self.assertIn('legal_rep_consent', s.errors)

    def test_milk_with_consent_valid(self):
        s = AnalysisCreateSerializer(data={'age_group': 'milk', 'legal_rep_consent': True})
        self.assertTrue(s.is_valid(), s.errors)

    def test_permanent_adult_without_consent_valid(self):
        """Для группы 18+ согласие не требуется."""
        s = AnalysisCreateSerializer(data={'age_group': 'permanent_adult'})
        self.assertTrue(s.is_valid(), s.errors)

    def test_unknown_group_invalid(self):
        s = AnalysisCreateSerializer(data={'age_group': 'invented'})
        self.assertFalse(s.is_valid())
        self.assertIn('age_group', s.errors)

    def test_underage_set_includes_three_groups(self):
        self.assertEqual(UNDERAGE_GROUPS, {'milk', 'mixed', 'permanent_teen'})


class PromptRoutingTests(TestCase):
    """get_prompt_for_age_group: правильный промпт по группе."""

    def setUp(self):
        SystemSettings.objects.create(key='prompt_text', value='FALLBACK')
        SystemSettings.objects.create(key='prompt_milk', value='MILK_PROMPT')
        SystemSettings.objects.create(key='prompt_mixed', value='MIXED_PROMPT')
        SystemSettings.objects.create(key='prompt_permanent', value='PERMANENT_PROMPT')

    def test_milk_uses_milk_prompt(self):
        self.assertEqual(get_prompt_for_age_group('milk'), 'MILK_PROMPT')

    def test_mixed_uses_mixed_prompt(self):
        self.assertEqual(get_prompt_for_age_group('mixed'), 'MIXED_PROMPT')

    def test_permanent_teen_uses_permanent_prompt(self):
        self.assertEqual(get_prompt_for_age_group('permanent_teen'), 'PERMANENT_PROMPT')

    def test_permanent_adult_uses_permanent_prompt(self):
        self.assertEqual(get_prompt_for_age_group('permanent_adult'), 'PERMANENT_PROMPT')

    def test_unknown_group_falls_back(self):
        self.assertEqual(get_prompt_for_age_group('xyz'), 'FALLBACK')

    def test_missing_group_prompt_falls_back(self):
        """Если ключа группы нет в SystemSettings — используется prompt_text."""
        SystemSettings.objects.filter(key='prompt_milk').delete()
        self.assertEqual(get_prompt_for_age_group('milk'), 'FALLBACK')

    def test_mapping_covers_all_groups(self):
        self.assertEqual(set(AGE_GROUP_TO_PROMPT_KEY.keys()),
                         {'milk', 'mixed', 'permanent_teen', 'permanent_adult'})


class AnalysisCreateApiTests(TestCase):
    """E2E через APIClient: создание анализа с разными группами и количеством фото."""

    def setUp(self):
        SystemSettings.objects.create(key='prompt_text', value='FALLBACK')
        SystemSettings.objects.create(key='prompt_milk', value='MILK')
        SystemSettings.objects.create(key='prompt_mixed', value='MIXED')
        SystemSettings.objects.create(key='prompt_permanent', value='PERMANENT')
        SystemSettings.objects.create(key='ai_provider', value='gemini')
        SystemSettings.objects.create(key='ai_model', value='gemini-2.5-flash')

        self.user = User.objects.create_user(
            email='patient@example.com', name='P', password='x', attempts_left=5,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.url = reverse('analysis-create')

    def _post(self, **kwargs):
        return self.client.post(self.url, kwargs, format='multipart')

    @patch('apps.analysis.views.ai_analyze', return_value=(FAKE_AI_RESULT, FAKE_AI_RAW))
    def test_adult_single_photo_succeeds(self, _):
        resp = self._post(age_group='permanent_adult', photos=upload())
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        a = Analysis.objects.get()
        self.assertEqual(a.age_group, 'permanent_adult')
        self.assertFalse(a.legal_rep_consent)
        self.assertEqual(a.consent_ip, '')
        self.assertIsNone(a.consent_datetime)
        self.assertEqual(a.photos.count(), 1)
        self.assertEqual(a.score, 7)
        self.assertTrue(a.attempt_deducted)

    @patch('apps.analysis.views.ai_analyze', return_value=(FAKE_AI_RESULT, FAKE_AI_RAW))
    def test_milk_with_consent_logs_ip_and_datetime(self, _):
        resp = self._post(
            age_group='milk',
            legal_rep_consent='true',
            photos=upload(),
            HTTP_X_FORWARDED_FOR='203.0.113.42',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        a = Analysis.objects.get()
        self.assertEqual(a.age_group, 'milk')
        self.assertTrue(a.legal_rep_consent)
        self.assertIsNotNone(a.consent_datetime)
        self.assertEqual(a.consent_text_version, CONSENT_TEXT_VERSION)

    @patch('apps.analysis.views.ai_analyze', return_value=(FAKE_AI_RESULT, FAKE_AI_RAW))
    def test_underage_without_consent_blocked(self, _):
        resp = self._post(age_group='mixed', photos=upload())
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Analysis.objects.count(), 0)

    @patch('apps.analysis.views.ai_analyze', return_value=(FAKE_AI_RESULT, FAKE_AI_RAW))
    def test_five_photos_succeeds(self, _):
        files = [upload(f'p{i}.jpg') for i in range(5)]
        resp = self.client.post(
            self.url,
            {'age_group': 'permanent_adult', 'photos': files},
            format='multipart',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        a = Analysis.objects.get()
        self.assertEqual(a.photos.count(), 5)
        # ordering сохранён
        orders = sorted(p.order for p in a.photos.all())
        self.assertEqual(orders, [0, 1, 2, 3, 4])

    @patch('apps.analysis.views.ai_analyze', return_value=(FAKE_AI_RESULT, FAKE_AI_RAW))
    def test_six_photos_rejected(self, _):
        files = [upload(f'p{i}.jpg') for i in range(6)]
        resp = self.client.post(
            self.url,
            {'age_group': 'permanent_adult', 'photos': files},
            format='multipart',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Analysis.objects.count(), 0)

    @patch('apps.analysis.views.ai_analyze', return_value=(FAKE_AI_RESULT, FAKE_AI_RAW))
    def test_zero_photos_rejected(self, _):
        resp = self._post(age_group='permanent_adult')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('apps.analysis.views.ai_analyze', return_value=(FAKE_AI_RESULT, FAKE_AI_RAW))
    def test_correct_prompt_passed_to_ai(self, mock_ai):
        self._post(age_group='milk', legal_rep_consent='true', photos=upload())
        args, kwargs = mock_ai.call_args
        photos_arg, prompt_arg = args
        self.assertEqual(prompt_arg, 'MILK')
        self.assertEqual(len(photos_arg), 1)

    @patch('apps.analysis.views.ai_analyze', return_value=(FAKE_AI_RESULT, FAKE_AI_RAW))
    def test_no_attempts_blocks_analysis(self, _):
        self.user.attempts_left = 0
        self.user.save()
        resp = self._post(age_group='permanent_adult', photos=upload())
        self.assertEqual(resp.status_code, status.HTTP_402_PAYMENT_REQUIRED)
        self.assertEqual(Analysis.objects.count(), 0)

    @patch('apps.analysis.views.ai_analyze', side_effect=RuntimeError('ai down'))
    def test_ai_error_does_not_deduct_attempt(self, _):
        before = self.user.attempts_left
        resp = self._post(age_group='permanent_adult', photos=upload())
        self.assertEqual(resp.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.user.refresh_from_db()
        self.assertEqual(self.user.attempts_left, before)
        self.assertEqual(Analysis.objects.count(), 0)

    @patch('apps.analysis.views.ai_analyze', return_value=(
        {
            'is_valid': False,
            'score': None,
            'fresh_plaque_percent': None,
            'old_plaque_percent': None,
            'problem_zones': [],
            'recommendations': [],
        },
        '{"is_valid": false}',
    ))
    def test_photo_without_teeth_returns_invalid_not_500(self, _):
        """Фото без зубов: AI возвращает is_valid=false → 201 с is_valid=false,
        попытка списана, сервер не падает."""
        before = self.user.attempts_left
        resp = self._post(age_group='permanent_adult', photos=upload())
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertFalse(resp.data['is_valid'])
        self.user.refresh_from_db()
        self.assertEqual(self.user.attempts_left, before - 1)

    def test_unauthenticated_blocked(self):
        self.client.force_authenticate(None)
        resp = self._post(age_group='permanent_adult', photos=upload())
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch('apps.analysis.views.ai_analyze', return_value=(FAKE_AI_RESULT, FAKE_AI_RAW))
    def test_note_saved_and_returned(self, _):
        resp = self._post(age_group='permanent_adult', photos=upload(), note='Сменили щётку на электрическую')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        a = Analysis.objects.get()
        self.assertEqual(a.note, 'Сменили щётку на электрическую')
        self.assertEqual(resp.data['note'], 'Сменили щётку на электрическую')

    @patch('apps.analysis.views.ai_analyze', return_value=(FAKE_AI_RESULT, FAKE_AI_RAW))
    def test_note_optional_defaults_to_empty(self, _):
        resp = self._post(age_group='permanent_adult', photos=upload())
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        a = Analysis.objects.get()
        self.assertEqual(a.note, '')

    @patch('apps.analysis.views.ai_analyze', return_value=(FAKE_AI_RESULT, FAKE_AI_RAW))
    def test_note_whitespace_trimmed(self, _):
        resp = self._post(age_group='permanent_adult', photos=upload(), note='   с пробелами   ')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        a = Analysis.objects.get()
        self.assertEqual(a.note, 'с пробелами')

    @patch('apps.analysis.views.ai_analyze', return_value=(FAKE_AI_RESULT, FAKE_AI_RAW))
    def test_note_too_long_rejected(self, _):
        resp = self._post(age_group='permanent_adult', photos=upload(), note='x' * (MAX_NOTE_LENGTH + 1))
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Analysis.objects.exists())

    @patch('apps.analysis.views.ai_analyze', return_value=(FAKE_AI_RESULT, FAKE_AI_RAW))
    def test_note_does_not_leak_into_ai_prompt(self, mock_ai):
        """Заметка — личная пометка для истории, а не часть промта ИИ."""
        self._post(age_group='permanent_adult', photos=upload(), note='СЕКРЕТНАЯ ЗАМЕТКА')
        args, kwargs = mock_ai.call_args
        _, prompt_arg = args
        self.assertNotIn('СЕКРЕТНАЯ ЗАМЕТКА', prompt_arg)


class AnalysisPhotoModelTests(TestCase):
    """Модель AnalysisPhoto и связь с Analysis."""

    def setUp(self):
        self.user = User.objects.create_user(email='u@x.ru', name='U', password='x')
        self.analysis = Analysis.objects.create(user=self.user, age_group='permanent_adult')

    def test_photos_related_name(self):
        AnalysisPhoto.objects.create(analysis=self.analysis, photo='photos/p.jpg', order=0)
        AnalysisPhoto.objects.create(analysis=self.analysis, photo='photos/p.jpg', order=1)
        self.assertEqual(self.analysis.photos.count(), 2)

    def test_max_photos_constant(self):
        self.assertEqual(MAX_PHOTOS, 5)


class AnalysisListTests(TestCase):
    """История анализов: пользователь видит только свои записи."""

    def setUp(self):
        self.client = APIClient()
        self.u1 = User.objects.create_user(email='a@x.ru', name='A', password='x', attempts_left=3)
        self.u2 = User.objects.create_user(email='b@x.ru', name='B', password='x', attempts_left=3)
        Analysis.objects.create(user=self.u1, age_group='milk', score=8)
        Analysis.objects.create(user=self.u2, age_group='mixed', score=5)

    def test_user_sees_only_own_analyses(self):
        self.client.force_authenticate(self.u1)
        resp = self.client.get(reverse('analysis-list'))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.data if isinstance(resp.data, list) else resp.data.get('results', resp.data)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['age_group'], 'milk')
        # Бейдж группы доступен на фронте через age_group_display
        self.assertIn('age_group_display', data[0])


class AnalysisListPaginationTests(TestCase):
    """Пагинация /api/analysis/ — этап 3 «История»."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(email='p@x.ru', name='P', password='x', attempts_left=3)
        for i in range(15):
            Analysis.objects.create(user=self.user, age_group='permanent_adult',
                                     score=10 - i % 10, is_valid=(i % 3 != 0))
        self.client.force_authenticate(self.user)
        self.url = reverse('analysis-list')

    def test_returns_paginated_envelope(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('results', resp.data)
        self.assertIn('count', resp.data)
        self.assertEqual(resp.data['count'], 15)

    def test_default_page_size_is_10(self):
        resp = self.client.get(self.url)
        self.assertEqual(len(resp.data['results']), 10)
        self.assertIsNotNone(resp.data['next'])

    def test_page_size_param_respected(self):
        resp = self.client.get(self.url, {'page_size': 5})
        self.assertEqual(len(resp.data['results']), 5)

    def test_page_size_above_max_capped(self):
        resp = self.client.get(self.url, {'page_size': 1000})
        # max_page_size=50, у нас всего 15
        self.assertEqual(len(resp.data['results']), 15)

    def test_second_page(self):
        resp = self.client.get(self.url, {'page': 2})
        self.assertEqual(len(resp.data['results']), 5)
        self.assertIsNone(resp.data['next'])

    def test_valid_only_filter(self):
        resp = self.client.get(self.url, {'valid_only': 'true', 'page_size': 50})
        ids_valid = [a['id'] for a in resp.data['results']]
        self.assertTrue(all(a['is_valid'] for a in resp.data['results']))
        self.assertEqual(len(ids_valid), Analysis.objects.filter(user=self.user, is_valid=True).count())


def _qwen_response(content: str):
    """Сборщик мок-ответа OpenRouter (OpenAI-совместимый формат)."""
    m = MagicMock()
    m.raise_for_status = MagicMock()
    m.json = MagicMock(return_value={'choices': [{'message': {'content': content}}]})
    m.text = content
    return m


@override_settings(
    OPENROUTER_API_KEY='test-or-key',
    OPENROUTER_APP_URL='https://example.test',
    OPENROUTER_APP_TITLE='Test App',
)
class QwenServiceTests(TestCase):
    """Юнит-тесты сервиса qwen.analyze — Qwen-VL через OpenRouter."""

    def test_payload_uses_chat_completions_with_image_url(self):
        payload_json = json.dumps({
            'is_valid': True, 'score': 8,
            'fresh_plaque_percent': 5, 'old_plaque_percent': 2,
            'problem_zones': ['z'], 'recommendations': ['r1', 'r2', 'r3'],
        })
        with patch('apps.analysis.services.qwen.requests.post',
                   return_value=_qwen_response(payload_json)) as mock_post:
            result, raw = qwen.analyze(
                [b'\xff\xd8imgbytes'], 'PROMPT',
                model='qwen/qwen3-vl-235b-a22b-instruct',
            )

        self.assertTrue(result['is_valid'])
        self.assertEqual(result['score'], 8)

        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], 'https://openrouter.ai/api/v1/chat/completions')
        body = kwargs['json']
        self.assertEqual(body['model'], 'qwen/qwen3-vl-235b-a22b-instruct')
        self.assertEqual(body['response_format'], {'type': 'json_object'})
        self.assertEqual(body['messages'][0]['role'], 'user')
        content = body['messages'][0]['content']
        # Текст ДО картинки (рекомендация OpenRouter для лучшего парсинга)
        self.assertEqual(content[0]['type'], 'text')
        self.assertEqual(content[0]['text'], 'PROMPT')
        self.assertEqual(content[1]['type'], 'image_url')
        self.assertTrue(content[1]['image_url']['url'].startswith('data:image/jpeg;base64,'))
        # Auth — Bearer + опциональные атрибуционные заголовки
        self.assertEqual(kwargs['headers']['Authorization'], 'Bearer test-or-key')
        self.assertEqual(kwargs['headers']['HTTP-Referer'], 'https://example.test')
        self.assertEqual(kwargs['headers']['X-Title'], 'Test App')

    def test_multi_photo_hint_appended(self):
        with patch('apps.analysis.services.qwen.requests.post',
                   return_value=_qwen_response('{"is_valid": false}')) as mock_post:
            qwen.analyze([b'a', b'b', b'c'], 'BASE')

        body = mock_post.call_args.kwargs['json']
        content = body['messages'][0]['content']
        # Один текстовый блок + три картинки
        self.assertEqual(len(content), 4)
        self.assertIn('3 фотографий', content[0]['text'])
        self.assertIn('BASE', content[0]['text'])

    def test_markdown_fence_stripped(self):
        wrapped = '```json\n{"is_valid": true, "score": 9}\n```'
        with patch('apps.analysis.services.qwen.requests.post',
                   return_value=_qwen_response(wrapped)):
            result, raw = qwen.analyze([b'x'], 'P')
        self.assertEqual(result['score'], 9)

    def test_garbage_json_returns_invalid(self):
        with patch('apps.analysis.services.qwen.requests.post',
                   return_value=_qwen_response('totally not json')):
            result, raw = qwen.analyze([b'x'], 'P')
        self.assertFalse(result['is_valid'])
        self.assertIsNone(result['score'])

    def test_attribution_headers_skipped_when_empty(self):
        with override_settings(OPENROUTER_APP_URL='', OPENROUTER_APP_TITLE=''):
            with patch('apps.analysis.services.qwen.requests.post',
                       return_value=_qwen_response('{"is_valid": false}')) as mock_post:
                qwen.analyze([b'x'], 'P')
        headers = mock_post.call_args.kwargs['headers']
        self.assertNotIn('HTTP-Referer', headers)
        self.assertNotIn('X-Title', headers)

    def test_missing_api_key_raises(self):
        with override_settings(OPENROUTER_API_KEY=''):
            with self.assertRaisesMessage(RuntimeError, 'OPENROUTER_API_KEY'):
                qwen.analyze([b'x'], 'P')

    def test_empty_photo_list_raises(self):
        with self.assertRaisesMessage(ValueError, 'пустой'):
            qwen.analyze([], 'P')


class HistoryContextTests(TestCase):
    """ИИ-память: build_history_context подмешивает прошлые анализы пациента в промт."""

    def setUp(self):
        SystemSettings.objects.create(key='prompt_text', value='BASE')
        self.user = User.objects.create_user(
            email='hist@example.com', name='H', password='x', attempts_left=5,
        )

    def _make_analysis(self, score, zones=None, recs=None, is_valid=True):
        return Analysis.objects.create(
            user=self.user,
            age_group='permanent_adult',
            score=score,
            fresh_plaque_percent=10,
            old_plaque_percent=5,
            problem_zones=zones or ['зона A'],
            recommendations=recs or ['rec1', 'rec2', 'rec3'],
            is_valid=is_valid,
        )

    def test_empty_history_returns_empty_string(self):
        from apps.analysis.services.ai_router import build_history_context
        self.assertEqual(build_history_context(self.user), '')

    def test_single_analysis_returns_context_block(self):
        from apps.analysis.services.ai_router import build_history_context
        self._make_analysis(score=7)
        ctx = build_history_context(self.user)
        self.assertIn('ИСТОРИЯ ПРЕДЫДУЩИХ АНАЛИЗОВ', ctx)
        # Оценки и проценты убраны из строк истории — модель не должна якориться на числа
        self.assertNotIn('оценка 7/10', ctx)
        self.assertNotIn('/10', ctx)
        self.assertNotIn('свежий налёт', ctx)
        self.assertNotIn('старый налёт', ctx)
        # Зоны и рекомендации по-прежнему присутствуют
        self.assertIn('зона A', ctx)
        self.assertIn('rec1', ctx)

    def test_invalid_analyses_excluded(self):
        from apps.analysis.services.ai_router import build_history_context
        self._make_analysis(score=7, is_valid=True)
        self._make_analysis(score=None, is_valid=False)
        ctx = build_history_context(self.user)
        # В контексте только 1 анализ (валидный), несмотря на 2 в базе
        self.assertEqual(ctx.count('Анализ от'), 1)

    def test_limit_5_by_default(self):
        from apps.analysis.services.ai_router import build_history_context
        for s in [3, 4, 5, 6, 7, 8, 9]:
            self._make_analysis(score=s)
        ctx = build_history_context(self.user)
        # Лимит 5, в базе 7 анализов
        self.assertEqual(ctx.count('Анализ от'), 5)

    def test_custom_limit(self):
        from apps.analysis.services.ai_router import build_history_context
        for s in [3, 4, 5, 6, 7]:
            self._make_analysis(score=s)
        ctx = build_history_context(self.user, limit=2)
        self.assertEqual(ctx.count('Анализ от'), 2)

    def test_ordered_newest_first(self):
        from apps.analysis.services.ai_router import build_history_context
        from django.utils import timezone
        from datetime import timedelta
        # Два анализа с разными зонами — порядок проверяем по зонам (не по оценке,
        # т.к. оценки убраны из истории).
        a1 = self._make_analysis(score=3, zones=['зона старая'])
        a2 = self._make_analysis(score=8, zones=['зона новая'])
        # Явно сдвигаем a1 в прошлое — auto_now_add может выставить одинаковые
        # timestamps при быстром последовательном создании.
        Analysis.objects.filter(pk=a1.pk).update(
            created_at=timezone.now() - timedelta(days=2),
        )
        # a2 свежее (создан позже) — должен быть первым в контексте
        ctx = build_history_context(self.user)
        idx_old = ctx.find('зона старая')
        idx_new = ctx.find('зона новая')
        self.assertGreater(idx_old, idx_new, 'свежий анализ (зона новая) должен идти раньше старого')

    def test_includes_instructions_for_model(self):
        from apps.analysis.services.ai_router import build_history_context
        self._make_analysis(score=7)
        ctx = build_history_context(self.user)
        # Зоны и оценка — только по текущему фото, история их не меняет
        self.assertIn('ТОЛЬКО тем', ctx)
        # Пункт «должны совпадать» удалён: идентичные фото обрабатывает кэш по хэшу
        self.assertNotIn('должны совпадать', ctx)
        self.assertIn('не повторяй прошлые', ctx)
        self.assertIn('ДИНАМИКУ НЕ ОЦЕНИВАЙ', ctx)
        self.assertNotIn('похвали пациента', ctx)

    def test_other_users_history_not_included(self):
        from apps.analysis.services.ai_router import build_history_context
        other = User.objects.create_user(
            email='other@example.com', name='O', password='x', attempts_left=3,
        )
        Analysis.objects.create(
            user=other, age_group='permanent_adult', score=2, is_valid=True,
            problem_zones=['чужая зона'], recommendations=['чужой совет'],
        )
        ctx = build_history_context(self.user)
        # У текущего юзера истории нет → пустая строка
        self.assertEqual(ctx, '')


class HistoryIntegrationTests(TestCase):
    """E2E проверка: при создании анализа в промт подмешивается история пользователя."""

    def setUp(self):
        SystemSettings.objects.create(key='prompt_text', value='FALLBACK')
        SystemSettings.objects.create(key='prompt_milk', value='MILK')
        SystemSettings.objects.create(key='prompt_mixed', value='MIXED')
        SystemSettings.objects.create(key='prompt_permanent', value='PERMANENT_PROMPT_BASE')
        SystemSettings.objects.create(key='ai_provider', value='gemini')
        SystemSettings.objects.create(key='ai_model', value='gemini-2.5-flash')

        self.user = User.objects.create_user(
            email='int@example.com', name='I', password='x', attempts_left=5,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.url = reverse('analysis-create')

    @patch('apps.analysis.views.ai_analyze', return_value=(FAKE_AI_RESULT, FAKE_AI_RAW))
    def test_first_analysis_has_no_history_in_prompt(self, mock_ai):
        resp = self.client.post(
            self.url,
            {'age_group': 'permanent_adult', 'photos': upload()},
            format='multipart',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        # Первый аргумент ai_analyze — список фото, второй — промт
        called_prompt = mock_ai.call_args[0][1]
        self.assertNotIn('ИСТОРИЯ ПРЕДЫДУЩИХ', called_prompt)
        self.assertEqual(called_prompt, 'PERMANENT_PROMPT_BASE')

    @patch('apps.analysis.views.ai_analyze', return_value=(FAKE_AI_RESULT, FAKE_AI_RAW))
    def test_second_analysis_includes_history(self, mock_ai):
        # Создаём первый анализ
        Analysis.objects.create(
            user=self.user, age_group='permanent_adult', score=6, is_valid=True,
            fresh_plaque_percent=20, old_plaque_percent=10,
            problem_zones=['нижние резцы'], recommendations=['нить', 'ирригатор', 'ёршики'],
        )
        # Второй анализ должен получить историю в промте
        self.client.post(
            self.url,
            {'age_group': 'permanent_adult', 'photos': upload()},
            format='multipart',
        )
        called_prompt = mock_ai.call_args[0][1]
        self.assertIn('ИСТОРИЯ ПРЕДЫДУЩИХ', called_prompt)
        self.assertIn('нижние резцы', called_prompt)
        self.assertIn('нить', called_prompt)
        # Базовый промт тоже на месте, после блока истории
        self.assertIn('PERMANENT_PROMPT_BASE', called_prompt)


FAKE_AI_INVALID = {
    'is_valid': False,
    'score': None,
    'fresh_plaque_percent': None,
    'old_plaque_percent': None,
    'problem_zones': [],
    'recommendations': [],
}
FAKE_AI_INVALID_RAW = '{"is_valid": false}'


def make_jpeg_color(color, size=(64, 64)):
    """JPEG заданного цвета — для генерации фото с разными байтами."""
    buf = BytesIO()
    Image.new('RGB', size, color=color).save(buf, format='JPEG')
    buf.seek(0)
    return buf.getvalue()


def upload_bytes(data, name='p.jpg'):
    return SimpleUploadedFile(name, data, content_type='image/jpeg')


class CachedResultTests(TestCase):
    """Кэш результата по хэшу фото: повторная загрузка тех же фото не дёргает ИИ,
    отдаёт сохранённый результат, но всё равно списывает попытку."""

    def setUp(self):
        SystemSettings.objects.create(key='prompt_text', value='FALLBACK')
        SystemSettings.objects.create(key='prompt_milk', value='MILK')
        SystemSettings.objects.create(key='prompt_permanent', value='PERMANENT')
        SystemSettings.objects.create(key='ai_provider', value='gemini')
        SystemSettings.objects.create(key='ai_model', value='gemini-2.5-flash')

        self.user = User.objects.create_user(
            email='cache@example.com', name='C', password='x', attempts_left=10,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.url = reverse('analysis-create')

        # Один и тот же набор байт → один и тот же хэш при повторной загрузке.
        self.photo_a = make_jpeg_color((200, 100, 100))
        self.photo_b = make_jpeg_color((10, 220, 30))

    def _post(self, data_list, age_group='permanent_adult', consent=False):
        files = [upload_bytes(d, f'p{i}.jpg') for i, d in enumerate(data_list)]
        payload = {'age_group': age_group, 'photos': files}
        if consent:
            payload['legal_rep_consent'] = 'true'
        return self.client.post(self.url, payload, format='multipart')

    @patch('apps.analysis.views.ai_analyze', return_value=(FAKE_AI_RESULT, FAKE_AI_RAW))
    def test_repeat_same_photo_uses_cache(self, mock_ai):
        r1 = self._post([self.photo_a])
        r2 = self._post([self.photo_a])
        self.assertEqual(r1.status_code, status.HTTP_201_CREATED, r1.data)
        self.assertEqual(r2.status_code, status.HTTP_201_CREATED, r2.data)
        # ИИ вызван только в первый раз
        self.assertEqual(mock_ai.call_count, 1)

        a1, a2 = Analysis.objects.order_by('id')
        self.assertEqual(a2.score, a1.score)
        self.assertEqual(a2.fresh_plaque_percent, a1.fresh_plaque_percent)
        self.assertEqual(a2.old_plaque_percent, a1.old_plaque_percent)
        self.assertEqual(a2.problem_zones, a1.problem_zones)
        self.assertEqual(a2.recommendations, a1.recommendations)
        self.assertTrue(a2.raw_response.startswith('[cached from analysis'))

    @patch('apps.analysis.views.ai_analyze', return_value=(FAKE_AI_RESULT, FAKE_AI_RAW))
    def test_different_file_calls_ai_again(self, mock_ai):
        self._post([self.photo_a])
        self._post([self.photo_b])
        # Разные байты → разный хэш → кэш не срабатывает
        self.assertEqual(mock_ai.call_count, 2)

    @patch('apps.analysis.views.ai_analyze', return_value=(FAKE_AI_RESULT, FAKE_AI_RAW))
    def test_same_photo_different_age_group_calls_ai_again(self, mock_ai):
        self._post([self.photo_a], age_group='permanent_adult')
        self._post([self.photo_a], age_group='milk', consent=True)
        # Тот же файл, но другая возрастная группа → кэш не срабатывает
        self.assertEqual(mock_ai.call_count, 2)

    @patch('apps.analysis.views.ai_analyze', return_value=(FAKE_AI_RESULT, FAKE_AI_RAW))
    def test_cached_still_deducts_attempt(self, _):
        before = self.user.attempts_left
        self._post([self.photo_a])
        self._post([self.photo_a])
        self.user.refresh_from_db()
        # Списано 2 попытки — кэш не освобождает от списания
        self.assertEqual(self.user.attempts_left, before - 2)
        a2 = Analysis.objects.order_by('id').last()
        self.assertTrue(a2.attempt_deducted)

    @patch('apps.analysis.views.ai_analyze', return_value=(FAKE_AI_RESULT, FAKE_AI_RAW))
    def test_photos_hash_filled_and_equal(self, _):
        self._post([self.photo_a])
        self._post([self.photo_a])
        a1, a2 = Analysis.objects.order_by('id')
        self.assertEqual(len(a1.photos_hash), 64)
        self.assertEqual(len(a2.photos_hash), 64)
        self.assertEqual(a1.photos_hash, a2.photos_hash)

    @patch('apps.analysis.views.ai_analyze', return_value=(FAKE_AI_RESULT, FAKE_AI_RAW))
    def test_hash_invariant_to_photo_order(self, mock_ai):
        self._post([self.photo_a, self.photo_b])
        self._post([self.photo_b, self.photo_a])
        a1, a2 = Analysis.objects.order_by('id')
        # [A,B] и [B,A] → одинаковый хэш (хэши сортируются)
        self.assertEqual(a1.photos_hash, a2.photos_hash)
        # Значит второй POST — попадание в кэш, ИИ вызван один раз
        self.assertEqual(mock_ai.call_count, 1)

    @patch('apps.analysis.views.ai_analyze', return_value=(FAKE_AI_INVALID, FAKE_AI_INVALID_RAW))
    def test_invalid_result_cached(self, mock_ai):
        self._post([self.photo_a])
        self._post([self.photo_a])
        # Невалидный результат тоже кэшируется (raw_response не пустой)
        self.assertEqual(mock_ai.call_count, 1)
        a2 = Analysis.objects.order_by('id').last()
        self.assertFalse(a2.is_valid)
        self.assertTrue(a2.raw_response.startswith('[cached from analysis'))

    @patch('apps.analysis.views.ai_analyze', return_value=(FAKE_AI_RESULT, FAKE_AI_RAW))
    def test_prompt_change_invalidates_cache(self, mock_ai):
        """Смена промта в SystemSettings инвалидирует кэш: ИИ вызывается повторно."""
        # Первый POST — ИИ вызван, результат сохранён с хэшем промта 'PERMANENT'
        self._post([self.photo_a])
        self.assertEqual(mock_ai.call_count, 1)

        # Меняем промт в БД — следующий запрос получит другой prompt_hash
        SystemSettings.objects.filter(key='prompt_permanent').update(value='PERMANENT_V2')

        # Второй POST с тем же фото — другой prompt_hash → кэш не срабатывает
        self._post([self.photo_a])
        self.assertEqual(mock_ai.call_count, 2,
                         'ИИ должен быть вызван повторно после изменения промта')


class PhotoStorageSelectionTests(TestCase):
    """Выбор хранилища для фото-полей: локальное по умолчанию, S3 при USE_S3_PHOTOS."""

    @override_settings(USE_S3_PHOTOS=False)
    def test_local_storage_when_s3_disabled(self):
        from django.core.files.storage import FileSystemStorage
        from apps.analysis.storages import photo_storage
        self.assertIsInstance(photo_storage(), FileSystemStorage)

    @override_settings(
        USE_S3_PHOTOS=True,
        AWS_STORAGE_BUCKET_NAME='teledent-photos',
        AWS_S3_ENDPOINT_URL='https://media.example.ru',
        AWS_ACCESS_KEY_ID='k', AWS_SECRET_ACCESS_KEY='s',
        AWS_S3_REGION_NAME='us-east-1', AWS_QUERYSTRING_EXPIRE=3600,
    )
    def test_s3_storage_when_enabled(self):
        from apps.analysis.storages import photo_storage
        storage = photo_storage()
        # Это S3Storage с нашими параметрами (без сетевых вызовов — конфиг локальный).
        self.assertEqual(storage.bucket_name, 'teledent-photos')
        self.assertEqual(storage.endpoint_url, 'https://media.example.ru')
        self.assertTrue(storage.querystring_auth)
        self.assertEqual(storage.querystring_expire, 3600)

    def test_photo_storage_is_deconstructible_callable(self):
        """Поле ссылается на photo_storage по import-пути, поэтому смена env не плодит
        миграции. Django вычисляет callable при определении класса и хранит сам callable
        в _storage_callable (а field.storage — это уже результат вызова)."""
        from apps.analysis.models import AnalysisPhoto
        from apps.analysis.storages import photo_storage
        field = AnalysisPhoto._meta.get_field('photo')
        self.assertIs(field._storage_callable, photo_storage)


class MigratePhotosCommandTests(TestCase):
    """Команда migrate_photos_to_rf не падает без данных и требует включённого S3."""

    @override_settings(USE_S3_PHOTOS=False)
    def test_requires_s3_enabled(self):
        from django.core.management import call_command
        from django.core.management.base import CommandError
        with self.assertRaises(CommandError):
            call_command('migrate_photos_to_rf', '--dry-run')


class DynamicsTests(TestCase):
    """Доп ТЗ: график динамики оценок. Источник данных — apps.analysis.dynamics,
    общий для ЛК (API /analysis/dynamics/) и админки."""

    def setUp(self):
        self.user = User.objects.create_user(email='d@t.ru', name='D', password='x')

    def _make(self, score, is_valid=True, day=1):
        from datetime import datetime, timezone as dt_tz
        a = Analysis.objects.create(user=self.user, score=score, is_valid=is_valid)
        # created_at = auto_now_add, поэтому фиксируем дату через update для порядка.
        Analysis.objects.filter(pk=a.pk).update(
            created_at=datetime(2026, 1, day, 12, 0, 0, tzinfo=dt_tz.utc),
        )
        return a

    def test_empty_when_no_valid_analyses(self):
        from apps.analysis.dynamics import build_dynamics
        data = build_dynamics(self.user)
        self.assertEqual(data['points'], [])
        self.assertEqual(data['summary']['count'], 0)
        self.assertEqual(data['summary']['trend'], 'none')

    def test_excludes_invalid_and_null_score(self):
        from apps.analysis.dynamics import build_dynamics
        self._make(6.0, day=1)
        self._make(8.0, is_valid=False, day=2)   # невалидный — не в графике
        self._make(None, day=3)                  # без оценки — не в графике
        data = build_dynamics(self.user)
        self.assertEqual(data['summary']['count'], 1)
        self.assertEqual([p['score'] for p in data['points']], [6.0])

    def test_summary_and_order(self):
        from apps.analysis.dynamics import build_dynamics
        self._make(5.0, day=1)
        self._make(9.0, day=2)
        self._make(7.0, day=3)
        data = build_dynamics(self.user)
        s = data['summary']
        self.assertEqual([p['score'] for p in data['points']], [5.0, 9.0, 7.0])  # по дате
        self.assertEqual(s['count'], 3)
        self.assertEqual(s['first'], 5.0)
        self.assertEqual(s['last'], 7.0)
        self.assertEqual(s['best'], 9.0)
        self.assertEqual(s['average'], 7.0)
        self.assertEqual(s['change'], 2.0)   # 7 - 5
        self.assertEqual(s['trend'], 'up')

    def test_trend_down_and_flat(self):
        from apps.analysis.dynamics import build_dynamics
        u2 = User.objects.create_user(email='d2@t.ru', name='D2', password='x')
        Analysis.objects.create(user=u2, score=8.0, is_valid=True)
        Analysis.objects.create(user=u2, score=6.0, is_valid=True)
        self.assertEqual(build_dynamics(u2)['summary']['trend'], 'down')

        self._make(7.0, day=1)
        self._make(7.0, day=2)
        self.assertEqual(build_dynamics(self.user)['summary']['trend'], 'flat')

    def test_api_requires_auth(self):
        client = APIClient()
        resp = client.get(reverse('analysis-dynamics'))
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_api_returns_dynamics(self):
        self._make(6.0, day=1)
        self._make(8.0, day=2)
        client = APIClient()
        client.force_authenticate(self.user)
        resp = client.get(reverse('analysis-dynamics'))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['summary']['count'], 2)
        self.assertEqual(resp.data['summary']['change'], 2.0)
        self.assertEqual(len(resp.data['points']), 2)
        self.assertIn('date', resp.data['points'][0])

    def test_api_isolates_users(self):
        """Динамика показывает только анализы самого пользователя."""
        self._make(6.0, day=1)
        other = User.objects.create_user(email='o@t.ru', name='O', password='x')
        Analysis.objects.create(user=other, score=1.0, is_valid=True)
        client = APIClient()
        client.force_authenticate(self.user)
        resp = client.get(reverse('analysis-dynamics'))
        self.assertEqual(resp.data['summary']['count'], 1)
        self.assertEqual(resp.data['points'][0]['score'], 6.0)


class DynamicsAdminRenderTests(TestCase):
    """Серверный SVG для админки строится без ошибок и экранирует подписи."""

    def test_empty_render(self):
        from apps.users.admin import _render_dynamics_svg
        html = _render_dynamics_svg({'points': [], 'summary': {
            'count': 0, 'first': None, 'last': None, 'best': None,
            'average': None, 'change': None, 'trend': 'none'}})
        self.assertIn('Нет завершённых анализов', html)

    def test_render_with_points(self):
        from apps.users.admin import _render_dynamics_svg
        from apps.analysis.dynamics import build_dynamics
        u = User.objects.create_user(email='a@t.ru', name='A', password='x')
        Analysis.objects.create(user=u, score=5.0, is_valid=True)
        Analysis.objects.create(user=u, score=8.0, is_valid=True)
        html = _render_dynamics_svg(build_dynamics(u))
        self.assertIn('<svg', html)
        self.assertIn('10-балльной', html)


class DeriveScoreTests(TestCase):
    """Балл выводится детерминированно из процента налёта (фикс «оценка липнет к 7»)."""

    def test_clean_is_ten(self):
        from apps.analysis.services.ai_router import derive_score
        self.assertEqual(derive_score(0, 0), 10)
        self.assertEqual(derive_score(1, 0.5), 10)

    def test_monotonic_decreasing(self):
        """Чем больше налёта — тем не выше балл (никогда не растёт)."""
        from apps.analysis.services.ai_router import derive_score
        prev = 11
        for total in range(0, 101, 2):
            s = derive_score(total, 0)
            self.assertLessEqual(s, prev)
            self.assertTrue(1 <= s <= 10)
            prev = s

    def test_dirty_photo_is_low(self):
        from apps.analysis.services.ai_router import derive_score
        self.assertLessEqual(derive_score(30, 40), 3)   # 70% налёта
        self.assertLessEqual(derive_score(50, 45), 2)   # 95% налёта

    def test_same_input_same_score(self):
        """Воспроизводимость: одинаковый ввод — одинаковый балл."""
        from apps.analysis.services.ai_router import derive_score
        self.assertEqual(derive_score(15, 25), derive_score(15, 25))

    def test_score_follows_percent_not_sticks(self):
        """Регресс на жалобу: разный процент даёт разный балл, а не один и тот же 7."""
        from apps.analysis.services.ai_router import derive_score
        scores = {derive_score(p, 0) for p in (5, 12, 20, 30, 40, 55)}
        self.assertGreater(len(scores), 1)

    def test_none_when_no_percent(self):
        from apps.analysis.services.ai_router import derive_score
        self.assertIsNone(derive_score(None, None))

    def test_caps_at_100(self):
        from apps.analysis.services.ai_router import derive_score
        self.assertEqual(derive_score(80, 80), 1)


class AiRouterDeriveIntegrationTests(TestCase):
    """ai_router.analyze перезаписывает «интуитивный» балл модели на выведенный из %."""

    def setUp(self):
        SystemSettings.objects.create(key='ai_provider', value='gemini')
        SystemSettings.objects.create(key='ai_model', value='gemini-2.5-flash')

    def test_score_overridden_from_percent(self):
        from apps.analysis.services import ai_router
        model_out = ({
            'is_valid': True, 'score': 7,            # «интуиция» модели
            'fresh_plaque_percent': 0, 'old_plaque_percent': 1,  # фактически чисто
            'problem_zones': [], 'recommendations': [],
        }, 'raw')
        with patch('apps.analysis.services.gemini.analyze', return_value=model_out):
            result, _ = ai_router.analyze([b'x'], 'prompt')
        self.assertEqual(result['score'], 10)        # выведено из 1% налёта

    def test_invalid_keeps_none_score(self):
        from apps.analysis.services import ai_router
        model_out = ({
            'is_valid': False, 'score': None,
            'fresh_plaque_percent': None, 'old_plaque_percent': None,
            'problem_zones': [], 'recommendations': [],
        }, 'raw')
        with patch('apps.analysis.services.gemini.analyze', return_value=model_out):
            result, _ = ai_router.analyze([b'x'], 'prompt')
        self.assertIsNone(result['score'])


def _fake_gigachat_client(content: str, file_id: str = 'file-xyz'):
    """Мок SDK-клиента GigaChat: контекст-менеджер с upload_file и chat.
    Возвращает (cm, client): cm подставляется вместо _build_client(),
    client — то, что отдаёт cm.__enter__() (на нём проверяем вызовы)."""
    cm = MagicMock()
    client = cm.__enter__.return_value
    client.upload_file.return_value = MagicMock(id_=file_id)
    resp = MagicMock()
    resp.choices = [MagicMock(message=MagicMock(content=content))]
    client.chat.return_value = resp
    return cm, client


@override_settings(GIGACHAT_CREDENTIALS='test-cred', GIGACHAT_SCOPE='GIGACHAT_API_PERS')
class GigaChatServiceTests(TestCase):
    """Юнит-тесты сервиса gigachat.analyze — GigaChat (Сбер)."""

    def test_uploads_photo_and_parses_json(self):
        from apps.analysis.services import gigachat
        payload = json.dumps({
            'is_valid': True, 'score': 8,
            'fresh_plaque_percent': 5, 'old_plaque_percent': 2,
            'problem_zones': ['z'], 'recommendations': ['r1', 'r2', 'r3'],
        })
        cm, client = _fake_gigachat_client(payload)
        with patch('apps.analysis.services.gigachat._build_client', return_value=cm):
            result, raw = gigachat.analyze([b'\xff\xd8img'], 'PROMPT', model='GigaChat-2-Max')
        self.assertTrue(result['is_valid'])
        self.assertEqual(result['score'], 8)
        client.upload_file.assert_called_once()
        chat_arg = client.chat.call_args.args[0]
        self.assertEqual(chat_arg.model, 'GigaChat-2-Max')
        self.assertEqual(chat_arg.messages[0].attachments, ['file-xyz'])
        self.assertEqual(chat_arg.messages[0].content, 'PROMPT')

    def test_multi_photo_hint_and_multiple_attachments(self):
        from apps.analysis.services import gigachat
        cm, client = _fake_gigachat_client('{"is_valid": false}')
        with patch('apps.analysis.services.gigachat._build_client', return_value=cm):
            gigachat.analyze([b'a', b'b', b'c'], 'BASE')
        self.assertEqual(client.upload_file.call_count, 3)
        chat_arg = client.chat.call_args.args[0]
        self.assertEqual(len(chat_arg.messages[0].attachments), 3)
        self.assertIn('3 фотографий', chat_arg.messages[0].content)
        self.assertIn('BASE', chat_arg.messages[0].content)

    def test_markdown_fence_stripped(self):
        from apps.analysis.services import gigachat
        cm, _ = _fake_gigachat_client('```json\n{"is_valid": true, "score": 9}\n```')
        with patch('apps.analysis.services.gigachat._build_client', return_value=cm):
            result, raw = gigachat.analyze([b'x'], 'P')
        self.assertEqual(result['score'], 9)

    def test_garbage_json_returns_invalid(self):
        from apps.analysis.services import gigachat
        cm, _ = _fake_gigachat_client('not json at all')
        with patch('apps.analysis.services.gigachat._build_client', return_value=cm):
            result, raw = gigachat.analyze([b'x'], 'P')
        self.assertFalse(result['is_valid'])
        self.assertIsNone(result['score'])

    def test_empty_response_invalid(self):
        from apps.analysis.services import gigachat
        cm, _ = _fake_gigachat_client('   ')
        with patch('apps.analysis.services.gigachat._build_client', return_value=cm):
            result, raw = gigachat.analyze([b'x'], 'P')
        self.assertFalse(result['is_valid'])

    def test_wrong_model_falls_back_to_vision_default(self):
        """Если в ai_model осталась модель чужой сети — берём дефолтную vision-модель GigaChat."""
        from apps.analysis.services import gigachat
        cm, client = _fake_gigachat_client('{"is_valid": false}')
        with patch('apps.analysis.services.gigachat._build_client', return_value=cm):
            gigachat.analyze([b'x'], 'P', model='gemini-2.5-flash')
        chat_arg = client.chat.call_args.args[0]
        self.assertEqual(chat_arg.model, gigachat.AVAILABLE_MODELS[0])

    def test_missing_credentials_raises(self):
        from apps.analysis.services import gigachat
        with override_settings(GIGACHAT_CREDENTIALS=''):
            with self.assertRaisesMessage(RuntimeError, 'GIGACHAT_CREDENTIALS'):
                gigachat.analyze([b'x'], 'P')

    def test_empty_photo_list_raises(self):
        from apps.analysis.services import gigachat
        with self.assertRaisesMessage(ValueError, 'пустой'):
            gigachat.analyze([], 'P')


class AiRouterGigaChatDispatchTests(TestCase):
    """ai_router маршрутизирует в GigaChat при provider=gigachat и всё равно
    переписывает «интуитивный» балл на выведенный из % налёта."""

    def setUp(self):
        SystemSettings.objects.create(key='ai_provider', value='gigachat')
        SystemSettings.objects.create(key='ai_model', value='GigaChat-2-Max')

    def test_router_dispatches_to_gigachat_and_overrides_score(self):
        from apps.analysis.services import ai_router
        model_out = ({
            'is_valid': True, 'score': 6,            # «интуиция» модели
            'fresh_plaque_percent': 1, 'old_plaque_percent': 0,  # фактически чисто
            'problem_zones': [], 'recommendations': [],
        }, 'raw')
        with patch('apps.analysis.services.gigachat.analyze', return_value=model_out) as m:
            result, _ = ai_router.analyze([b'x'], 'prompt')
        m.assert_called_once()
        self.assertEqual(result['score'], 10)        # выведено из 1% налёта


# ============================================================================
# ЭКСПРЕСС-ОЦЕНКА (kind=express): фото без индикатора, только текст, свой счётчик
# ============================================================================

FAKE_EXPRESS_RESULT = {
    'is_valid': True,
    'observations': ['Зубы в целом выглядят ухоженными', 'У линии дёсен заметен мягкий налёт'],
    'recommendations': ['rec 1', 'rec 2', 'rec 3'],
}
FAKE_EXPRESS_RAW = '{"is_valid": true}'


class ExpressCreateApiTests(TestCase):
    """E2E экспресс-оценки: свой счётчик, отсутствие цифр, валидация фото."""

    def setUp(self):
        SystemSettings.objects.create(key='prompt_express', value='EXPRESS')
        SystemSettings.objects.create(key='prompt_text', value='FALLBACK')
        SystemSettings.objects.create(key='ai_provider', value='gemini')
        SystemSettings.objects.create(key='ai_model', value='gemini-2.5-flash')

        self.user = User.objects.create_user(
            email='e@example.com', name='E', password='x',
            attempts_left=5, express_attempts_left=3,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.url = reverse('analysis-express')

    def _post(self, **kwargs):
        return self.client.post(self.url, kwargs, format='multipart')

    @patch('apps.analysis.views.ai_analyze_express',
           return_value=(FAKE_EXPRESS_RESULT, FAKE_EXPRESS_RAW))
    def test_creates_express_without_any_numbers(self, _):
        resp = self._post(age_group='permanent_adult', photos=upload())
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)

        a = Analysis.objects.get()
        self.assertEqual(a.kind, 'express')
        self.assertTrue(a.is_valid)
        self.assertEqual(a.observations, FAKE_EXPRESS_RESULT['observations'])
        self.assertEqual(a.recommendations, FAKE_EXPRESS_RESULT['recommendations'])
        # Ключевое требование заказчика: никаких баллов и процентов
        self.assertIsNone(a.score)
        self.assertIsNone(a.fresh_plaque_percent)
        self.assertIsNone(a.old_plaque_percent)
        self.assertEqual(a.problem_zones, [])
        self.assertEqual(a.dynamics_text, '')
        self.assertIsNone(resp.data['score'])

    @patch('apps.analysis.views.ai_analyze_express',
           return_value=(FAKE_EXPRESS_RESULT, FAKE_EXPRESS_RAW))
    def test_spends_only_express_counter(self, _):
        self._post(age_group='permanent_adult', photos=upload())
        self.user.refresh_from_db()
        self.assertEqual(self.user.express_attempts_left, 2)
        # Платный баланс полных анализов не тронут
        self.assertEqual(self.user.attempts_left, 5)

    @patch('apps.analysis.views.ai_analyze_express',
           return_value=(FAKE_EXPRESS_RESULT, FAKE_EXPRESS_RAW))
    def test_no_express_attempts_left_rejected(self, _):
        self.user.express_attempts_left = 0
        self.user.save(update_fields=['express_attempts_left'])
        resp = self._post(age_group='permanent_adult', photos=upload())
        self.assertEqual(resp.status_code, status.HTTP_402_PAYMENT_REQUIRED)
        self.assertFalse(Analysis.objects.exists())

    @patch('apps.analysis.views.ai_analyze_express',
           return_value=(FAKE_EXPRESS_RESULT, FAKE_EXPRESS_RAW))
    def test_full_analysis_balance_does_not_unlock_express(self, _):
        """Полные попытки есть, экспресс-попыток нет — экспресс всё равно закрыт."""
        self.user.express_attempts_left = 0
        self.user.attempts_left = 10
        self.user.save()
        resp = self._post(age_group='permanent_adult', photos=upload())
        self.assertEqual(resp.status_code, status.HTTP_402_PAYMENT_REQUIRED)

    @patch('apps.analysis.views.ai_analyze_express',
           return_value=(FAKE_EXPRESS_RESULT, FAKE_EXPRESS_RAW))
    def test_more_than_one_photo_rejected(self, _):
        resp = self._post(age_group='permanent_adult', photos=[upload('a.jpg'), upload('b.jpg')])
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Analysis.objects.exists())
        self.user.refresh_from_db()
        self.assertEqual(self.user.express_attempts_left, 3)

    @patch('apps.analysis.views.ai_analyze_express',
           return_value=(FAKE_EXPRESS_RESULT, FAKE_EXPRESS_RAW))
    def test_underage_requires_consent(self, _):
        resp = self._post(age_group='milk', photos=upload())
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('legal_rep_consent', resp.data)
        self.assertFalse(Analysis.objects.exists())

    @patch('apps.analysis.views.ai_analyze_express',
           return_value=(FAKE_EXPRESS_RESULT, FAKE_EXPRESS_RAW))
    def test_underage_with_consent_logs_ip(self, _):
        resp = self._post(
            age_group='milk', legal_rep_consent='true', photos=upload(),
            HTTP_X_FORWARDED_FOR='203.0.113.7',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        a = Analysis.objects.get()
        self.assertTrue(a.legal_rep_consent)
        self.assertEqual(a.consent_text_version, CONSENT_TEXT_VERSION)
        self.assertIsNotNone(a.consent_datetime)

    @patch('apps.analysis.views.ai_analyze_express', side_effect=RuntimeError('AI down'))
    def test_ai_error_does_not_charge_attempt(self, _):
        resp = self._post(age_group='permanent_adult', photos=upload())
        self.assertEqual(resp.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertFalse(Analysis.objects.exists())
        self.user.refresh_from_db()
        self.assertEqual(self.user.express_attempts_left, 3)

    def test_missing_prompt_setting_returns_503(self):
        SystemSettings.objects.filter(key='prompt_express').delete()
        resp = self._post(age_group='permanent_adult', photos=upload())
        self.assertEqual(resp.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.user.refresh_from_db()
        self.assertEqual(self.user.express_attempts_left, 3)

    @patch('apps.analysis.views.ai_analyze_express',
           return_value=({'is_valid': False, 'observations': [], 'recommendations': []}, 'raw'))
    def test_invalid_photo_marks_invalid(self, _):
        resp = self._post(age_group='permanent_adult', photos=upload())
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        a = Analysis.objects.get()
        self.assertFalse(a.is_valid)
        self.assertEqual(a.observations, [])

    @patch('apps.analysis.views.ai_analyze_express',
           return_value=(FAKE_EXPRESS_RESULT, FAKE_EXPRESS_RAW))
    def test_note_saved_on_express_too(self, _):
        resp = self._post(age_group='permanent_adult', photos=upload(), note='Заметка к экспресс-оценке')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        a = Analysis.objects.get()
        self.assertEqual(a.note, 'Заметка к экспресс-оценке')
        self.assertEqual(resp.data['note'], 'Заметка к экспресс-оценке')

    @patch('apps.analysis.views.ai_analyze_express',
           return_value=(FAKE_EXPRESS_RESULT, FAKE_EXPRESS_RAW))
    def test_note_too_long_rejected_on_express(self, _):
        resp = self._post(age_group='permanent_adult', photos=upload(), note='x' * (MAX_NOTE_LENGTH + 1))
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Analysis.objects.exists())


class ExpressIsolationTests(TestCase):
    """Экспресс-оценка не протекает в динамику, в историю для ИИ и в кэш."""

    def setUp(self):
        SystemSettings.objects.create(key='prompt_express', value='EXPRESS')
        SystemSettings.objects.create(key='prompt_text', value='FULL')
        SystemSettings.objects.create(key='ai_provider', value='gemini')
        SystemSettings.objects.create(key='ai_model', value='gemini-2.5-flash')
        self.user = User.objects.create_user(
            email='iso@example.com', name='I', password='x',
            attempts_left=5, express_attempts_left=5,
        )

    def test_express_excluded_from_dynamics(self):
        from apps.analysis.dynamics import build_dynamics
        # Экспресс с проставленным баллом (аномалия) не должен попасть в график
        Analysis.objects.create(user=self.user, kind='express', is_valid=True, score=9)
        Analysis.objects.create(user=self.user, kind='indicator', is_valid=True, score=6)

        data = build_dynamics(self.user)
        self.assertEqual(data['summary']['count'], 1)
        self.assertEqual(data['points'][0]['score'], 6)

    def test_express_excluded_from_ai_history_context(self):
        from apps.analysis.services.ai_router import build_history_context
        Analysis.objects.create(
            user=self.user, kind='express', is_valid=True, score=8,
            problem_zones=['ЗОНА ИЗ ЭКСПРЕССА'], recommendations=['r'],
        )
        ctx = build_history_context(self.user)
        self.assertNotIn('ЗОНА ИЗ ЭКСПРЕССА', ctx)
        self.assertEqual(ctx, '')

    @patch('apps.analysis.views.ai_analyze', return_value=(FAKE_AI_RESULT, FAKE_AI_RAW))
    @patch('apps.analysis.views.ai_analyze_express',
           return_value=(FAKE_EXPRESS_RESULT, FAKE_EXPRESS_RAW))
    def test_same_photo_in_both_modes_does_not_share_cache(self, mock_express, mock_full):
        """Одно и то же фото в двух режимах — два разных результата, ИИ зовём дважды.
        Если бы kind не входил в ключ кэша, полный анализ переиспользовал бы результат
        экспресс-оценки (без баллов) и наоборот."""
        client = APIClient()
        client.force_authenticate(self.user)
        blob = make_jpeg()

        r1 = client.post(
            reverse('analysis-express'),
            {'age_group': 'permanent_adult',
             'photos': SimpleUploadedFile('p.jpg', blob, content_type='image/jpeg')},
            format='multipart',
        )
        r2 = client.post(
            reverse('analysis-create'),
            {'age_group': 'permanent_adult',
             'photos': SimpleUploadedFile('p.jpg', blob, content_type='image/jpeg')},
            format='multipart',
        )
        self.assertEqual(r1.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r2.status_code, status.HTTP_201_CREATED)

        mock_express.assert_called_once()
        mock_full.assert_called_once()

        express = Analysis.objects.get(kind='express')
        full = Analysis.objects.get(kind='indicator')
        self.assertEqual(express.photos_hash, full.photos_hash)  # фото и правда одинаковые
        self.assertIsNone(express.score)
        self.assertEqual(full.score, 7)

    def test_history_can_be_filtered_by_kind(self):
        Analysis.objects.create(user=self.user, kind='express', is_valid=True)
        Analysis.objects.create(user=self.user, kind='indicator', is_valid=True, score=5)
        client = APIClient()
        client.force_authenticate(self.user)

        all_items = client.get(reverse('analysis-list')).data['results']
        self.assertEqual(len(all_items), 2)

        only_express = client.get(reverse('analysis-list'), {'kind': 'express'}).data['results']
        self.assertEqual(len(only_express), 1)
        self.assertEqual(only_express[0]['kind'], 'express')
        self.assertEqual(only_express[0]['kind_display'], 'Экспресс-оценка')


class AnalyzeExpressRouterTests(TestCase):
    """analyze_express: числа вырезаются, даже если модель их прислала."""

    def setUp(self):
        SystemSettings.objects.create(key='ai_provider', value='gemini')
        SystemSettings.objects.create(key='ai_model', value='gemini-2.5-flash')

    def test_strips_numbers_model_invented(self):
        from apps.analysis.services import ai_router
        # Модель проигнорировала запрет и всё равно насочиняла цифры
        model_out = ({
            'is_valid': True,
            'score': 7,
            'fresh_plaque_percent': 30,
            'old_plaque_percent': 10,
            'observations': ['видно налёт'],
            'recommendations': ['r1', 'r2', 'r3'],
        }, 'raw')
        with patch('apps.analysis.services.gemini.analyze', return_value=model_out):
            result, _ = ai_router.analyze_express([b'x'], 'prompt')

        self.assertEqual(set(result), {'is_valid', 'observations', 'recommendations'})
        self.assertNotIn('score', result)
        self.assertNotIn('fresh_plaque_percent', result)

    def test_valid_without_observations_becomes_invalid(self):
        from apps.analysis.services import ai_router
        model_out = ({'is_valid': True, 'observations': [], 'recommendations': ['r']}, 'raw')
        with patch('apps.analysis.services.gemini.analyze', return_value=model_out):
            result, _ = ai_router.analyze_express([b'x'], 'prompt')
        self.assertFalse(result['is_valid'])
        self.assertEqual(result['recommendations'], [])

    def test_string_instead_of_list_is_normalized(self):
        from apps.analysis.services import ai_router
        model_out = ({'is_valid': True, 'observations': 'одна строка',
                      'recommendations': ['r1', '', '  ', 'r2', 'r3', 'r4']}, 'raw')
        with patch('apps.analysis.services.gemini.analyze', return_value=model_out):
            result, _ = ai_router.analyze_express([b'x'], 'prompt')
        self.assertEqual(result['observations'], ['одна строка'])
        # пустые строки выброшены, список обрезан до 3
        self.assertEqual(result['recommendations'], ['r1', 'r2', 'r3'])

    def test_invalid_result_clears_everything(self):
        from apps.analysis.services import ai_router
        model_out = ({'is_valid': False, 'observations': ['x'], 'recommendations': ['y']}, 'raw')
        with patch('apps.analysis.services.gemini.analyze', return_value=model_out):
            result, _ = ai_router.analyze_express([b'x'], 'prompt')
        self.assertFalse(result['is_valid'])
        self.assertEqual(result['observations'], [])
        self.assertEqual(result['recommendations'], [])


class GeminiGlobalLocationTests(TestCase):
    """Модели gemini-3* опубликованы только в location=global (в us-central1 → 404)."""

    def test_gemini3_needs_global(self):
        from apps.analysis.services.gemini import _needs_global_location
        self.assertTrue(_needs_global_location('gemini-3-flash-preview'))
        self.assertTrue(_needs_global_location('gemini-3.1-pro-preview'))
        self.assertTrue(_needs_global_location('gemini-3.5-flash'))
        self.assertFalse(_needs_global_location('gemini-2.5-flash'))
        self.assertFalse(_needs_global_location('gemini-2.5-pro'))
        self.assertFalse(_needs_global_location(''))

    @override_settings(USE_VERTEX_AI=True, GCP_PROJECT_ID='proj', GCP_LOCATION='us-central1')
    def test_client_switches_location_for_gemini3(self):
        from apps.analysis.services import gemini
        with patch.object(gemini.genai, 'Client') as mock_client:
            gemini._build_client('gemini-3.5-flash')
            self.assertEqual(mock_client.call_args.kwargs['location'], 'global')

            gemini._build_client('gemini-2.5-flash')
            self.assertEqual(mock_client.call_args.kwargs['location'], 'us-central1')


# ============================================================================
# РАЗДЕЛЬНЫЙ ВЫБОР НЕЙРОСЕТИ: у экспресс-оценки свои ai_provider_express / ai_model_express
# ============================================================================


class ResolveAiTargetTests(TestCase):
    """Пустые настройки экспресса означают «как в основном анализе» — старые
    инсталляции (где ключей нет вовсе) обязаны работать ровно как раньше."""

    def _set(self, **kwargs):
        for key, value in kwargs.items():
            SystemSettings.objects.update_or_create(key=key, defaults={'value': value})

    def test_indicator_uses_base_settings(self):
        from apps.analysis.services.ai_router import resolve_ai_target
        self._set(ai_provider='qwen', ai_model='qwen/qwen3-vl-235b-a22b-instruct')
        self.assertEqual(
            resolve_ai_target(express=False),
            ('qwen', 'qwen/qwen3-vl-235b-a22b-instruct'),
        )

    def test_express_falls_back_to_base_when_not_configured(self):
        from apps.analysis.services.ai_router import resolve_ai_target
        self._set(ai_provider='gigachat', ai_model='GigaChat-2-Max')
        self.assertEqual(resolve_ai_target(express=True), ('gigachat', 'GigaChat-2-Max'))

    def test_express_falls_back_when_keys_empty(self):
        from apps.analysis.services.ai_router import resolve_ai_target
        self._set(ai_provider='gemini', ai_model='gemini-2.5-pro',
                  ai_provider_express='', ai_model_express='')
        self.assertEqual(resolve_ai_target(express=True), ('gemini', 'gemini-2.5-pro'))

    def test_express_uses_own_provider_and_model(self):
        from apps.analysis.services.ai_router import resolve_ai_target
        self._set(ai_provider='gemini', ai_model='gemini-2.5-pro',
                  ai_provider_express='gigachat', ai_model_express='GigaChat-2')
        self.assertEqual(resolve_ai_target(express=True), ('gigachat', 'GigaChat-2'))
        # Основной анализ при этом не тронут.
        self.assertEqual(resolve_ai_target(express=False), ('gemini', 'gemini-2.5-pro'))

    def test_express_provider_without_model_takes_provider_default(self):
        """Сеть переключили, модель не выбрали: подставлять модель другой сети
        нельзя — в GigaChat не существует gemini-2.5-pro."""
        from apps.analysis.services.ai_router import resolve_ai_target, _DEFAULT_MODEL
        self._set(ai_provider='gemini', ai_model='gemini-2.5-pro',
                  ai_provider_express='gigachat', ai_model_express='')
        self.assertEqual(
            resolve_ai_target(express=True),
            ('gigachat', _DEFAULT_MODEL['gigachat']),
        )

    def test_express_same_provider_without_model_keeps_base_model(self):
        from apps.analysis.services.ai_router import resolve_ai_target
        self._set(ai_provider='gemini', ai_model='gemini-2.5-pro',
                  ai_provider_express='gemini', ai_model_express='')
        self.assertEqual(resolve_ai_target(express=True), ('gemini', 'gemini-2.5-pro'))


class ExpressDispatchRoutingTests(TestCase):
    """analyze_express уходит в свою сеть, analyze — в основную. Проверяем, что
    один режим нельзя случайно увести за собой при переключении другого."""

    def setUp(self):
        SystemSettings.objects.create(key='ai_provider', value='gemini')
        SystemSettings.objects.create(key='ai_model', value='gemini-2.5-pro')
        SystemSettings.objects.create(key='ai_provider_express', value='gigachat')
        SystemSettings.objects.create(key='ai_model_express', value='GigaChat-2')

    def test_express_goes_to_its_own_provider(self):
        from apps.analysis.services import ai_router
        out = ({'is_valid': True, 'observations': ['ok'], 'recommendations': ['r']}, 'raw')
        with patch('apps.analysis.services.gigachat.analyze', return_value=out) as giga, \
                patch('apps.analysis.services.gemini.analyze') as gem:
            ai_router.analyze_express([b'x'], 'P')
        gem.assert_not_called()
        self.assertEqual(giga.call_args.kwargs['model'], 'GigaChat-2')

    def test_indicator_stays_on_base_provider(self):
        from apps.analysis.services import ai_router
        out = ({
            'is_valid': True, 'score': 5, 'fresh_plaque_percent': 2, 'old_plaque_percent': 0,
            'problem_zones': [], 'recommendations': [],
        }, 'raw')
        with patch('apps.analysis.services.gemini.analyze', return_value=out) as gem, \
                patch('apps.analysis.services.gigachat.analyze') as giga:
            ai_router.analyze([b'x'], 'P')
        giga.assert_not_called()
        self.assertEqual(gem.call_args.kwargs['model'], 'gemini-2.5-pro')


class ExpressAnalysisModelLabelTests(TestCase):
    """В карточке экспресс-анализа должна сохраняться модель экспресса, а не основная."""

    def setUp(self):
        SystemSettings.objects.create(key='prompt_express', value='EXPRESS')
        SystemSettings.objects.create(key='ai_provider', value='gemini')
        SystemSettings.objects.create(key='ai_model', value='gemini-2.5-pro')
        SystemSettings.objects.create(key='ai_provider_express', value='gigachat')
        SystemSettings.objects.create(key='ai_model_express', value='GigaChat-2')
        self.user = User.objects.create_user(
            email='lbl@example.com', name='L', password='x',
            attempts_left=2, express_attempts_left=2,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    @patch('apps.analysis.views.ai_analyze_express',
           return_value=(FAKE_EXPRESS_RESULT, FAKE_EXPRESS_RAW))
    def test_saved_ai_model_is_express_one(self, _):
        resp = self.client.post(
            reverse('analysis-express'),
            {'photos': upload(), 'age_group': 'permanent_adult'},
            format='multipart',
        )
        self.assertEqual(resp.status_code, 201)
        analysis = Analysis.objects.get(pk=resp.data['id'])
        self.assertEqual(analysis.ai_model, 'gigachat/GigaChat-2')


# ─── CV-скрипт измерения налёта (plaque_cv) ──────────────────────────────────

from apps.analysis.services.plaque_cv import (  # noqa: E402
    measure_photo, measure_photos, build_measured_block,
)


def make_mouth_jpeg(with_fresh=True, with_old=True, size=(400, 300)):
    """Синтетический «рот»: тёмно-красный фон (полость/дёсны), белая полоса
    «зубов» в центре, поверх — пятна цветов индикатора. Цвета подобраны под
    реальный краситель: маджента (H≈162) и синий (H≈110) в HSV OpenCV."""
    img = Image.new('RGB', size, color=(120, 30, 30))
    px = img.load()
    for x in range(60, 340):
        for y in range(110, 190):
            px[x, y] = (245, 245, 240)                    # эмаль
    if with_fresh:
        for x in range(80, 140):
            for y in range(120, 180):
                px[x, y] = (230, 40, 180)                 # свежий: маджента
    if with_old:
        for x in range(200, 260):
            for y in range(120, 180):
                px[x, y] = (60, 90, 230)                  # зрелый: синий
    buf = BytesIO()
    img.save(buf, format='JPEG', quality=95)
    return buf.getvalue()


class PlaqueCvUnitTests(TestCase):
    """Юнит-тесты измерителя: без Django-стека, чистые картинки."""

    def test_measures_synthetic_mouth(self):
        m = measure_photo(make_mouth_jpeg())
        self.assertTrue(m.ok)
        # Пятна по 3600px на полосе 22400px ≈ 16%; допуск на JPEG-сглаживание краёв.
        self.assertAlmostEqual(m.fresh_percent, 16.0, delta=6.0)
        self.assertAlmostEqual(m.old_percent, 16.0, delta=6.0)

    def test_clean_teeth_measure_zero(self):
        m = measure_photo(make_mouth_jpeg(with_fresh=False, with_old=False))
        self.assertTrue(m.ok)
        self.assertLessEqual(m.fresh_percent, 2.0)
        self.assertLessEqual(m.old_percent, 2.0)

    def test_no_teeth_fails_honestly(self):
        """Однотонная красная картинка: якорной эмали нет — ok=False, не ноль процентов."""
        m = measure_photo(make_jpeg())
        self.assertFalse(m.ok)
        self.assertIsNone(m.fresh_percent)

    def test_garbage_bytes_fail_without_exception(self):
        self.assertFalse(measure_photo(b'not a jpeg at all').ok)

    def test_deterministic(self):
        blob = make_mouth_jpeg()
        m1, m2 = measure_photo(blob), measure_photo(blob)
        self.assertEqual((m1.fresh_pixels, m1.old_pixels, m1.tooth_pixels),
                         (m2.fresh_pixels, m2.old_pixels, m2.tooth_pixels))

    def test_overlay_is_valid_jpeg(self):
        m = measure_photo(make_mouth_jpeg())
        self.assertIsNotNone(m.overlay_jpeg)
        overlay = Image.open(BytesIO(m.overlay_jpeg))
        self.assertEqual(overlay.size, (400, 300))

    def test_measure_photos_requires_all_ok(self):
        """Если хотя бы одно фото скрипт не понял — весь набор в фолбэк."""
        totals = measure_photos([make_mouth_jpeg(), make_jpeg()])
        self.assertFalse(totals.ok)

    def test_measure_photos_aggregates(self):
        totals = measure_photos([make_mouth_jpeg(), make_mouth_jpeg()])
        self.assertTrue(totals.ok)
        self.assertAlmostEqual(totals.fresh_percent, 16.0, delta=6.0)

    def test_measured_block_mentions_numbers(self):
        block = build_measured_block(12.3, 4.5)
        self.assertIn('12.3%', block)
        self.assertIn('4.5%', block)


def upload_mouth(name='m.jpg', **kwargs):
    return SimpleUploadedFile(name, make_mouth_jpeg(**kwargs), content_type='image/jpeg')


class PlaqueCvIntegrationTests(TestCase):
    """Интеграция скрипта в POST /api/analysis/: настройки, кэш, оверлеи, фолбэк."""

    def setUp(self):
        SystemSettings.objects.create(key='prompt_text', value='BASE')
        SystemSettings.objects.create(key='prompt_permanent', value='PERMANENT')
        SystemSettings.objects.create(key='ai_provider', value='gemini')
        SystemSettings.objects.create(key='ai_model', value='gemini-2.5-flash')
        # cv_plaque_enabled не создаём: по умолчанию скрипт ВКЛЮЧЁН (default='true')
        self.user = User.objects.create_user(
            email='cv@example.com', name='CV', password='x', attempts_left=10,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.url = reverse('analysis-create')

    def _post(self, photo=None):
        return self.client.post(
            self.url,
            {'age_group': 'permanent_adult', 'photos': photo or upload_mouth()},
            format='multipart',
        )

    @patch('apps.analysis.views.ai_analyze', return_value=(FAKE_AI_RESULT, FAKE_AI_RAW))
    def test_cv_on_measures_and_saves_overlay(self, mock_ai):
        resp = self._post()
        self.assertEqual(resp.status_code, 201, resp.data)
        a = Analysis.objects.get()
        self.assertTrue(a.cv_measured)
        photo = a.photos.get()
        self.assertTrue(photo.overlay, 'оверлей с подсветкой должен сохраниться')
        # Промпт получил блок с измеренными цифрами, а сами цифры ушли kwargs-ом
        _, prompt_arg = mock_ai.call_args.args
        self.assertIn('ИЗМЕРЕННЫЕ ДАННЫЕ', prompt_arg)
        self.assertIn('PERMANENT', prompt_arg)
        self.assertIsNotNone(mock_ai.call_args.kwargs.get('measured'))

    def test_cv_on_overrides_model_percentages(self):
        """Даже если модель проигнорировала инструкцию и вернула свои проценты,
        сохраняются измеренные скриптом (и балл выводится из них)."""
        stubborn = dict(FAKE_AI_RESULT, fresh_plaque_percent=90, old_plaque_percent=5)
        with patch('apps.analysis.services.ai_router._dispatch',
                   return_value=(stubborn, FAKE_AI_RAW)):
            resp = self._post()
        self.assertEqual(resp.status_code, 201, resp.data)
        a = Analysis.objects.get()
        self.assertTrue(a.cv_measured)
        self.assertLess(a.fresh_plaque_percent, 30)     # ~16%, а не 90 от модели
        from apps.analysis.services.ai_router import derive_score
        self.assertEqual(a.score, derive_score(a.fresh_plaque_percent, a.old_plaque_percent))

    @patch('apps.analysis.views.ai_analyze', return_value=(FAKE_AI_RESULT, FAKE_AI_RAW))
    def test_cv_off_keeps_legacy_behaviour(self, mock_ai):
        SystemSettings.objects.create(key='cv_plaque_enabled', value='false')
        resp = self._post()
        self.assertEqual(resp.status_code, 201, resp.data)
        a = Analysis.objects.get()
        self.assertFalse(a.cv_measured)
        self.assertEqual(a.fresh_plaque_percent, 15)    # проценты модели как раньше
        self.assertFalse(a.photos.get().overlay)
        self.assertNotIn('ИЗМЕРЕННЫЕ ДАННЫЕ', mock_ai.call_args.args[1])
        self.assertIsNone(mock_ai.call_args.kwargs.get('measured'))

    @patch('apps.analysis.views.ai_analyze', return_value=(FAKE_AI_RESULT, FAKE_AI_RAW))
    def test_cv_fallback_when_teeth_not_found(self, mock_ai):
        """Скрипт включён, но фото без распознаваемых зубов → честный фолбэк на модель."""
        resp = self._post(photo=upload())               # однотонный jpeg
        self.assertEqual(resp.status_code, 201, resp.data)
        a = Analysis.objects.get()
        self.assertFalse(a.cv_measured)
        self.assertEqual(a.fresh_plaque_percent, 15)
        self.assertFalse(a.photos.get().overlay)

    @patch('apps.analysis.views.ai_analyze', return_value=(FAKE_AI_RESULT, FAKE_AI_RAW))
    def test_cache_not_shared_between_cv_modes(self, mock_ai):
        """Результат с оценёнными моделью процентами нельзя переиспользовать
        как измеренный: у режимов раздельный кэш (поле cv_measured)."""
        SystemSettings.objects.create(key='cv_plaque_enabled', value='false')
        blob = make_mouth_jpeg()
        self.client.post(self.url, {
            'age_group': 'permanent_adult',
            'photos': SimpleUploadedFile('p.jpg', blob, content_type='image/jpeg'),
        }, format='multipart')
        self.assertEqual(mock_ai.call_count, 1)

        SystemSettings.objects.filter(key='cv_plaque_enabled').update(value='true')
        resp = self.client.post(self.url, {
            'age_group': 'permanent_adult',
            'photos': SimpleUploadedFile('p.jpg', blob, content_type='image/jpeg'),
        }, format='multipart')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(mock_ai.call_count, 2, 'кэш выключенного режима не должен сработать')
        first, second = Analysis.objects.order_by('created_at')
        self.assertFalse(first.cv_measured)
        self.assertTrue(second.cv_measured)

    @patch('apps.analysis.views.ai_analyze', return_value=(FAKE_AI_RESULT, FAKE_AI_RAW))
    def test_cache_reused_within_cv_mode_and_overlay_still_saved(self, mock_ai):
        """Повторная загрузка тех же фото при включённом скрипте: ИИ не дёргаем
        (кэш), но оверлеи у НОВОЙ записи есть — скрипт детерминирован."""
        blob = make_mouth_jpeg()
        for _ in range(2):
            resp = self.client.post(self.url, {
                'age_group': 'permanent_adult',
                'photos': SimpleUploadedFile('p.jpg', blob, content_type='image/jpeg'),
            }, format='multipart')
            self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(mock_ai.call_count, 1, 'второй запрос должен взять кэш')
        second = Analysis.objects.order_by('created_at').last()
        self.assertTrue(second.cv_measured)
        self.assertTrue(second.photos.get().overlay)
        self.assertIn('cached', second.raw_response)

    @patch('apps.analysis.views.ai_analyze', return_value=(
        {'is_valid': False, 'score': None, 'fresh_plaque_percent': None,
         'old_plaque_percent': None, 'problem_zones': [], 'recommendations': []},
        '{"is_valid": false}',
    ))
    def test_model_invalid_verdict_wins_over_script(self, _):
        """Скрипт умеет считать пиксели, но валидность фото решает модель:
        если она сказала is_valid=false, баллов и процентов нет."""
        resp = self._post()
        self.assertEqual(resp.status_code, 201, resp.data)
        a = Analysis.objects.get()
        self.assertFalse(a.is_valid)
        self.assertIsNone(a.score)
        self.assertIsNone(a.fresh_plaque_percent)

    @patch('apps.analysis.views.ai_analyze', return_value=(FAKE_AI_RESULT, FAKE_AI_RAW))
    def test_photo_and_overlay_in_api_response(self, _):
        resp = self._post()
        photos = resp.data['photos']
        self.assertEqual(len(photos), 1)
        self.assertTrue(photos[0]['overlay'])
        self.assertTrue(resp.data['cv_measured'])


class AnalysisExportTests(TestCase):
    """Выгрузка анализов в CSV из админки и её ограничение по правам.

    Главному админу выгрузка доступна всегда; эксперту — только если ему выдано
    индивидуальное право analysis.export_analysis (в группу «Эксперт» оно не входит)."""

    def setUp(self):
        from apps.users.permissions_setup import ensure_expert_group
        self.changelist = reverse('admin:analysis_analysis_changelist')

        self.superadmin = User.objects.create_superuser(
            email='boss@raduga.ru', name='Главный', password='x')
        # Эксперт: staff + группа «Эксперт», но без права на выгрузку.
        self.expert = User.objects.create_user(
            email='exp@raduga.ru', name='Эксперт', password='x',
            role='expert', is_staff=True)
        self.expert.groups.add(ensure_expert_group())

        patient = User.objects.create_user(email='p@raduga.ru', name='Пётр', password='x')
        self.analysis = Analysis.objects.create(
            user=patient, kind='indicator', score=7.0,
            fresh_plaque_percent=15, old_plaque_percent=15,
            problem_zones=['резцы снизу'], recommendations=['чистить дважды'],
            note='сменил щётку', is_valid=True)

    def _grant_export(self, user):
        from apps.analysis.admin import EXPORT_PERM
        from django.contrib.auth.models import Permission
        perm = Permission.objects.get(
            content_type__app_label='analysis', codename='export_analysis')
        user.user_permissions.add(perm)
        # Сбрасываем кэш прав, чтобы has_perm увидел свежую выдачу.
        return User.objects.get(pk=user.pk)

    def _run_action(self, user):
        c = Client()
        c.force_login(user)
        return c.post(self.changelist, {
            'action': 'export_as_csv',
            '_selected_action': [str(self.analysis.pk)],
        })

    def test_export_permission_registered(self):
        from django.contrib.auth.models import Permission
        self.assertTrue(Permission.objects.filter(
            content_type__app_label='analysis', codename='export_analysis').exists())

    def test_export_not_in_expert_group(self):
        from apps.users.permissions_setup import ensure_expert_group
        codenames = set(ensure_expert_group().permissions.values_list('codename', flat=True))
        self.assertNotIn('export_analysis', codenames)

    def test_superadmin_gets_csv(self):
        resp = self._run_action(self.superadmin)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'text/csv; charset=utf-8')
        self.assertIn('attachment', resp['Content-Disposition'])
        body = resp.content.decode('utf-8-sig')  # -sig отрежет BOM
        self.assertTrue(resp.content.startswith(b'\xef\xbb\xbf'), 'нет BOM для Excel')
        self.assertIn('Заметка пользователя', body)   # заголовок
        self.assertIn('сменил щётку', body)            # значение note
        self.assertIn('резцы снизу', body)             # проблемные зоны
        self.assertIn(';', body)                       # разделитель «;»

    def test_expert_without_permission_cannot_export(self):
        # Без права экшна нет в списке → редирект назад на changelist без файла.
        resp = self._run_action(self.expert)
        self.assertNotEqual(resp.get('Content-Type'), 'text/csv; charset=utf-8')
        self.assertNotIn('attachment', resp.get('Content-Disposition', ''))

    def test_expert_with_permission_can_export(self):
        expert = self._grant_export(self.expert)
        resp = self._run_action(expert)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'text/csv; charset=utf-8')
        self.assertIn('сменил щётку', resp.content.decode('utf-8-sig'))

    def test_export_action_hidden_from_expert_without_permission(self):
        from django.contrib.admin.sites import AdminSite
        from django.test import RequestFactory
        from apps.analysis.admin import AnalysisAdmin
        admin_obj = AnalysisAdmin(Analysis, AdminSite())
        req = RequestFactory().get(self.changelist)
        req.user = self.expert
        self.assertNotIn('export_as_csv', admin_obj.get_actions(req))
        # А главному админу — доступен.
        req.user = self.superadmin
        self.assertIn('export_as_csv', admin_obj.get_actions(req))
