# inventory/tasks.py
import os
import io
from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMessage
from django.contrib.auth import get_user_model
from django.utils.timezone import now
from django.urls import reverse

from .views import (  # import the report builders (they are pure functions/classes)
    _fetch_inventory_rows, _fetch_low_stock_rows, _fetch_stock_logs,
    _build_pdf_from_table
)
import pandas as pd

User = get_user_model()

REPORTS_DIR = settings.REPORTS_ROOT if hasattr(settings, "REPORTS_ROOT") else (settings.MEDIA_ROOT / "reports")

def _ensure_reports_dir():
    os.makedirs(REPORTS_DIR, exist_ok=True)
    return REPORTS_DIR

@shared_task(bind=True)
def generate_and_email_report(self, report_type, to_emails=None, params=None, email_subject=None, email_body=None, attach_types=("pdf","xlsx")):
    """
    report_type: "inventory" | "low_stock" | "stock_logs"
    params: dict for filters (e.g., category, supplier, from_date, to_date)
    to_emails: list of recipient emails
    attach_types: tuple of attachments to create and attach
    """
    try:
        params = params or {}
        _ensure_reports_dir()
        files_to_attach = []

        # INVENTORY
        if report_type == "inventory":
            rows = _fetch_inventory_rows(params)
            df = pd.DataFrame(rows)

            if "xlsx" in attach_types:
                xname = REPORTS_DIR / f"inventory_{now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                with pd.ExcelWriter(xname, engine="openpyxl") as writer:
                    df.to_excel(writer, index=False, sheet_name="Inventory")
                files_to_attach.append(str(xname))

            if "pdf" in attach_types:
                # build table for pdf
                data = [["SKU","Name","Category","Qty","Purchase Price","Selling Price","Total Value","Supplier","Low Threshold"]]
                for r in rows:
                    data.append([
                        r.get("sku",""), r.get("name",""), r.get("category",""), str(r.get("quantity","")),
                        f"{r.get('purchase_price',0):.2f}", f"{r.get('selling_price',0) if r.get('selling_price') is not None else ''}",
                        f"{r.get('total_value',0):.2f}", r.get("supplier",""), str(r.get("low_stock_threshold",""))
                    ])
                buf = _build_pdf_from_table(data, title="Inventory Report")
                path = REPORTS_DIR / f"inventory_{now().strftime('%Y%m%d_%H%M%S')}.pdf"
                with open(path, "wb") as f:
                    f.write(buf.getvalue())
                files_to_attach.append(str(path))

        # LOW STOCK
        elif report_type == "low_stock":
            rows = _fetch_low_stock_rows()
            df = pd.DataFrame(rows)
            if "xlsx" in attach_types:
                xname = REPORTS_DIR / f"lowstock_{now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                with pd.ExcelWriter(xname, engine="openpyxl") as writer:
                    df.to_excel(writer, index=False, sheet_name="LowStock")
                files_to_attach.append(str(xname))
            if "pdf" in attach_types:
                data = [["SKU","Name","Category","Qty","Low Threshold","Purchase Price","Selling Price","Total Value","Supplier"]]
                for r in rows:
                    data.append([
                        r.get("sku",""), r.get("name",""), r.get("category",""), str(r.get("quantity","")),
                        str(r.get("low_stock_threshold","")), f"{r.get('purchase_price',0):.2f}",
                        f"{r.get('selling_price',0) if r.get('selling_price') is not None else ''}",
                        f"{r.get('total_value',0):.2f}", r.get("supplier","")
                    ])
                buf = _build_pdf_from_table(data, title="Low Stock Report", highlight_low=True)
                path = REPORTS_DIR / f"lowstock_{now().strftime('%Y%m%d_%H%M%S')}.pdf"
                with open(path, "wb") as f:
                    f.write(buf.getvalue())
                files_to_attach.append(str(path))

        # STOCK LOGS
        elif report_type == "stock_logs":
            rows = _fetch_stock_logs(params.get("from_date"), params.get("to_date"))
            df = pd.DataFrame(rows)
            if "xlsx" in attach_types:
                xname = REPORTS_DIR / f"stocklogs_{now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                with pd.ExcelWriter(xname, engine="openpyxl") as writer:
                    df.to_excel(writer, index=False, sheet_name="StockLogs")
                files_to_attach.append(str(xname))
            if "pdf" in attach_types:
                data = [["Product","User","Change","Resulting Qty","Reason","Reference","Date"]]
                for r in rows:
                    data.append([
                        r.get("product_name",""), r.get("user","") or "", str(r.get("change_amount","")), str(r.get("resulting_quantity","")),
                        r.get("reason","") or "", r.get("reference","") or "", r.get("created_at","")
                    ])
                buf = _build_pdf_from_table(data, title="Stock Logs Report")
                path = REPORTS_DIR / f"stocklogs_{now().strftime('%Y%m%d_%H%M%S')}.pdf"
                with open(path, "wb") as f:
                    f.write(buf.getvalue())
                files_to_attach.append(str(path))

        # send email if requested
        if to_emails:
            subject = email_subject or f"{settings.SHOP_NAME} - {report_type.replace('_',' ').title()} Report"
            body = email_body or f"Attached is the requested {report_type} report generated at {now().isoformat()}."
            email = EmailMessage(subject, body, settings.DEFAULT_FROM_EMAIL, to_emails)
            for fpath in files_to_attach:
                email.attach_file(fpath)
            email.send(fail_silently=False)

        return {"status":"ok", "files": [str(x) for x in files_to_attach]}

    except Exception as e:
        # capture exception to task backend
        self.update_state(state='FAILURE', meta={'exc': str(e)})
        raise
