# inventory/reports.py
import io
from datetime import datetime
from pathlib import Path

import pandas as pd
from django.conf import settings
from django.utils.timezone import now

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader

from .models import Product, StockLog

# -----------------------------
# Data helpers
# -----------------------------
def _fetch_inventory_rows(filters=None):
    qs = Product.objects.all().order_by("name")
    if filters:
        category = filters.get("category")
        supplier = filters.get("supplier")
        if category:
            qs = qs.filter(category__iexact=category)
        if supplier:
            qs = qs.filter(supplier__iexact=supplier)
    rows = []
    for p in qs:
        rows.append({
            "id": str(p.id),
            "sku": p.sku or "",
            "name": p.name,
            "category": p.category or "",
            "quantity": int(p.quantity),
            "purchase_price": float(p.purchase_price),
            "selling_price": float(p.selling_price) if p.selling_price is not None else None,
            "total_value": float(p.purchase_price) * int(p.quantity),
            "supplier": p.supplier or "",
            "low_stock_threshold": int(p.low_stock_threshold or 0),
        })
    return rows

def _fetch_low_stock_rows():
    qs = Product.objects.filter(quantity__lte=Product._meta.get_field('low_stock_threshold').name and (Product.objects.none().query))  # placeholder to avoid lint errors
    # Better: use F expression so import here:
    from django.db.models import F
    qs = Product.objects.filter(quantity__lte=F('low_stock_threshold')).order_by("quantity")
    rows = []
    for p in qs:
        rows.append({
            "id": str(p.id),
            "sku": p.sku or "",
            "name": p.name,
            "category": p.category or "",
            "quantity": int(p.quantity),
            "low_stock_threshold": int(p.low_stock_threshold or 0),
            "purchase_price": float(p.purchase_price),
            "selling_price": float(p.selling_price) if p.selling_price is not None else None,
            "total_value": float(p.purchase_price) * int(p.quantity),
            "supplier": p.supplier or "",
        })
    return rows

def _fetch_stock_logs(from_date=None, to_date=None):
    qs = StockLog.objects.select_related("product", "user").order_by("-created_at")
    if from_date:
        qs = qs.filter(created_at__gte=from_date)
    if to_date:
        qs = qs.filter(created_at__lte=to_date)
    rows = []
    for l in qs:
        rows.append({
            "id": str(l.id),
            "product_id": str(l.product.id),
            "product_name": l.product.name,
            "user": l.user.username if l.user else None,
            "change_amount": l.change_amount,
            "resulting_quantity": l.resulting_quantity,
            "reason": l.reason,
            "reference": l.reference,
            "created_at": l.created_at.isoformat(),
        })
    return rows

# -----------------------------
# PDF helpers
# -----------------------------
def _get_styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Small", parent=styles["Normal"], fontSize=9))
    styles.add(ParagraphStyle(name="SmallBold", parent=styles["Normal"], fontSize=9, leading=11, spaceAfter=2))
    return styles

def _header_footer(canvas, doc):
    canvas.saveState()
    width, height = landscape(A4)

    # Header: shop name left
    shop_name = getattr(settings, "SHOP_NAME", "Inventory")
    canvas.setFont("Helvetica-Bold", 12)
    canvas.drawString(20 * mm, height - 15 * mm, shop_name)

    # Optional logo
    logo_path = getattr(settings, "SHOP_LOGO_PATH", None)
    try:
        if logo_path:
            img = ImageReader(str(logo_path))
            img_w, img_h = img.getSize()
            max_w = 30 * mm
            max_h = 12 * mm
            ratio = min(max_w / img_w, max_h / img_h, 1)
            w = img_w * ratio
            h = img_h * ratio
            canvas.drawImage(img, width - 20 * mm - w, height - 18 * mm - h / 2, width=w, height=h, preserveAspectRatio=True)
    except Exception:
        pass

    # Timestamp (right)
    canvas.setFont("Helvetica", 9)
    timestamp = now().strftime("%Y-%m-%d %H:%M:%S")
    canvas.drawRightString(width - 20 * mm, height - 15 * mm, f"Generated: {timestamp}")

    # Footer page number
    canvas.setFont("Helvetica", 8)
    page_num_text = f"Page {doc.page}"
    canvas.drawCentredString(width / 2.0, 10 * mm, page_num_text)

    canvas.restoreState()

def _build_pdf_from_table(data, col_widths=None, title="Report", highlight_rows=None, highlight_low=False):
    highlight_rows = set(highlight_rows or [])

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=15 * mm, rightMargin=15 * mm, topMargin=25 * mm, bottomMargin=20 * mm)
    styles = _get_styles()
    story = []
    story.append(Paragraph(title, styles["Title"]))
    story.append(Spacer(1, 6))

    table = Table(data, repeatRows=1, colWidths=col_widths)
    table_style = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#F2F2F2")),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
    ]

    for row_idx in range(1, len(data)):
        if highlight_low or (row_idx in highlight_rows):
            table_style.append(('BACKGROUND', (0, row_idx), (-1, row_idx), colors.HexColor("#FFEEEE")))
            table_style.append(('TEXTCOLOR', (0, row_idx), (-1, row_idx), colors.HexColor("#880000")))

    table.setStyle(TableStyle(table_style))
    story.append(table)

    doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
    buf.seek(0)
    return buf

# Expose functions used by tasks/views
__all__ = [
    "_fetch_inventory_rows",
    "_fetch_low_stock_rows",
    "_fetch_stock_logs",
    "_build_pdf_from_table",
]
