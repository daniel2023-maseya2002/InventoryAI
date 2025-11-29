# inventory/urls.py
from django.urls import path, include
from rest_framework import routers
from .views import (
    ProductViewSet, StockLogViewSet, NotificationViewSet,
    InventoryExcelReportView, InventoryPdfReportView,
    LowStockExcelReportView, LowStockPdfReportView,
    StockLogsExcelReportView, StockLogsPdfReportView
)

router = routers.DefaultRouter()
router.register(r'products', ProductViewSet, basename='product')
router.register(r'stock-logs', StockLogViewSet, basename='stocklog')
router.register(r'notifications', NotificationViewSet, basename='notification')

urlpatterns = [
    path('', include(router.urls)),
    path('reports/inventory.xlsx', InventoryExcelReportView.as_view(), name='inventory-excel'),
    path('reports/inventory.pdf', InventoryPdfReportView.as_view(), name='inventory-pdf'),
    path('reports/low_stock.xlsx', LowStockExcelReportView.as_view(), name='lowstock-excel'),
    path('reports/low_stock.pdf', LowStockPdfReportView.as_view(), name='lowstock-pdf'),
    path('reports/stock_logs.xlsx', StockLogsExcelReportView.as_view(), name='stocklogs-excel'),
    path('reports/stock_logs.pdf', StockLogsPdfReportView.as_view(), name='stocklogs-pdf'),
]
