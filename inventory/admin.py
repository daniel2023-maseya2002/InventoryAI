from django.contrib import admin
from .models import Product, StockLog, Notification

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "sku", "category", "quantity", "purchase_price", "selling_price", "low_stock_threshold")
    search_fields = ("name", "sku", "barcode", "category", "supplier")
    list_filter = ("category", "supplier")
    readonly_fields = ("created_at", "updated_at")

@admin.register(StockLog)
class StockLogAdmin(admin.ModelAdmin):
    list_display = ("product", "user", "change_amount", "resulting_quantity", "reason", "created_at")
    search_fields = ("product__name", "reason", "reference")
    list_filter = ("created_at",)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "type", "user", "is_read", "created_at")
    search_fields = ("title", "message", "type")
    list_filter = ("type", "is_read", "created_at")