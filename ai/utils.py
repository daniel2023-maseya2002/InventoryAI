import json
import re
from datetime import datetime
from django.core.files.base import ContentFile
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from .models import AIReport
from django.core.mail import EmailMessage
from django.conf import settings
from typing import Any, Dict, Optional
import io
import logging

logger = logging.getLogger(__name__)

def extract_json_from_ai(text: str) -> dict:
    """
    Safely extract valid JSON from AI output even if wrapped in markdown.
    """

    try:
        # Remove ```json blocks if present
        text = re.sub(r"```json|```", "", text, flags=re.IGNORECASE).strip()
        return json.loads(text)
    except Exception:
        raise ValueError("AI response is not valid JSON")
    

def render_report_pdf(report_dict_or_text, title="AI Report"):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    margin = 40
    y = height - margin

    c.setFont("Helvetica-Bold", 14)
    c.drawString(margin, y, title)
    y -= 30

    c.setFont("Helvetica", 10)
    if isinstance(report_dict_or_text, dict):
        text = json.dumps(report_dict_or_text, indent=2)
    else:
        text = str(report_dict_or_text)

    for line in text.splitlines():
        c.drawString(margin, y, line)
        y -= 12
        if y < margin:
            c.showPage()
            y = height - margin

    c.save()
    buf.seek(0)

    filename = f"ai_report_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.pdf"
    return filename, buf.read()

def save_ai_report_local(
    report_type: str,
    raw_text: str,
    parsed: Optional[Dict[str, Any]] = None
) -> AIReport:
    """
    Persist AIReport to DB and return the created instance.
    This version GUARANTEES no NULL values hit the database.
    """

    parsed_field = parsed if parsed is not None else {}

    ar = AIReport.objects.create(
        report_type=report_type,
        raw=raw_text or "",    # ✅ NEVER NULL
        data=parsed_field,     # ✅ ✅ ✅ CORRECT FIELD NAME
    )

    logger.debug("Saved AIReport id=%s type=%s", ar.pk, report_type)
    return ar

def email_ai_report(report: AIReport):
    recipients = [a[1] for a in getattr(settings, "ADMINS", [])]

    if not recipients:
        return False

    subject = f"Daily AI Report - {report.created_at.date()}"
    body = "Attached is the latest AI inventory report."

    email = EmailMessage(
        subject=subject,
        body=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=recipients,
    )

    if report.pdf:
        report.pdf.open("rb")
        email.attach(report.pdf.name.split("/")[-1], report.pdf.read(), "application/pdf")
        report.pdf.close()

    email.send()
    return True

def send_low_stock_email(items):
    subject = "URGENT: Low Stock Alert"
    body = "Low stock detected:\n\n"

    for i in items:
        body += f"- {i['product']} (Stock: {i['stock']})\n"

    EmailMessage(
        subject,
        body,
        settings.DEFAULT_FROM_EMAIL,
        [settings.ADMINS[0][1]],
    ).send()