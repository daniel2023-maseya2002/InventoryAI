# ai/views.py
from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .reports import generate_inventory_ai_report


class AiInventoryReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        report = generate_inventory_ai_report()
        return Response({
            "generated_at": str(report and "now"),
            "ai_report": report
        })
