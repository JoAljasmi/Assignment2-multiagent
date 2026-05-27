import threading
import time
from hub import fetch_new_messages, post_message
from config import POLL_INTERVAL, AGENT_NAME, MAX_TOKENS_DEFAULT, MAX_REQUESTS_PER_MINUTE_DEFAULT
from budget import Budget
from console_control import run_console
from classifier import classify, format_chat_history
from agent import run_agent


CHAT_HISTORY_SIZE = 10
chat_history = []
budget = Budget(MAX_TOKENS_DEFAULT, MAX_REQUESTS_PER_MINUTE_DEFAULT)
_last_ratelimit_print = 0


def remember(msg):
    chat_history.append(msg)
    if len(chat_history) > CHAT_HISTORY_SIZE:
        chat_history.pop(0)


def handle_message(msg):
    global _last_ratelimit_print
    
    if not budget.is_posting_enabled():
        print(f"[handle] skipping (posting disabled) | from {msg['agent_name']}: {msg['content'][:60]}")
        return

    try:
        decision = classify(msg, chat_history[:-1], budget=budget)
    except RuntimeError as e:
        now = time.time()
        if now - _last_ratelimit_print > 30: 
            print(f"[handle] classifier blocked: {e}")
            _last_ratelimit_print = now
        return

    print(f"[classifier] {decision} | seq={msg['seq']} | from {msg['agent_name']}: {msg['content'][:120]}")

    if decision in ("IGNORE", "YIELD"):
        return

    user_message = (
        f"You are participating in a group chat. Here is recent context:\n\n"
        f"{format_chat_history(chat_history[:-1])}\n\n"
        f"The latest message is:\n"
        f"[{msg['agent_name']}] {msg['content']}\n\n"
    )
    user_message += (
    "Write your reply as plain text. Do not prefix it with any agent name "
    "or use bracket-name formatting — everyone in the chat sees every message. "
    "Just write what you want to say.\n\n"
    )
    
    if decision == "REPLY":
        user_message += (
            "Respond with a short, useful chat message. "
            "Do not call any tools. Keep your reply concise."
        )
    elif decision == "TOOL_CALL":
        user_message += (
            "You may use tools (bash, edit_file) to do real work, then "
            "post a short chat reply summarizing what you did or what you found. "
            "Keep messages concise — every post counts against your 10-message cap."
        )

    def deliver_to_hub(text):
        seq = post_message(text, budget=budget)
        if seq is not None:
            print(f"[handle] posted reply, seq={seq}")
        else:
            print(f"[handle] post failed")

    print(f"[handle] running agent for decision={decision}")
    try:
        run_agent(user_message, deliver=deliver_to_hub, budget=budget)
    except RuntimeError as e:
        print(f"[handle] agent blocked: {e}")


def main():
    global chat_history

    print(f"[chat_loop] agent '{AGENT_NAME}' starting")
    print(f"[chat_loop] poll interval: {POLL_INTERVAL}s")
    print(f"[chat_loop] initial budget: {budget.snapshot()}")

    stop_event = threading.Event()
    console_thread = threading.Thread(
        target=run_console, args=(budget, stop_event), daemon=True
    )
    console_thread.start()

    print("[chat_loop] fetching existing chat for context...")
    existing = fetch_new_messages(0)
    if existing:
        # Populate the rolling chat history with the most recent messages.
        for msg in existing[-CHAT_HISTORY_SIZE:]:
            chat_history.append(msg)
        # Set last_seen so we only classify messages newer than what's already there.
        last_seen = max(m["seq"] for m in existing)
        print(f"[chat_loop] joined chat with {len(existing)} prior messages; starting fresh from seq {last_seen}")
    else:
        last_seen = 0
        print("[chat_loop] no prior messages, starting from seq 0")

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
        stop_event.set()


if __name__ == "__main__":
    main()