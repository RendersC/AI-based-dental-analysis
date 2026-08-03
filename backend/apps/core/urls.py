from django.urls import path
from .views import SystemSettingsView, InstructionView, OfficialDocumentsView

urlpatterns = [
    path('', SystemSettingsView.as_view(), name='settings'),
    path('instruction/', InstructionView.as_view(), name='instruction'),
    path('official-documents/', OfficialDocumentsView.as_view(), name='official-documents'),
]
