import json
from datetime import datetime
from pathlib import Path

SESSIONS_DIR = Path(__file__).parent / "sessions"

def start_session(user_goal=""):
    """Creating the sessions dir if needed, returning the session file path for this log"""
    SESSIONS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    # Take first few words of goal for the filename, sanitize
    slug = "".join(c if c.isalnum() else "_" for c in user_goal[:40]).strip("_")
    filename = f"session_{timestamp}_{slug}.json" if slug else f"session_{timestamp}.json"
    return SESSIONS_DIR / filename

def save_session(path, messages):
    """automatically dump the messages to a list in the session file"""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(messages, f, indent=2, ensure_ascii=False)
