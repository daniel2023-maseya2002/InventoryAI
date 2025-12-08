# ai/urls.py
from django.urls import path
from .views import AiInventoryReportView

urlpatterns = [
    path("report/", AiInventoryReportView.as_view(), name="ai-inventory-report"),
]
