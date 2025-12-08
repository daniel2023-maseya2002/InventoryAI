# ai/reports.py
from inventory.models import Product, StockLog
from django.utils.timezone import now
from .ollama import ask_ollama


def generate_inventory_ai_report():
    products = Product.objects.all()

    if not products.exists():
        return "No products available to analyze."

    low_stock = []
    best_sellers = []
    dead_stock = []

    for p in products:
        if p.quantity <= p.low_stock_threshold:
            low_stock.append(f"{p.name} (qty={p.quantity})")

        logs_count = StockLog.objects.filter(product=p).count()
        if logs_count > 20:
            best_sellers.append(p.name)
        if logs_count == 0:
            dead_stock.append(p.name)

    prompt = f"""
You are a professional inventory AI analyst.

DATE: {now().date()}

LOW STOCK ITEMS:
{", ".join(low_stock) or "None"}

BEST SELLING PRODUCTS:
{", ".join(best_sellers) or "None"}

DEAD STOCK PRODUCTS:
{", ".join(dead_stock) or "None"}

TASK:
1. Generate a professional business intelligence report.
2. Give risk warnings.
3. Provide reorder recommendations.
4. Suggest actions for dead stock.
"""

    return ask_ollama(prompt)
    