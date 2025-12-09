# ai/ollama.py
import requests
from django.conf import settings

OLLAMA_URL = getattr(settings, "OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = getattr(settings, "OLLAMA_MODEL", "llama3")
GEN_PATH = "/api/generate"
MODELS_PATH = "/api/models"  # Ollama exposes models list at /api/models

def ask_ollama(prompt, model=None, timeout=120):
    model = model or OLLAMA_MODEL
    payload = {"model": model, "prompt": prompt, "stream": False}
    url = OLLAMA_URL.rstrip("/") + GEN_PATH
    try:
        res = requests.post(url, json=payload, timeout=timeout)
        # if model not found, try to pick another available model
        if res.status_code == 400 and "not found" in res.text.lower():
            # try listing models
            try:
                ml = requests.get(OLLAMA_URL.rstrip("/") + MODELS_PATH, timeout=10)
                ml.raise_for_status()
                models = ml.json()
                # models might be a list of names or dicts; normalise
                if isinstance(models, list) and models:
                    first = None
                    if isinstance(models[0], dict):
                        # example dict: {"name": "llama2", ...}
                        first = models[0].get("name") or models[0].get("model")
                    else:
                        first = models[0]
                    if first and first != model:
                        payload["model"] = first
                        res = requests.post(url, json=payload, timeout=timeout)
            except Exception:
                # ignore listing failures, raise original
                pass
        res.raise_for_status()
        j = res.json()
        # Ollama returns 'response' or sometimes 'output'; be forgiving
        return j.get("response") or j.get("output") or j
    except requests.RequestException as e:
        # raise a clearer exception for the view to log
        raise Exception(f"Ollama request failed: {str(e)}. Response text: {getattr(e.response,'text',None)}")
