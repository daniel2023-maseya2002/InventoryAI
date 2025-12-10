# ai/views.py
from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .services import generate_sales_ai_report
from rest_framework import generics, permissions
from .models import AIReport, AIAnomaly, AIPrediction
from .serializers import AIReportSerializer, AIPredictionSerializer, AIAnomalySerializer
from django.http import FileResponse, Http404



class AiInventoryReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        days = int(request.query_params.get("days", 30))
        report = generate_sales_ai_report(days)
        return Response(report)

class AdminAIReportListView(generics.ListAPIView):
    queryset = AIReport.objects.all().order_by("-created_at")
    serializer_class = AIReportSerializer
    permission_classes = [permissions.IsAdminUser]

class DownloadAIReportPDFView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request, pk):
        try:
            report = AIReport.objects.get(pk=pk)
            return FileResponse(report.pdf.open("rb"), as_attachment=True)
        except:
            raise Http404("PDF not found")

class AIAnomalyListView(generics.ListAPIView):
    queryset = AIAnomaly.objects.all().order_by("-created_at")
    serializer_class = AIAnomalySerializer
    permission_classes = [permissions.IsAdminUser]


class PredictionHistoryView(generics.ListAPIView):
    queryset = AIPrediction.objects.all().order_by("-created_at")
    serializer_class = AIPredictionSerializer
    permission_classes = [permissions.IsAdminUser]

