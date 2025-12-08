from django.db import models
import uuid
from django.conf import settings

class Product(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sku = models.CharField(max_length=64, unique=True, blank=True, null=True)
    name = models.CharField(max_length=255)
    category = models.CharField(max_length=128, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    purchase_price = models.DecimalField(max_digits=12, decimal_places=2)
    selling_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    quantity = models.IntegerField(default=0)
    supplier = models.CharField(max_length=255, blank=True, null=True)
    barcode = models.CharField(max_length=128, blank=True, null=True)
    low_stock_threshold = models.IntegerField(default=5)
    reorder_qty = models.IntegerField(default=10)
    image = models.ImageField(upload_to="products/", blank=True, null=True)
    last_price_updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def total_value(self):
        return self.quantity * self.purchase_price

    def __str__(self):
        return self.name

class StockLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="stock_logs")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    change_amount = models.IntegerField()  # positive for add, negative for remove
    reason = models.CharField(max_length=255, blank=True, null=True)
    resulting_quantity = models.IntegerField()
    reference = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

class Notification(models.Model):
    """
    Simple notification model.
    - user: who should receive it. If null, it's a broadcast (shop-wide).
    - type: low_stock, stock_changed, price_suggestion_ready, message_received, etc.
    - payload: JSON with contextual data (product id, name, qty, threshold, link).
    - is_read: mark read/unread.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE)
    type = models.CharField(max_length=64)
    title = models.CharField(max_length=255)
    message = models.TextField(blank=True)
    payload = models.JSONField(default=dict, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.type} - {self.title}"
    
class Sale(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="sales")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=12, decimal_places=2)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        self.total_price = self.quantity * self.unit_price
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product.name} x {self.quantity} ({self.total_price})"