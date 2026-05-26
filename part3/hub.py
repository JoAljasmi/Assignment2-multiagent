import requests
from config import HUB_URL, HUB_PASSWORD, AGENT_NAME

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

def post_message(content):
    """post a message to the hub. returns the assigned seq number, or none on failure."""
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

    