import time
from hub import fetch_new_messages, post_message
from config import POLL_INTERVAL, AGENT_NAME
from classifier import classify


CHAT_HISTORY_SIZE = 10
chat_history = []

def remember(msg):
    chat_history.append(msg)
    if len(chat_history) > CHAT_HISTORY_SIZE:
        chat_history.pop(0)

def handle_message(msg):
    """classify and call run_agent"""
    decision = classify(msg, chat_history[:-1])  # exclude the message itself from "history"
    print(f"[classifier] {decision} | from {msg['agent_name']}: {msg['content'][:120]}")

    if decision == "IGNORE":
        return

    print(f"[handle] would act with decision={decision}, not implemented yet")


def main():
    print(f"[chat_loop] agent '{AGENT_NAME}' starting")
    print(f"[chat_loop] poll interval: {POLL_INTERVAL}s")

    last_seen = 0
    try:
        while True:
            time.sleep(POLL_INTERVAL)
            new_messages = fetch_new_messages(last_seen)
            for msg in new_messages:
                remember(msg)
                handle_message(msg)
                last_seen = max(last_seen, msg["seq"])
    except KeyboardInterrupt:
        print("\n[chat_loop] shutting down")


if __name__ == "__main__":
    main()