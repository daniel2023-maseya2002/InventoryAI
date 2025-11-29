# inventory/views.py
import io
import pandas as pd
from datetime import datetime

from django.shortcuts import get_object_or_404
from django.db import models as djmodels
from django.db.models import Q
from django.contrib.auth import get_user_model
from django.conf import settings
from django.utils.timezone import now
from django.http import StreamingHttpResponse

from rest_framework import viewsets, status, parsers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticatedOrReadOnly, IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

# ReportLab imports
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader

from .models import Product, StockLog, Notification
from .serializers import ProductSerializer, StockLogSerializer, NotificationSerializer
from .permissions import IsAdminOrStaffWrite
from .utils import create_notification

User = get_user_model()


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
    qs = Product.objects.filter(quantity__lte=djmodels.F('low_stock_threshold')).order_by("quantity")
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

    # Header
    shop_name = getattr(settings, "SHOP_NAME", "Inventory")
    canvas.setFont("Helvetica-Bold", 12)
    canvas.drawString(20 * mm, height - 15 * mm, shop_name)

    # Optional logo (if configured)
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

    # Footer: page number centered
    canvas.setFont("Helvetica", 8)
    page_num_text = f"Page {doc.page}"
    canvas.drawCentredString(width / 2.0, 10 * mm, page_num_text)

    canvas.restoreState()


def _build_pdf_from_table(data, col_widths=None, title="Report"):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=15 * mm, rightMargin=15 * mm, topMargin=25 * mm, bottomMargin=20 * mm)
    styles = _get_styles()
    story = []
    story.append(Paragraph(title, styles["Title"]))
    story.append(Spacer(1, 6))

    table = Table(data, repeatRows=1, colWidths=col_widths)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#F2F2F2")),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
    ]))
    story.append(table)

    doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
    buf.seek(0)
    return buf


