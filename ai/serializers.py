from rest_framework import serializers
from .models import AIReport, AIPrediction, AIAnomaly

class AIReportSerializer(serializers.ModelSerializer):
    pdf_url = serializers.SerializerMethodField()

    class Meta:
        model = AIReport
        fields = "__all__"

    def get_pdf_url(self, obj):
        if obj.pdf:
            return obj.pdf.url
        return None

# ✅ MISSING SERIALIZER → ADD THIS
class AIAnomalySerializer(serializers.ModelSerializer):
    class Meta:
        model = AIAnomaly
        fields = "__all__"


# ✅ Also needed for prediction history
class AIPredictionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIPrediction
        fields = "__all__"