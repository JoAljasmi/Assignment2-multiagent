import json
from datetime import datetime
from pathlib import Path

SESSIONS_DIR = Path(__file__).parent / "sessions"

def start_session():
    """Creating the sessions dir if needed, returning the session file path for this log"""
    SESSIONS_DIR.mkdir(exist_ok=True)
    Timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    return SESSIONS_DIR / f"session_{Timestamp}.json"

def save_session(path, messages):
    """automatically dump the messages to a list in the session file"""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(messages, f, indent=2, ensure_ascii=False)
