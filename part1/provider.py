import os
from dotenv import load_dotenv
import requests

# Load constants
load_dotenv()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "openai/gpt-4o-mini"

def chat(messages):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    body = {
        "model": MODEL,
        "messages": messages
    }
    response = requests.post(OPENROUTER_URL, headers=headers, json=body)
    response_json = response.json()
    return response_json["choices"][0]["message"]["content"]



if __name__ == "__main__":
    reply = chat([
        {"role": "user", "content": "whats 4+4?"}
    ])
    print(reply)