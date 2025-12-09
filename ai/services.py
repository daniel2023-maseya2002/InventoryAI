import requests
import json
from django.conf import settings
from inventory.models import Product, Sale
from django.db.models import Sum
from datetime import timedelta
from django.utils.timezone import now

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3"

def ollama_generate(prompt: str) -> str:
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False
    }

    res = requests.post(OLLAMA_URL, json=payload, timeout=400)
    res.raise_for_status()
    return res.json()["response"]


# ✅ MAIN AI ENGINE
def generate_sales_ai_report(days=30):
    since = now() - timedelta(days=days)

    sales = (
        Sale.objects.filter(created_at__gte=since)
        .values("product__name")
        .annotate(total_qty=Sum("quantity"))
        .order_by("-total_qty")
    )

    products = Product.objects.all()

    sales_data = []
    for s in sales:
        sales_data.append({
            "product": s["product__name"],
            "quantity_sold": s["total_qty"]
        })

    stock_data = []
    for p in products:
        stock_data.append({
            "product": p.name,
            "stock": p.quantity,
            "low_stock_threshold": p.low_stock_threshold
        })

    prompt = f"""
You are an AI inventory analyst.

Sales Data:
{json.dumps(sales_data, indent=2)}

Stock Data:
{json.dumps(stock_data, indent=2)}

Return STRICT JSON with:
- best_selling_products
- dead_stock_products
- reorder_recommendations
- low_stock_warnings
- demand_forecast
- summary_insight
"""

    ai_response = ollama_generate(prompt)

    try:
        return json.loads(ai_response)
    except Exception:
        return {
            "raw_ai_output": ai_response,
            "error": "Failed to parse AI JSON"
        }
