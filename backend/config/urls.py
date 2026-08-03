from django.contrib import admin
from django.urls import path, re_path, include
from django.conf import settings
from django.conf.urls.static import static
from apps.core.views import legal_document_view

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('apps.users.urls')),
    path('api/analysis/', include('apps.analysis.urls')),
    path('api/settings/', include('apps.core.urls')),
    # Правовые документы — динамика поверх старых статических URL.
    # Слаг строго из LegalDocument.SLUG_CHOICES, без точек.
    re_path(r'^docs/(?P<slug>[a-z][a-z0-9-]*)\.html$', legal_document_view, name='legal-doc'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
