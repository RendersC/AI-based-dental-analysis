from django.urls import path
from .views import (
    AnalysisCreateView,
    ExpressCreateView,
    AnalysisListView,
    AnalysisDetailView,
    AnalysisDynamicsView,
)

urlpatterns = [
    path('', AnalysisListView.as_view(), name='analysis-list'),
    path('create/', AnalysisCreateView.as_view(), name='analysis-create'),
    path('express/', ExpressCreateView.as_view(), name='analysis-express'),
    # dynamics/ объявлен ДО <int:pk>/, иначе 'dynamics' попадёт в pk-маршрут.
    path('dynamics/', AnalysisDynamicsView.as_view(), name='analysis-dynamics'),
    path('<int:pk>/', AnalysisDetailView.as_view(), name='analysis-detail'),
]
