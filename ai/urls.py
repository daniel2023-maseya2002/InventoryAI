# ai/urls.py
from django.urls import path
from .views import AiInventoryReportView, AdminAIReportListView, DownloadAIReportPDFView

urlpatterns = [
    path("report/", AiInventoryReportView.as_view(), name="ai-inventory-report"),
    path("reports/", AdminAIReportListView.as_view()),
    path("reports/<int:pk>/download/", DownloadAIReportPDFView.as_view()),

]
