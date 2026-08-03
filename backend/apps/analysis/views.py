import hashlib
import logging
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import MultiPartParser
from django.core.files.base import ContentFile
from django.utils import timezone

from apps.core.models import SystemSettings
from .models import (
    Analysis, AnalysisPhoto, CONSENT_TEXT_VERSION,
    KIND_INDICATOR, KIND_EXPRESS,
)
from .serializers import (
    AnalysisSerializer,
    AnalysisCreateSerializer,
    UNDERAGE_GROUPS,
    MAX_PHOTOS,
    MAX_EXPRESS_PHOTOS,
)
from .services.photo import process_photo
from .services.plaque_cv import measure_photos, build_measured_block
from .services.ai_router import (
    analyze as ai_analyze,
    analyze_express as ai_analyze_express,
    get_prompt_for_age_group,
    build_history_context,
    derive_score,
    resolve_ai_target,
)
from .dynamics import build_dynamics

logger = logging.getLogger(__name__)


def _get_client_ip(request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if xff:
        return xff.split(',')[0].strip()[:45]
    return (request.META.get('REMOTE_ADDR') or '')[:45]


def _compute_photos_hash(photo_files):
    """sha256 от набора загруженных фото, инвариантный к порядку файлов.

    Для каждого файла берём sha256 сырых байт, сортируем список хэшей, склеиваем
    и берём sha256 от склейки. Указатель файла возвращаем в начало — дальше байты
    читает process_photo. Итог — 64-символьная hex-строка."""
    per_file = []
    for f in photo_files:
        f.seek(0)
        data = f.read()
        f.seek(0)
        per_file.append(hashlib.sha256(data).hexdigest())
    joined = ''.join(sorted(per_file))
    return hashlib.sha256(joined.encode('utf-8')).hexdigest()


def _survey_prompt(user):
    """Решаем, показывать ли карточку с анкетой после анализа.

    Условия (по требованию заказчика):
    - ссылка на анкету задана в настройках;
    - пользователь ещё не проходил текущую версию анкеты;
    - срабатывает раз в 3 анализа (на 3-м, 6-м, 9-м… анализе пользователя).
    Возвращает (show: bool, url: str)."""
    url = (SystemSettings.get('survey_url', default='') or '').strip()
    if not url:
        return False, ''
    if user.survey_completed_version >= SystemSettings.survey_version():
        return False, url
    count = Analysis.objects.filter(user=user).count()
    show = count > 0 and count % 3 == 0
    return show, url


def _calculate_dynamics(user, current_analysis):
    prev = (
        Analysis.objects
        .filter(user=user, is_valid=True)
        .exclude(pk=current_analysis.pk)
        .order_by('-created_at')
        .first()
    )
    if not prev or prev.score is None:
        return ''
    diff = round((current_analysis.score or 0) - prev.score, 1)
    date_str = prev.created_at.strftime('%d.%m.%Y')
    if diff > 0:
        return f'Улучшение: +{diff} балла по сравнению с анализом от {date_str}'
    elif diff < 0:
        return f'Ухудшение: {diff} балла по сравнению с анализом от {date_str}'
    return f'Результат не изменился по сравнению с анализом от {date_str}'


class AnalysisCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser]

    def post(self, request):
        user = request.user

        if user.attempts_left <= 0:
            return Response(
                {'detail': 'Недостаточно попыток для анализа'},
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )

        serializer = AnalysisCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        age_group = serializer.validated_data['age_group']
        legal_rep_consent = serializer.validated_data.get('legal_rep_consent', False)
        note = serializer.validated_data.get('note', '').strip()

        # Вычисляем промт и его хэш как можно раньше: хэш промта входит в ключ кэша
        # и записывается в Analysis при создании. Хэшируем только базовый промт
        # (без history_context) — иначе кэш никогда не сработает, так как
        # history_context меняется после каждого нового анализа.
        base_prompt = get_prompt_for_age_group(age_group)
        prompt_hash = hashlib.sha256(base_prompt.encode('utf-8')).hexdigest()

        photo_files = request.FILES.getlist('photos')
        if not photo_files:
            single = request.FILES.get('photo')
            if single:
                photo_files = [single]
        if not photo_files:
            return Response({'photos': 'Прикрепите хотя бы одно фото'}, status=status.HTTP_400_BAD_REQUEST)
        if len(photo_files) > MAX_PHOTOS:
            return Response(
                {'photos': f'Не более {MAX_PHOTOS} фотографий за один анализ'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Хэш набора фото считаем ДО process_photo (по сырым байтам загрузки),
        # process_photo читает файлы дальше — указатель уже возвращён в _compute_photos_hash.
        photos_hash = _compute_photos_hash(photo_files)

        try:
            clean_blobs = [process_photo(f) for f in photo_files]
        except Exception as e:
            logger.error('Photo processing error for user_id=%s: %s', user.id, e)
            return Response({'detail': 'Ошибка обработки фото'}, status=status.HTTP_400_BAD_REQUEST)

        # CV-скрипт: детерминированно меряет проценты налёта по пикселям красителя.
        # Выключен в настройках или не нашёл зубы (totals.ok=False) — работаем
        # по-старому, проценты оценит нейросеть. Запускается и при кэш-хите:
        # оверлеи с подсветкой принадлежат СВОИМ записям фото, а скрипт
        # детерминирован — цифры совпадут с закэшированными.
        cv_enabled = (SystemSettings.get('cv_plaque_enabled', default='true') or '').strip().lower() == 'true'
        totals = measure_photos(clean_blobs) if cv_enabled else None
        cv_ok = bool(totals and totals.ok)
        if cv_enabled and not cv_ok:
            logger.info('plaque_cv: зубы не найдены, фолбэк на оценку нейросетью (user_id=%s)', user.id)

        is_underage = age_group in UNDERAGE_GROUPS
        analysis = Analysis.objects.create(
            user=user,
            kind=KIND_INDICATOR,
            age_group=age_group,
            photos_hash=photos_hash,
            prompt_hash=prompt_hash,
            cv_measured=cv_ok,
            note=note,
            legal_rep_consent=bool(legal_rep_consent) if is_underage else False,
            consent_ip=_get_client_ip(request) if is_underage else '',
            consent_datetime=timezone.now() if is_underage else None,
            consent_text_version=CONSENT_TEXT_VERSION if is_underage else '',
        )

        photo_objects = []
        for idx, blob in enumerate(clean_blobs):
            p = AnalysisPhoto(analysis=analysis, order=idx)
            p.photo.save(
                f'analysis_{analysis.id}_photo_{idx}.jpg',
                ContentFile(blob),
                save=False,
            )
            overlay = totals.measurements[idx].overlay_jpeg if cv_ok else None
            if overlay:
                p.overlay.save(
                    f'analysis_{analysis.id}_overlay_{idx}.jpg',
                    ContentFile(overlay),
                    save=False,
                )
            p.save()
            photo_objects.append(p)

        # Дублируем первое фото в legacy поле photo_url для совместимости с админкой / историей
        analysis.photo_url.save(
            f'analysis_{analysis.id}_legacy.jpg',
            ContentFile(clean_blobs[0]),
            save=True,
        )

        provider, ai_model = resolve_ai_target(express=False)

        # Кэш по хэшу фото + версии промта: если этот же пользователь уже анализировал
        # точно те же фото в той же возрастной группе с тем же промтом и получил реальный
        # результат (raw_response != ''), переиспользуем его — не дёргаем ИИ, чтобы один
        # и тот же ввод давал один и тот же результат (фикс «разные оценки на одно фото»).
        # kind в фильтре обязателен: то же самое фото могло пройти экспресс-оценку,
        # и её результат (без цифр) нельзя переиспользовать для полного анализа.
        # cv_measured тоже обязателен: проценты, оценённые моделью при выключенном
        # скрипте, нельзя выдавать за измеренные (и наоборот).
        cached = (
            Analysis.objects
            .filter(user=user, kind=KIND_INDICATOR, photos_hash=photos_hash,
                    age_group=age_group, prompt_hash=prompt_hash, cv_measured=cv_ok)
            .exclude(pk=analysis.pk)
            .exclude(raw_response='')
            .order_by('-created_at')
            .first()
        )

        if cached is not None:
            logger.info(
                'Cache hit: analysis_id=%s reuses analysis_id=%s user_id=%s hash=%s',
                analysis.id, cached.id, user.id, photos_hash,
            )
            is_valid = cached.is_valid
            analysis.fresh_plaque_percent = cached.fresh_plaque_percent
            analysis.old_plaque_percent = cached.old_plaque_percent
            # Балл пересчитываем из процентов налёта — так даже закэшированный
            # (в т.ч. старый, до фикса) результат получает детерминированный балл.
            analysis.score = (
                derive_score(cached.fresh_plaque_percent, cached.old_plaque_percent)
                if is_valid else cached.score
            )
            analysis.problem_zones = cached.problem_zones
            analysis.recommendations = cached.recommendations
            analysis.ai_model = cached.ai_model
            analysis.raw_response = f'[cached from analysis {cached.id}: identical photos]'
            analysis.is_valid = is_valid
        else:
            history_context = build_history_context(user)
            measured_block = (
                build_measured_block(totals.fresh_percent, totals.old_percent)
                if cv_ok else ''
            )
            prompt = history_context + measured_block + base_prompt

            try:
                result, raw_response = ai_analyze(
                    clean_blobs, prompt,
                    measured=(totals.fresh_percent, totals.old_percent) if cv_ok else None,
                )
            except Exception as e:
                logger.error('AI error for user_id=%s analysis_id=%s: %s', user.id, analysis.id, e)
                analysis.delete()
                return Response({'detail': 'Ошибка ИИ-анализа, попытка не списана'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

            is_valid = result.get('is_valid', True)
            analysis.score = result.get('score')
            analysis.fresh_plaque_percent = result.get('fresh_plaque_percent')
            analysis.old_plaque_percent = result.get('old_plaque_percent')
            analysis.problem_zones = result.get('problem_zones', [])
            analysis.recommendations = result.get('recommendations', [])
            # Для qwen ai_model уже в формате 'qwen/<slug>' — не дублируем префикс провайдера.
            analysis.ai_model = ai_model if '/' in ai_model else f'{provider}/{ai_model}'
            analysis.raw_response = raw_response
            analysis.is_valid = is_valid

        if is_valid and analysis.score is not None:
            analysis.dynamics_text = _calculate_dynamics(user, analysis)

        analysis.save()

        user.attempts_left = max(0, user.attempts_left - 1)
        user.save(update_fields=['attempts_left'])
        analysis.attempt_deducted = True
        analysis.save(update_fields=['attempt_deducted'])

        logger.info(
            'Analysis created: id=%s user_id=%s group=%s photos=%d is_valid=%s',
            analysis.id, user.id, age_group, len(clean_blobs), is_valid,
        )

        data = AnalysisSerializer(analysis).data
        show_survey, survey_url = _survey_prompt(user)
        data['show_survey'] = show_survey
        data['survey_url'] = survey_url
        return Response(data, status=status.HTTP_201_CREATED)


class ExpressCreateView(APIView):
    """POST /api/analysis/express/ — экспресс-оценка по ОДНОМУ фото без индикатора.

    Отличия от полного анализа, все намеренные:
    - тратит СВОЙ счётчик (express_attempts_left), баланс анализов с индикатором не трогает;
    - не выставляет ни балла, ни процентов налёта — без окрашивания их неоткуда взять,
      а выдуманные числа хуже, чем их отсутствие (см. analyze_express);
    - не участвует в динамике и не подмешивается в историю для ИИ.

    Возрастная группа и согласие законного представителя спрашиваются так же, как в полном
    анализе: режим быстрый, но фото ребёнка остаётся персональными данными (152-ФЗ).
    """
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser]

    def post(self, request):
        user = request.user

        if user.express_attempts_left <= 0:
            return Response(
                {'detail': 'Бесплатные экспресс-оценки закончились'},
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )

        serializer = AnalysisCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        age_group = serializer.validated_data['age_group']
        legal_rep_consent = serializer.validated_data.get('legal_rep_consent', False)
        note = serializer.validated_data.get('note', '').strip()

        base_prompt = SystemSettings.get('prompt_express', default='')
        if not base_prompt:
            logger.error('prompt_express не задан в настройках — экспресс-оценка недоступна')
            return Response(
                {'detail': 'Экспресс-оценка временно недоступна'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        prompt_hash = hashlib.sha256(base_prompt.encode('utf-8')).hexdigest()

        photo_files = request.FILES.getlist('photos')
        if not photo_files:
            single = request.FILES.get('photo')
            if single:
                photo_files = [single]
        if not photo_files:
            return Response({'photos': 'Прикрепите фото'}, status=status.HTTP_400_BAD_REQUEST)
        if len(photo_files) > MAX_EXPRESS_PHOTOS:
            return Response(
                {'photos': 'Для экспресс-оценки нужно одно фото'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        photos_hash = _compute_photos_hash(photo_files)

        try:
            clean_blobs = [process_photo(f) for f in photo_files]
        except Exception as e:
            logger.error('Photo processing error (express) for user_id=%s: %s', user.id, e)
            return Response({'detail': 'Ошибка обработки фото'}, status=status.HTTP_400_BAD_REQUEST)

        is_underage = age_group in UNDERAGE_GROUPS
        analysis = Analysis.objects.create(
            user=user,
            kind=KIND_EXPRESS,
            age_group=age_group,
            photos_hash=photos_hash,
            prompt_hash=prompt_hash,
            note=note,
            legal_rep_consent=bool(legal_rep_consent) if is_underage else False,
            consent_ip=_get_client_ip(request) if is_underage else '',
            consent_datetime=timezone.now() if is_underage else None,
            consent_text_version=CONSENT_TEXT_VERSION if is_underage else '',
        )

        for idx, blob in enumerate(clean_blobs):
            p = AnalysisPhoto(analysis=analysis, order=idx)
            p.photo.save(f'express_{analysis.id}_photo_{idx}.jpg', ContentFile(blob), save=True)

        analysis.photo_url.save(
            f'express_{analysis.id}_legacy.jpg',
            ContentFile(clean_blobs[0]),
            save=True,
        )

        # У экспресса может быть своя сеть/модель (настройки ai_*_express) — берём
        # именно её, иначе в карточке анализа окажется модель основного анализа.
        provider, ai_model = resolve_ai_target(express=True)

        cached = (
            Analysis.objects
            .filter(user=user, kind=KIND_EXPRESS, photos_hash=photos_hash,
                    age_group=age_group, prompt_hash=prompt_hash)
            .exclude(pk=analysis.pk)
            .exclude(raw_response='')
            .order_by('-created_at')
            .first()
        )

        if cached is not None:
            logger.info(
                'Express cache hit: analysis_id=%s reuses analysis_id=%s user_id=%s',
                analysis.id, cached.id, user.id,
            )
            analysis.observations = cached.observations
            analysis.recommendations = cached.recommendations
            analysis.ai_model = cached.ai_model
            analysis.raw_response = f'[cached from analysis {cached.id}: identical photo]'
            analysis.is_valid = cached.is_valid
        else:
            group_hint = ''
            if age_group:
                group_hint = f'ВОЗРАСТНАЯ ГРУППА ПАЦИЕНТА: {analysis.get_age_group_display()}\n\n'

            try:
                result, raw_response = ai_analyze_express(clean_blobs, group_hint + base_prompt)
            except Exception as e:
                logger.error('AI error (express) for user_id=%s analysis_id=%s: %s', user.id, analysis.id, e)
                analysis.delete()
                return Response(
                    {'detail': 'Ошибка ИИ-анализа, попытка не списана'},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )

            analysis.observations = result['observations']
            analysis.recommendations = result['recommendations']
            analysis.ai_model = ai_model if '/' in ai_model else f'{provider}/{ai_model}'
            analysis.raw_response = raw_response
            analysis.is_valid = result['is_valid']

        analysis.save()

        user.express_attempts_left = max(0, user.express_attempts_left - 1)
        user.save(update_fields=['express_attempts_left'])
        analysis.attempt_deducted = True
        analysis.save(update_fields=['attempt_deducted'])

        logger.info(
            'Express created: id=%s user_id=%s group=%s is_valid=%s',
            analysis.id, user.id, age_group, analysis.is_valid,
        )

        data = AnalysisSerializer(analysis).data
        show_survey, survey_url = _survey_prompt(user)
        data['show_survey'] = show_survey
        data['survey_url'] = survey_url
        return Response(data, status=status.HTTP_201_CREATED)


class AnalysisListPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 50


class AnalysisListView(generics.ListAPIView):
    serializer_class = AnalysisSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = AnalysisListPagination

    def get_queryset(self):
        qs = Analysis.objects.filter(user=self.request.user).order_by('-created_at')
        if self.request.query_params.get('valid_only') == 'true':
            qs = qs.filter(is_valid=True)
        # История общая (оба режима вперемешку, с пометкой типа у записи), но при
        # необходимости её можно сузить: ?kind=express или ?kind=indicator.
        kind = self.request.query_params.get('kind')
        if kind in (KIND_INDICATOR, KIND_EXPRESS):
            qs = qs.filter(kind=kind)
        return qs


class AnalysisDetailView(generics.RetrieveAPIView):
    serializer_class = AnalysisSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Analysis.objects.filter(user=self.request.user)


class AnalysisDynamicsView(APIView):
    """GET /api/analysis/dynamics/ — динамика оценок гигиены пользователя
    (точки для графика + сводка). Данные строит общий модуль dynamics,
    тот же что и админка, чтобы цифры в ЛК и в админке совпадали."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(build_dynamics(request.user))
