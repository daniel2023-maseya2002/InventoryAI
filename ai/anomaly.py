from inventory.models import Product, Sale
from django.db.models import Sum
from django.utils.timezone import now
from datetime import timedelta

def detect_anomalies():
    anomalies = []

    recent_sales = Sale.objects.filter(
        created_at__gte=now() - timedelta(days=1)
    )

    for product in Product.objects.all():
        total = recent_sales.filter(product=product).aggregate(t=Sum("quantity"))["t"] or 0

        if product.quantity < 0:
            anomalies.append(f"NEGATIVE STOCK: {product.name}")

        if total > product.low_stock_threshold * 5:
            anomalies.append(f"POSSIBLE FRAUD: {product.name} sold unusually fast")

    return anomalies
