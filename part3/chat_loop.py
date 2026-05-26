import time
from hub import fetch_new_messages, post_message
from config import POLL_INTERVAL, AGENT_NAME


def handle_messages(msg):
    """classify and call run_agent"""
    print(f"[handle] from {msg['agent_name']}: {msg['content'][:200]}")

def main():
    print(f"[chat_loop] agent '{AGENT_NAME}' starting")
    print(f"[chat_loop] poll interval: {POLL_INTERVAL}s")

    last_seen = 0
    try:
        while True:
            time.sleep(POLL_INTERVAL)
            new_messages = fetch_new_messages(last_seen)
            for msg in new_messages:
                handle_messages(msg)
                last_seen = max(last_seen, msg["seq"])
    except KeyboardInterrupt:
        print("\n[chat_loop] shutting down")


if __name__ == "__main__":
    main()