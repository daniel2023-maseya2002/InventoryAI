# ai/ollama.py
import requests

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3"   # or mistral, deepseek, etc.

def ask_ollama(prompt: str) -> str:
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
    }

    res = requests.post(OLLAMA_URL, json=payload, timeout=120)

    if res.status_code != 200:
        raise Exception(f"Ollama error: {res.text}")

    return res.json().get("response", "")