# -----------------------------
# ViewSets
# -----------------------------
class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all().order_by("-updated_at")
    serializer_class = ProductSerializer
    permission_classes = [IsAdminOrStaffWrite]
    parser_classes = [parsers.JSONParser, MultiPartParser, FormParser]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["category", "supplier"]
    search_fields = ["name", "sku", "barcode", "category"]
    ordering_fields = ["name", "quantity", "purchase_price", "selling_price", "updated_at"]

    @action(detail=True, methods=["post"])
    def adjust_stock(self, request, pk=None):
        product = self.get_object()
        try:
            change = int(request.data.get("change_amount", 0))
        except (ValueError, TypeError):
            return Response({"detail": "change_amount must be an integer"}, status=status.HTTP_400_BAD_REQUEST)

        reason = request.data.get("reason", "")
        reference = request.data.get("reference", "")

        product.quantity = product.quantity + change
        product.save()

        log = StockLog.objects.create(
            product=product,
            user=request.user if request.user.is_authenticated else None,
            change_amount=change,
            reason=reason,
            resulting_quantity=product.quantity,
            reference=reference
        )

        # Low-stock detection & notifications
        try:
            if product.quantity <= product.low_stock_threshold:
                admins_qs = User.objects.filter(Q(role="admin") | Q(is_superuser=True))
                for admin in admins_qs:
                    create_notification(
                        user=admin,
                        type="low_stock",
                        title=f"Low stock: {product.name}",
                        message=f"Product '{product.name}' quantity is {product.quantity} (threshold {product.low_stock_threshold}).",
                        payload={
                            "product_id": str(product.id),
                            "product_name": product.name,
                            "quantity": product.quantity,
                            "threshold": product.low_stock_threshold,
                            "reference": reference,
                        },
                        send_email=False,
                    )

                create_notification(
                    user=None,
                    type="low_stock",
                    title=f"Low stock: {product.name}",
                    message=f"Product '{product.name}' quantity is {product.quantity} (threshold {product.low_stock_threshold}).",
                    payload={
                        "product_id": str(product.id),
                        "product_name": product.name,
                        "quantity": product.quantity,
                        "threshold": product.low_stock_threshold,
                        "reference": reference,
                    },
                    send_email=False,
                )
        except Exception:
            pass

        return Response({
            "product": ProductSerializer(product, context={"request": request}).data,
            "log": StockLogSerializer(log).data
        }, status=status.HTTP_200_OK)

    def perform_update(self, serializer):
        instance = self.get_object()
        old_price = instance.selling_price
        new_price = serializer.validated_data.get("selling_price", old_price)
        if new_price != old_price and self.request.user.is_authenticated:
            serializer.save(last_price_updated_by=self.request.user)
        else:
            serializer.save()

    @action(detail=False, methods=["post"], url_path="bulk_import", permission_classes=[IsAdminOrStaffWrite])
    def bulk_import(self, request):
        uploaded = request.FILES.get("file")
        if not uploaded:
            return Response({"detail": "No file uploaded (name 'file')"}, status=status.HTTP_400_BAD_REQUEST)

        filename = uploaded.name.lower()
        try:
            if filename.endswith(".csv"):
                df = pd.read_csv(uploaded)
            else:
                df = pd.read_excel(uploaded)
        except Exception as e:
            return Response({"detail": f"Could not read the file: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

        created = []
        failed = []
        for idx, row in df.iterrows():
            try:
                name = str(row.get("name") or row.get("Name") or "").strip()
                if not name:
                    raise ValueError("Missing name")
                data = {
                    "name": name,
                    "sku": row.get("sku") or row.get("SKU") or None,
                    "category": row.get("category") or row.get("Category") or None,
                    "purchase_price": float(row.get("purchase_price") or row.get("Purchase_Price") or 0),
                    "selling_price": float(row.get("selling_price") or row.get("Selling_Price") or 0),
                    "quantity": int(row.get("quantity") or row.get("Quantity") or 0),
                    "supplier": row.get("supplier") or row.get("Supplier") or None,
                }
                prod = Product.objects.create(**data)
                created.append(ProductSerializer(prod).data)
            except Exception as e:
                failed.append({"row": int(idx) + 1, "error": str(e)})

        return Response({"created_count": len(created), "failed": failed, "created": created})


class StockLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = StockLog.objects.select_related("product", "user").all()
    serializer_class = StockLogSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["reason", "reference", "product__name"]
    ordering_fields = ["created_at"]


class NotificationViewSet(viewsets.ModelViewSet):
    queryset = Notification.objects.all().order_by("-created_at")
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or getattr(user, "role", "") == "admin":
            return Notification.objects.all()
        return Notification.objects.filter(Q(user=user) | Q(user__isnull=True))


# ---------- Reports: Inventory, Low-stock, Stock Logs (Excel + PDF) ----------
class InventoryExcelReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, format=None):
        filters = {
            "category": request.query_params.get("category"),
            "supplier": request.query_params.get("supplier"),
        }
        rows = _fetch_inventory_rows(filters)
        df = pd.DataFrame(rows)
        if df.empty:
            df = pd.DataFrame(columns=["id", "sku", "name", "category", "quantity", "purchase_price", "selling_price", "total_value", "supplier", "low_stock_threshold"])

        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Inventory")
            summary = {
                "generated_at": [now().isoformat()],
                "total_products": [len(df)],
                "total_stock_value": [df["total_value"].sum() if "total_value" in df.columns and not df.empty else 0]
            }
            pd.DataFrame(summary).to_excel(writer, index=False, sheet_name="Summary")
        buf.seek(0)
        filename = f"inventory_summary_{datetime.utcnow().date().isoformat()}.xlsx"
        resp = StreamingHttpResponse(buf, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        resp['Content-Disposition'] = f'attachment; filename="{filename}"'
        return resp


class InventoryPdfReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, format=None):
        filters = {
            "category": request.query_params.get("category"),
            "supplier": request.query_params.get("supplier"),
        }
        rows = _fetch_inventory_rows(filters)
        data = [["SKU", "Name", "Category", "Qty", "Purchase Price", "Selling Price", "Total Value", "Supplier", "Low Threshold"]]
        for r in rows:
            data.append([
                r.get("sku", ""),
                r.get("name", ""),
                r.get("category", ""),
                str(r.get("quantity", "")),
                f"{r.get('purchase_price', 0):.2f}",
                f"{r.get('selling_price', 0) if r.get('selling_price') is not None else ''}",
                f"{r.get('total_value', 0):.2f}",
                r.get("supplier", ""),
                str(r.get("low_stock_threshold", "")),
            ])

        title = "Inventory Summary"
        buf = _build_pdf_from_table(data, title=title)
        filename = f"inventory_summary_{datetime.utcnow().date().isoformat()}.pdf"
        resp = StreamingHttpResponse(buf, content_type="application/pdf")
        resp['Content-Disposition'] = f'attachment; filename="{filename}"'
        return resp


class LowStockExcelReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, format=None):
        rows = _fetch_low_stock_rows()
        df = pd.DataFrame(rows)
        if df.empty:
            df = pd.DataFrame(columns=["id", "sku", "name", "category", "quantity", "low_stock_threshold", "purchase_price", "selling_price", "total_value", "supplier"])
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="LowStock")
            summary = {
                "generated_at": [now().isoformat()],
                "low_stock_count": [len(df)],
            }
            pd.DataFrame(summary).to_excel(writer, index=False, sheet_name="Summary")
        buf.seek(0)
        filename = f"low_stock_report_{datetime.utcnow().date().isoformat()}.xlsx"
        resp = StreamingHttpResponse(buf, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        resp['Content-Disposition'] = f'attachment; filename="{filename}"'
        return resp


class LowStockPdfReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, format=None):
        rows = _fetch_low_stock_rows()
        data = [["SKU", "Name", "Category", "Qty", "Low Threshold", "Purchase Price", "Selling Price", "Total Value", "Supplier"]]
        for r in rows:
            data.append([
                r.get("sku", ""),
                r.get("name", ""),
                r.get("category", ""),
                str(r.get("quantity", "")),
                str(r.get("low_stock_threshold", "")),
                f"{r.get('purchase_price', 0):.2f}",
                f"{r.get('selling_price', 0) if r.get('selling_price') is not None else ''}",
                f"{r.get('total_value', 0):.2f}",
                r.get("supplier", ""),
            ])
        title = "Low-Stock Report"
        buf = _build_pdf_from_table(data, title=title)
        filename = f"low_stock_report_{datetime.utcnow().date().isoformat()}.pdf"
        resp = StreamingHttpResponse(buf, content_type="application/pdf")
        resp['Content-Disposition'] = f'attachment; filename="{filename}"'
        return resp


class StockLogsExcelReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, format=None):
        from_date = request.query_params.get("from_date")
        to_date = request.query_params.get("to_date")
        rows = _fetch_stock_logs(from_date, to_date)
        df = pd.DataFrame(rows)
        if df.empty:
            df = pd.DataFrame(columns=["id", "product_id", "product_name", "user", "change_amount", "resulting_quantity", "reason", "reference", "created_at"])
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="StockLogs")
            summary = {
                "generated_at": [now().isoformat()],
                "log_count": [len(df)],
            }
            pd.DataFrame(summary).to_excel(writer, index=False, sheet_name="Summary")
        buf.seek(0)
        filename = f"stock_logs_{datetime.utcnow().date().isoformat()}.xlsx"
        resp = StreamingHttpResponse(buf, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        resp['Content-Disposition'] = f'attachment; filename="{filename}"'
        return resp


class StockLogsPdfReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, format=None):
        from_date = request.query_params.get("from_date")
        to_date = request.query_params.get("to_date")
        rows = _fetch_stock_logs(from_date, to_date)
        data = [["Product", "User", "Change", "Resulting Qty", "Reason", "Reference", "Date"]]
        for r in rows:
            data.append([
                r.get("product_name", ""),
                r.get("user", "") or "",
                str(r.get("change_amount", "")),
                str(r.get("resulting_quantity", "")),
                r.get("reason", "") or "",
                r.get("reference", "") or "",
                r.get("created_at", ""),
            ])
        title = "Stock Logs Report"
        buf = _build_pdf_from_table(data, title=title)
        filename = f"stock_logs_{datetime.utcnow().date().isoformat()}.pdf"
        resp = StreamingHttpResponse(buf, content_type="application/pdf")
        resp['Content-Disposition'] = f'attachment; filename="{filename}"'
        return resp
