import os
from dotenv import load_dotenv
import requests
from config import PROVIDER_URL, MODEL
from pathlib import Path


load_dotenv(Path(__file__).parent.parent / ".env")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")


def chat(messages, tools=None):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    body = {
        "model": MODEL,
        "messages": messages,
    }
    if tools is not None:
        body["tools"] = tools

    response = requests.post(PROVIDER_URL, headers=headers, json=body)
    if response.status_code != 200:
        raise RuntimeError(
            f"OpenRouter call failed: HTTP {response.status_code}\n{response.text}"
        )
    return response.json()["choices"][0]["message"]