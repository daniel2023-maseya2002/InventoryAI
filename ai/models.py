import uuid
from django.db import models

class AIReport(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    REPORT_TYPES = (
        ("sales", "Sales"),
        ("stock", "Stock"),
        ("anomaly", "Anomaly"),
    )

    report_type = models.CharField(max_length=20, choices=REPORT_TYPES)
    raw = models.TextField()  # ✅ must NOT be null
    data = models.JSONField(default=dict)  # ✅ DEFAULT IS REQUIRED
    created_at = models.DateTimeField(auto_now_add=True)

    pdf = models.FileField(upload_to="ai_pdfs/", null=True, blank=True)

    def __str__(self):
        return f"{self.report_type} - {self.created_at}"

class AIAnomaly(models.Model):
    message = models.TextField()
    level = models.CharField(max_length=20, default="warning")  # warning, critical
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.message

class AIPrediction(models.Model):
    product = models.CharField(max_length=255)
    predicted_quantity = models.IntegerField()
    period = models.CharField(max_length=20)  # week, month
    created_at = models.DateTimeField(auto_now_add=True)
