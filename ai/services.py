# ai/services.py
import requests
from django.conf import settings


def ollama_generate(prompt, model=None):
    """
    Send a prompt to Ollama and return the AI response.
    """
    model = model or getattr(settings, "OLLAMA_DEFAULT_MODEL", "llama3")

    url = f"{getattr(settings, 'OLLAMA_BASE_URL', 'http://127.0.0.1:11434')}/api/generate"

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False
    }

    try:
        response = requests.post(url, json=payload, timeout=120)
        response.raise_for_status()
        data = response.json()
        return data.get("response", "")
    except Exception as e:
        return f"Ollama Error: {str(e)}"
