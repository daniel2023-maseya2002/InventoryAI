# backend/ai/services.py
import json
import re
import time
import logging
from io import BytesIO
from typing import Any, Dict, Optional, List

import requests
from django.conf import settings
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.core.mail import EmailMessage
from django.db.models import Sum
from django.utils.timezone import now
from datetime import timedelta

from inventory.models import Product, Sale
from .models import AIReport  # ✅ FIELDS: report_type, raw, data, pdf, created_at
from .anomaly import detect_anomalies

logger = logging.getLogger(__name__)

# ============================
# ✅ CONFIG
# ============================
OLLAMA_URL = getattr(settings, "OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = getattr(settings, "OLLAMA_MODEL", "llama3")
OLLAMA_TIMEOUT = getattr(settings, "OLLAMA_TIMEOUT", 400)
OLLAMA_MAX_RETRIES = getattr(settings, "OLLAMA_MAX_RETRIES", 3)
OLLAMA_RETRY_BACKOFF = getattr(settings, "OLLAMA_RETRY_BACKOFF", 1.5)

AI_CACHE_SECONDS = getattr(settings, "AI_CACHE_SECONDS", 30)
AI_ADMIN_EMAILS = getattr(
    settings,
    "AI_ADMIN_EMAILS",
    [email for _, email in getattr(settings, "ADMINS", [])]
)

# ============================
# ✅ JSON EXTRACTION
# ============================
JSON_EXTRACTOR = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.IGNORECASE)
BRACE_JSON_FINDER = re.compile(r"\{[\s\S]*\}")


def _extract_json_from_text(text: str) -> Optional[str]:
    if not text:
        return None
    m = JSON_EXTRACTOR.search(text)
    if m:
        return m.group(1).strip()
    m2 = BRACE_JSON_FINDER.search(text)
    if m2:
        return m2.group(0)
    return None


def _safe_parse_ai_json(ai_text: str) -> Dict[str, Any]:
    try:
        parsed = json.loads(ai_text)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    candidate = _extract_json_from_text(ai_text)
    if candidate:
        try:
            return json.loads(candidate)
        except Exception:
            pass

    return {"raw_ai_output": ai_text, "error": "Failed to parse AI JSON"}

# ============================
# ✅ OLLAMA CALL
# ============================
def ollama_generate(prompt: str) -> str:
    payload = {"model": OLLAMA_MODEL, "prompt": prompt, "stream": False}

    for attempt in range(1, OLLAMA_MAX_RETRIES + 1):
        try:
            res = requests.post(OLLAMA_URL, json=payload, timeout=OLLAMA_TIMEOUT)
            res.raise_for_status()
            data = res.json()
            return data.get("response") or json.dumps(data)
        except Exception as exc:
            logger.warning("Ollama attempt %s failed: %s", attempt, exc)
            if attempt == OLLAMA_MAX_RETRIES:
                raise
            time.sleep(OLLAMA_RETRY_BACKOFF ** (attempt - 1))

# ============================
# ✅ FALLBACK HEURISTICS
# ============================
def _heuristic_sales_report(sales_data, stock_data):
    best = sorted(sales_data, key=lambda x: x["quantity_sold"], reverse=True)[:5]
    dead = [p for p in stock_data if p["stock"] <= 0]

    reorder = []
    for p in stock_data:
        if p["stock"] <= p["low_stock_threshold"]:
            reorder.append({"product": p["product"], "quantity": max(5, p["low_stock_threshold"] * 2)})

    return {
        "best_selling_products": best,
        "dead_stock_products": dead,
        "reorder_recommendations": reorder,
        "low_stock_warnings": reorder,
        "demand_forecast": {},
        "summary_insight": {"fallback": True}
    }

# ============================
# ✅ DB SAVE (FIXED)
# ============================
def save_ai_report_local(report_type: str, raw_text: str, data: Dict[str, Any]) -> AIReport:
    return AIReport.objects.create(
        report_type=report_type,
        raw=raw_text or "",
        data=data or {},
    )

# ============================
# ✅ EMAIL
# ============================
def email_ai_report_local(report: AIReport):
    if not AI_ADMIN_EMAILS:
        return

    subject = f"[Inventory AI] {report.report_type.upper()} Report"
    body = json.dumps(report.data, indent=2)[:3000]

    email = EmailMessage(subject, body, settings.DEFAULT_FROM_EMAIL, AI_ADMIN_EMAILS)

    if report.pdf:
        try:
            report.pdf.open("rb")
            email.attach(report.pdf.name, report.pdf.read(), "application/pdf")
            report.pdf.close()
        except Exception:
            logger.exception("Failed to attach PDF")

    email.send(fail_silently=True)

# ============================
# ✅ PDF GENERATOR
# ============================
def generate_pdf_for_report(report: AIReport) -> AIReport:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)

    y = 800
    c.drawString(40, y, f"AI Report: {report.report_type}")
    y -= 30

    for line in json.dumps(report.data, indent=2).splitlines():
        if y < 50:
            c.showPage()
            y = 800
        c.drawString(40, y, line[:90])
        y -= 12

    c.showPage()
    c.save()

    filename = f"ai_report_{int(time.time())}.pdf"
    report.pdf.save(filename, ContentFile(buf.getvalue()))
    return report

# ============================
# ✅ CHART DATA
# ============================
def get_sales_chart_data(days=30):
    since = now() - timedelta(days=days)
    qs = Sale.objects.filter(created_at__gte=since).values("product__name").annotate(total=Sum("quantity"))
    return [{"product": x["product__name"], "quantity": x["total"]} for x in qs]

# ============================
# ✅ HISTORY
# ============================
def get_prediction_history(limit=50):
    qs = AIReport.objects.order_by("-created_at")[:limit]
    return [{"id": r.id, "created_at": r.created_at, "data": r.data} for r in qs]

# ============================
# ✅ MAIN AI ENTRYPOINT
# ============================
def generate_sales_ai_report(days=30, use_cache=True):
    cache_key = f"sales_ai:{days}"
    if use_cache and cache.get(cache_key):
        return cache.get(cache_key)

    since = now() - timedelta(days=days)

    sales_qs = Sale.objects.filter(created_at__gte=since).values("product__name").annotate(total_qty=Sum("quantity"))
    sales_data = [{"product": s["product__name"], "quantity_sold": int(s["total_qty"])} for s in sales_qs]

    stock_data = [{"product": p.name, "stock": p.quantity, "low_stock_threshold": p.low_stock_threshold} for p in Product.objects.all()]

    anomalies = detect_anomalies()

    prompt = f"""
Sales:
{json.dumps(sales_data)}

Stock:
{json.dumps(stock_data)}

Anomalies:
{json.dumps(anomalies)}

Return strict JSON only.
"""

    try:
        raw = ollama_generate(prompt)
        parsed = _safe_parse_ai_json(raw)

    except Exception:
        parsed = _heuristic_sales_report(sales_data, stock_data)
        raw = json.dumps(parsed)

    report = save_ai_report_local("sales", raw, parsed)
    generate_pdf_for_report(report)
    email_ai_report_local(report)

    cache.set(cache_key, parsed, AI_CACHE_SECONDS)
    return parsed

# ============================
# ✅ CELERY DAILY TASK
# ============================
try:
    from celery import shared_task

    @shared_task
    def daily_sales_ai_task():
        generate_sales_ai_report(days=30, use_cache=False)

except Exception:
    pass
