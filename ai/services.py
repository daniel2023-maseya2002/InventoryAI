import requests
import json
import re
from inventory.models import Product, Sale
from django.db.models import Sum
from datetime import timedelta
from django.utils.timezone import now

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3"


# ✅ CLEAN AI REQUEST
def ollama_generate(prompt: str) -> str:
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "format": "json"  # ✅ THIS FORCES PURE JSON OUTPUT
    }

    res = requests.post(OLLAMA_URL, json=payload, timeout=400)
    res.raise_for_status()
    return res.json()["response"]


# ✅ SAFE JSON PARSER (ANTI-CRASH)
def safe_json_parse(text):
    try:
        # Remove markdown formatting if AI still sneaks it in
        text = re.sub(r"```json|```", "", text).strip()
        return json.loads(text)
    except Exception:
        return {
            "raw_ai_output": text,
            "error": "Failed to parse AI JSON"
        }


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

    sales_data = [
        {
            "product": s["product__name"],
            "quantity_sold": s["total_qty"]
        }
        for s in sales
    ]

    stock_data = [
        {
            "product": p.name,
            "stock": p.quantity,
            "low_stock_threshold": p.low_stock_threshold
        }
        for p in products
    ]

    prompt = f"""
Return ONLY valid raw JSON. No text. No explanation. No markdown.

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

    return safe_json_parse(ai_response)
