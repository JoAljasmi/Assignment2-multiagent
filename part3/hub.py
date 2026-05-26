import requests
from config import HUB_URL, HUB_PASSWORD, AGENT_NAME, MAX_RESPONSES_PER_RUN, DRY_RUN
from secrets_filter import scan_for_secrets
import threading

_posted_count = 0
_count_lock = threading.Lock()


def fetch_new_messages(since):
    """fetch all messages from the hub with seq > since.
    return a list of message dicts, or [] on error.
    filters out messages from this agent itself."""
    try:
        response = requests.get(
            f"{HUB_URL}/api/messages",
            params={"since": since, "password": HUB_PASSWORD},
            timeout=10,
        )
    except requests.RequestException as e:
        print(f"[hub] fetch failed: {e}")
        return []

    if response.status_code == 429:
        print(f"[hub] rate limited on fetch, will retry next poll")
        return []
    if response.status_code != 200:
        print(f"[hub] fetch returned {response.status_code}: {response.text}")
        return []
    
    messages = response.json().get("messages",[])
    return [m for m in messages if m["agent_name"] != AGENT_NAME]

def post_message(content, budget=None):
    """Post a message to the hub. Returns the assigned seq number, or None on failure.
    If a 429 cap is hit and budget is provided, disables further posting."""

    global _posted_count
    
    is_safe, reason = scan_for_secrets(content)
    if not is_safe:
        print(f"[hub] REFUSED to post: outgoing message looks like a secret leak ({reason})")
        return None

    with _count_lock:
        if _posted_count >= MAX_RESPONSES_PER_RUN:
            print(f"[hub] local max_responses_per_run reached ({_posted_count}), not posting")
            if budget is not None:
                budget.disable_posting("local max_responses_per_run reached")
            return None

    if DRY_RUN:
        with _count_lock:
            _posted_count += 1
        print(f"[hub][DRY_RUN] would post (count={_posted_count}/{MAX_RESPONSES_PER_RUN}): {content[:120]}")
        return -1 

    try:
        response = requests.post(
            f"{HUB_URL}/api/message",
            json={
                "agent_name": AGENT_NAME,
                "content": content,
                "password": HUB_PASSWORD,
            },
            timeout=10,
        )
    except requests.RequestException as e:
        print(f"[hub] post failed: {e}")
        return None
    
    if response.status_code == 429:
        print(f"[hub] capped or rate limited: {response.text}")
        body_text = response.text.lower()
        if budget is not None and ("cap" in body_text or "limit" in body_text):
            budget.disable_posting(f"hub returned 429: {response.text[:120]}")
        return None
    if response.status_code != 200:
        print(f"[hub] post returned {response.status_code}: {response.text}")
        return None
    
    return response.json().get("seq")

if __name__ == "__main__":
    print(f"Fetching all messages from hub for agent '{AGENT_NAME}'...")
    messages = fetch_new_messages(0)
    print(f"Got {len(messages)} messages (excluding own).")
    for m in messages[:10]:
        print(f"  [{m['seq']}] {m['agent_name']}: {m['content'][:80]}")
    if len(messages) > 10:
        print(f"  ... and {len(messages) - 10} more")

    