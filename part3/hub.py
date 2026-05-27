import requests
from config import HUB_URL, HUB_PASSWORD, AGENT_NAME, MAX_RESPONSES_PER_RUN, DRY_RUN
from secrets_filter import scan_for_secrets
import threading

HUB_MAX_MESSAGE_CHARS = 4000  # hub limit is 4096; leave headroom

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
    if not (200 <= response.status_code < 300):
        print(f"[hub] fetch returned {response.status_code}: {response.text}")
        return []

    messages = response.json().get("messages", [])
    return [m for m in messages if m["agent_name"] != AGENT_NAME]


def post_message(content, budget=None):
    """Post a message to the hub. Returns the assigned seq number, or None on failure.
    Only disables posting on PERMANENT caps, not on transient rate limits."""

    global _posted_count

    is_safe, reason = scan_for_secrets(content)
    if not is_safe:
        print(f"[hub] REFUSED to post: outgoing message looks like a secret leak ({reason})")
        return None

    if len(content) > HUB_MAX_MESSAGE_CHARS:
        print(f"[hub] message too long ({len(content)} > {HUB_MAX_MESSAGE_CHARS}), will not post")
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
        # Only disable posting on PERMANENT caps, not on transient rate limits.
        # Transient: "wait N seconds", "rate limited", "too fast" -> retry later.
        # Permanent: "cap", "daily", "exceeded" -> stop trying.
        is_permanent = any(w in body_text for w in ("cap", "daily", "exceeded", "quota"))
        is_transient = any(w in body_text for w in ("wait", "second", "rate limit", "too fast"))
        if budget is not None and is_permanent and not is_transient:
            budget.disable_posting(f"hub returned 429 (cap): {response.text[:120]}")
        return None
    if not (200 <= response.status_code < 300):
        print(f"[hub] post returned {response.status_code}: {response.text}")
        return None

    with _count_lock:
        _posted_count += 1
    return response.json().get("seq")


if __name__ == "__main__":
    print(f"Fetching all messages from hub for agent '{AGENT_NAME}'...")
    messages = fetch_new_messages(0)
    print(f"Got {len(messages)} messages (excluding own).")
    for m in messages[:10]:
        print(f"  [{m['seq']}] {m['agent_name']}: {m['content'][:80]}")
    if len(messages) > 10:
        print(f"  ... and {len(messages) - 10} more")