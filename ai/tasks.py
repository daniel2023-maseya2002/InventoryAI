from celery import shared_task
from .services import generate_sales_ai_report
from .utils import save_ai_report, email_ai_report
import json


@shared_task
def generate_daily_ai_report():
    generate_sales_ai_report(days=30)

@shared_task
def daily_ai_sales_report():
    result = generate_sales_ai_report(days=30)

    raw = json.dumps(result)
    report = save_ai_report("sales", raw, result)
    email_ai_report(report)

    return {"status": "sent", "report_id": report.id}