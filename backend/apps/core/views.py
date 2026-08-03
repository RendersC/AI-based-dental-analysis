from django.http import HttpResponse, HttpResponseNotFound, HttpResponseRedirect
from django.utils.html import escape
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Instruction, SystemSettings, LegalDocument, OfficialDocument
from .serializers import SystemSettingsSerializer, OfficialDocumentSerializer
from apps.analysis.services.gemini import AVAILABLE_MODELS as GEMINI_MODELS
from apps.analysis.services.qwen import AVAILABLE_MODELS as QWEN_MODELS


# Минимальный HTML-шаблон в едином стиле сервиса. Используется когда у документа
# заполнен только text_html (а PDF не загружен). text_html встраивается как есть
# без экранирования — админ контролирует ввод, но без <script> по политике.
_LEGAL_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title} — Радуга Улыбок</title>
  <style>
    *,*::before,*::after{{box-sizing:border-box}}
    body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Inter,system-ui,sans-serif;color:#1a2230;background:#f7f9fb;margin:0;padding:24px;line-height:1.55}}
    main{{max-width:760px;margin:0 auto;background:#fff;border:1px solid #E2E8F0;border-radius:12px;padding:32px}}
    h1{{font-size:24px;margin:0 0 8px;color:#00548d;font-weight:700}}
    .sub{{font-size:13px;color:#6E7785;margin:0 0 20px}}
    .ph{{background:linear-gradient(90deg,#f4f8fb 0%,#fff3ef 100%);border-left:4px solid #00548d;padding:14px 16px;border-radius:8px;margin:20px 0;color:#3A3A3A;font-size:14px}}
    .ph strong{{color:#00548d}}
    h2{{font-size:16px;margin:24px 0 8px;color:#1a2230}}
    p{{font-size:14px;color:#3A3A3A}}
    a{{color:#00548d;text-decoration:none}}
    a:hover{{text-decoration:underline}}
    footer{{margin-top:28px;padding-top:16px;border-top:1px solid #E2E8F0;font-size:12px;color:#6E7785;text-align:center}}
  </style>
</head>
<body>
  <main>
    <h1>{title}</h1>
    <p class="sub">Сервис «Радуга Улыбок» · радугаулыбок-dent.ru</p>
    {body}
    <footer>© Радуга Улыбок · обновлено {updated_at}</footer>
  </main>
</body>
</html>"""

_PLACEHOLDER_BODY = (
    '<div class="ph"><strong>Документ в подготовке.</strong> '
    'Финальный текст готовит юридическая команда. По вопросам — '
    '<a href="mailto:support@radugaulybok-dent.ru">support@radugaulybok-dent.ru</a>.</div>'
)


def legal_document_view(request, slug):
    """GET /docs/<slug>.html — отдаёт PDF (302) если загружен, иначе HTML-страницу
    с text_html, иначе плейсхолдер. Публичный эндпоинт без авторизации."""
    valid = {s for s, _ in LegalDocument.SLUG_CHOICES}
    if slug not in valid:
        return HttpResponseNotFound('Документ не найден')

    doc = LegalDocument.objects.filter(slug=slug).first()

    # Если есть PDF — редирект на media URL, браузер откроет его нативно
    if doc and doc.pdf:
        return HttpResponseRedirect(doc.pdf.url)

    title = doc.title if doc else dict(LegalDocument.SLUG_CHOICES).get(slug, slug)
    body = (doc.text_html if doc and doc.text_html.strip() else _PLACEHOLDER_BODY)
    updated_at = doc.updated_at.strftime('%d.%m.%Y') if doc else '—'

    html = _LEGAL_PAGE_TEMPLATE.format(title=escape(title), body=body, updated_at=updated_at)
    return HttpResponse(html, content_type='text/html; charset=utf-8')


class InstructionView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        obj = Instruction.get_current()
        if not obj or not obj.pdf:
            return Response({'url': None}, status=status.HTTP_200_OK)
        # Имя файла всегда одно (instruction/instruction.pdf), поэтому URL без
        # версии не меняется при замене PDF — браузер показывает старый из кеша.
        # Добавляем ?v=<метка времени обновления>: при каждой загрузке нового
        # файла updated_at (auto_now) меняется, ссылка становится новой,
        # браузер тянет свежий PDF.
        url = request.build_absolute_uri(obj.pdf.url)
        url = f"{url}?v={int(obj.updated_at.timestamp())}"
        return Response({
            'url': url,
            'updated_at': obj.updated_at,
        })


class OfficialDocumentsView(APIView):
    """GET /api/settings/official-documents/ — список сканов для блока
    «Официальный статус проекта» на лендинге. Публичный: лендинг открыт всем,
    авторизации на нём нет. Скрытые галочкой и записи без файла не отдаются."""

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        qs = OfficialDocument.objects.filter(is_visible=True).exclude(image='')
        data = OfficialDocumentSerializer(qs, many=True, context={'request': request}).data
        return Response({'results': data})


class IsAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'admin'


class SystemSettingsView(APIView):

    def get_permissions(self):
        if self.request.method == 'GET':
            return [permissions.AllowAny()]
        return [IsAdmin()]

    def get(self, request):
        # Public: initial_attempts + ID счётчика Яндекс.Метрики (нужен фронту до
        # авторизации, чтобы поднять аналитику после согласия на cookie).
        if not (request.user.is_authenticated and request.user.role == 'admin'):
            return Response({
                'initial_attempts': SystemSettings.get('initial_attempts', default='3'),
                'yandex_metrika_id': SystemSettings.get('yandex_metrika_id', default=''),
                # Ссылка на анкету — нужна фронту для кнопки в личном кабинете
                # и карточки после анализа. Пусто = анкета скрыта.
                'survey_url': SystemSettings.get('survey_url', default=''),
            })

        # Admin: all settings + available models list
        settings_qs = SystemSettings.objects.all()
        data = {s.key: s.value for s in settings_qs}
        data['available_gemini_models'] = GEMINI_MODELS
        data['available_qwen_models'] = QWEN_MODELS
        data['available_providers'] = ['gemini', 'qwen']
        return Response(data)

    def patch(self, request):
        allowed_keys = {'initial_attempts', 'initial_express_attempts',
                        'prompt_text', 'prompt_express', 'ai_provider', 'ai_model',
                        'ai_provider_express', 'ai_model_express', 'cv_plaque_enabled',
                        'yandex_metrika_id', 'survey_url', 'survey_version'}
        updated = {}
        for key, value in request.data.items():
            if key not in allowed_keys:
                continue
            obj, _ = SystemSettings.objects.get_or_create(key=key, defaults={'value': str(value)})
            obj.value = str(value)
            obj.save()
            updated[key] = obj.value
        return Response(updated)
