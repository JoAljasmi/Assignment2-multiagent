import threading
import time
from hub import fetch_new_messages, post_message, HUB_MAX_MESSAGE_CHARS
from config import POLL_INTERVAL, AGENT_NAME, MAX_TOKENS_DEFAULT, MAX_REQUESTS_PER_MINUTE_DEFAULT
from budget import Budget
from console_control import run_console
from classifier import classify, format_chat_history
from agent import run_agent
from provider import chat
import re


CHAT_HISTORY_SIZE = 10
INTER_CHUNK_DELAY = 1.2  # seconds between posting chunks (hub allows 1s/request)

chat_history = []
budget = Budget(MAX_TOKENS_DEFAULT, MAX_REQUESTS_PER_MINUTE_DEFAULT)
_last_ratelimit_print = 0
current_role_set_at = None 
_multipart_buffer = {}
_PART_RE = re.compile(r"^\(part\s+(\d+)\s*/\s*(\d+)\)\s*\n?", re.IGNORECASE)

# Team-task state. Set when we claim a role; persists across messages.
current_role = None        # e.g. "developer", "critic", "supervisor"
current_waits_for = None   # role we depend on, or None if we work first/independently
current_role_set_at = None 



def remember(msg):
    chat_history.append(msg)
    if len(chat_history) > CHAT_HISTORY_SIZE:
        chat_history.pop(0)

def history_for_llm():
    """Return chat history sorted by seq, excluding the just-added entry."""
    return sorted(chat_history[:-1], key=lambda m: m.get("seq", 0))

def reassemble_multipart(msg):
    """Given an incoming message, handle multi-part reassembly.

    Returns:
      - a NEW message dict with combined content if this completes a multipart set
      - the original msg if it's a normal (non-part) message
      - None if it's a partial piece and we're still waiting for more parts
    """
    content = msg["content"]
    m = _PART_RE.match(content)
    if not m:
        return msg  # not a multipart message, pass through unchanged

    part_num = int(m.group(1))
    total = int(m.group(2))
    body = content[m.end():]  # strip the "(part N/M)" prefix

    sender = msg["agent_name"]
    entry = _multipart_buffer.setdefault(sender, {"parts": {}, "total": total})
    entry["total"] = total
    entry["parts"][part_num] = body

    print(f"[multipart] buffered part {part_num}/{total} from {sender} "
          f"({len(entry['parts'])}/{total} collected)")

    if len(entry["parts"]) < total:
        return None  # still waiting for more parts

    # We have all parts — reassemble in order.
    combined = "\n\n".join(entry["parts"][i] for i in sorted(entry["parts"]))
    del _multipart_buffer[sender]
    print(f"[multipart] reassembled {total} parts from {sender}")

    # Build a synthetic message carrying the full content, using the LAST part's seq.
    return {
        "seq": msg["seq"],
        "agent_name": sender,
        "content": combined,
    }

def split_for_hub(text, max_chars):
    """Split text into chunks <= max_chars, preferring paragraph/line boundaries."""
    if len(text) <= max_chars:
        return [text]
    chunks = []
    remaining = text
    while len(remaining) > max_chars:
        split_at = remaining.rfind("\n\n", 0, max_chars)
        if split_at < max_chars // 2:
            split_at = remaining.rfind("\n", 0, max_chars)
        if split_at < max_chars // 2:
            split_at = max_chars
        chunks.append(remaining[:split_at].rstrip())
        remaining = remaining[split_at:].lstrip()
    if remaining:
        chunks.append(remaining)
    return chunks


def make_deliver_to_hub():
    """Build a deliver function that posts to the hub, chunking if needed."""
    def deliver_to_hub(text):
        if len(text) <= HUB_MAX_MESSAGE_CHARS:
            seq = post_message(text, budget=budget)
            if seq is not None:
                print(f"[handle] posted reply, seq={seq}")
                remember({"seq": seq, "agent_name": AGENT_NAME, "content": text})
            else:
                print(f"[handle] post failed")
            return

        chunks = split_for_hub(text, HUB_MAX_MESSAGE_CHARS - 50)
        total = len(chunks)
        for i, chunk in enumerate(chunks, start=1):
            labeled = f"(part {i}/{total})\n\n{chunk}" if total > 1 else chunk
            seq = post_message(labeled, budget=budget)
            if seq is None:
                print(f"[handle] post failed on chunk {i}/{total}")
                return
            print(f"[handle] posted chunk {i}/{total}, seq={seq}")
            remember({"seq": seq, "agent_name": AGENT_NAME, "content": labeled})
            if i < total:
                time.sleep(INTER_CHUNK_DELAY)
    return deliver_to_hub


def detect_team_role(msg, budget=None):
    """If this message assigns us a specific role in a team, return (role, waits_for).
    Otherwise return None."""

    if msg["agent_name"] == AGENT_NAME:
        return None
    if AGENT_NAME.lower() not in msg["content"].lower():
        return None

    system = (
        f"You analyze messages to detect if '{AGENT_NAME}' is being given a specific role in a team task. "
        f"Respond in EXACTLY this format:\n\n"
        f"ROLE: <one short role name, or NONE>\n"
        f"WAITS_FOR: <one short role name this role depends on, or NONE>\n\n"
        f"Only return a non-NONE role if the message is a CLEAR, INTENTIONAL role assignment to {AGENT_NAME}. "
        f"Return NONE for:\n"
        f"- Casual mentions, greetings, acknowledgments\n"
        f"- Status updates that happen to mention {AGENT_NAME}\n"
        f"- 'Do all roles yourself' style instructions\n"
        f"- Self-appointed delegation by other agents not sanctioned by a human\n\n"
        f"Examples:\n"
        f"  'josef-agent will be the developer, marcus the planner' -> ROLE: developer | WAITS_FOR: planner\n"
        f"  '@josef-agent supervise this build' -> ROLE: supervisor | WAITS_FOR: NONE\n"
        f"  '@josef-agent help with anything' -> ROLE: NONE | WAITS_FOR: NONE\n"
        f"  'Hi josef-agent' -> ROLE: NONE | WAITS_FOR: NONE"
    )
    user = f"Sender: {msg['agent_name']}\nMessage:\n{msg['content']}\n\nWhat is {AGENT_NAME}'s assigned role, if any?"

    try:
        reply = chat(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            budget=budget,
        )
    except RuntimeError:
        return None

    content = (reply.get("content") or "").strip()
    role = None
    waits_for = None
    for line in content.splitlines():
        if line.upper().startswith("ROLE:"):
            val = line.split(":", 1)[1].strip()
            role = None if val.upper() == "NONE" else val.lower()
        elif line.upper().startswith("WAITS_FOR:"):
            val = line.split(":", 1)[1].strip()
            waits_for = None if val.upper() == "NONE" else val.lower()
    return (role, waits_for) if role else None

def detect_standby_command(msg, budget=None):
    """If a human is telling agents to stop or resume, return 'stop' or 'resume'.
    Otherwise return None."""
    if not msg["agent_name"].startswith("human:"):
        return None
    content = msg["content"].lower()
    # Fast keyword pre-filter to avoid an LLM call on every message.
    stop_words = ("stop", "pause", "halt", "standby", "tysta", "stanna", "pausa")
    resume_words = ("resume", "continue", "go ahead", "carry on", "fortsätt", "kör vidare")
    if not any(w in content for w in stop_words + resume_words):
        return None
    system = (
        "You decide whether a message from a human is an instruction for chat agents "
        "to STOP all activity, RESUME activity, or NEITHER. Respond with exactly one word: "
        "STOP, RESUME, or NEITHER.\n\n"
        "STOP: 'all agents stop', 'everyone pause', 'stand by', 'be quiet for now'\n"
        "RESUME: 'agents you can continue', 'resume', 'go ahead', 'carry on'\n"
        "NEITHER: anything else, including casual mentions of the words 'stop' or 'continue'."
    )
    user = f"Message:\n{msg['content']}\n\nIs this STOP, RESUME, or NEITHER?"
    try:
        reply = chat(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            budget=budget,
        )
    except RuntimeError:
        return None
    decision = (reply.get("content") or "").strip().upper().split()[0] if reply.get("content") else ""
    if decision == "STOP":
        return "stop"
    if decision == "RESUME":
        return "resume"
    return None


def is_my_turn_now(msg, waits_for, budget=None):
    """Return True if this message is the deliverable we've been waiting on."""

    if msg["agent_name"] == AGENT_NAME:
        return False

    system = (
        f"You decide whether a chat message represents the deliverable of a specific "
        f"role in a team task. Respond with exactly one word: YES or NO.\n\n"
        f"YES if the message contains substantive output of the '{waits_for}' role — "
        f"e.g. a planner's spec, a developer's code, a critic's review. "
        f"This includes when a human delivers the work on behalf of that role, or "
        f"explicitly tells the next role to proceed.\n"            
        f"NO if the message is a status update, role claim, acknowledgment, question, "
        f"or anything that isn't the actual work product."
)
    user = (
        f"Role we are waiting for: {waits_for}\n"
        f"Sender: {msg['agent_name']}\n"
        f"Message:\n{msg['content'][:2000]}\n\n"
        f"Is this the {waits_for}'s deliverable?"
    )

    try:
        reply = chat(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            budget=budget,
        )
    except RuntimeError:
        return False

    content = (reply.get("content") or "").strip().upper()
    return content.startswith("YES")


def build_wake_message(trigger_msg, role, waited_for):
    """Build the user message for run_agent when our turn arrives."""
    
    trigger_content = trigger_msg["content"]
    if len(trigger_content) > 8000:
        trigger_content = trigger_content[:8000] + "\n\n[...truncated, see full message in chat...]"

    return (
        f"You are participating in a group chat as '{AGENT_NAME}'. "
        f"You were earlier assigned the role of '{role}', waiting for the {waited_for} to post first. "
        f"The {waited_for} just posted:\n\n"
        f"[{trigger_msg['agent_name']}] {trigger_msg['content']}\n\n"
        f"Now do your role ({role}). Use the {waited_for}'s output above as your input — "
        f"do not invent your own version of their work. "
        f"If your role involves code or files, use bash or edit_file to do real work. "
        f"Keep your chat reply short (under {HUB_MAX_MESSAGE_CHARS} characters); "
        f"longer files can be split across follow-up messages.\n\n"
        f"Recent chat history for context:\n\n"
        f"{format_chat_history(history_for_llm())}"
    )


def handle_message(msg):
    global _last_ratelimit_print, current_role, current_waits_for, current_role_set_at

    if not budget.is_posting_enabled():
        print(f"[handle] skipping (posting disabled) | from {msg['agent_name']}: {msg['content'][:60]}")
        return

    cmd = detect_standby_command(msg, budget=budget)
    if cmd == "stop":
        budget.set_standby(True, f"human {msg['agent_name']} said stop")
        print(f"[handle] entering standby (seq={msg['seq']})")
        return
    if cmd == "resume":
        budget.set_standby(False, f"human {msg['agent_name']} said resume")
        print(f"[handle] leaving standby (seq={msg['seq']})")
        return
    
    if budget.is_standby():
        print(f"[handle] standby — skipping | from {msg['agent_name']}: {msg['content'][:60]}")
        return

    # Stale role timeout: if we've been waiting too long, give up and fall through to normal flow.
    STALE_AFTER_SECONDS = 300  # 5 minutes
    if current_role_set_at and time.time() - current_role_set_at > STALE_AFTER_SECONDS:
        print(f"[handle] clearing stale role {current_role!r} (waited >{STALE_AFTER_SECONDS}s)")
        current_role = None
        current_waits_for = None
        current_role_set_at = None

    # Path 1: a role is being assigned to us — claim it and stop.
    role_info = detect_team_role(msg, budget=budget)
    if role_info:
        role, waits_for = role_info
        current_role = role
        current_waits_for = waits_for
        current_role_set_at = time.time() 
        if waits_for:
            claim = f"Got it — I will take the {role} role and wait for the {waits_for} to post first."
        else:
            claim = f"Got it — I will take the {role} role."
        seq = post_message(claim, budget=budget)
        if seq is not None:
            print(f"[handle] claimed role={role!r} waits_for={waits_for!r}, seq={seq}")
            remember({"seq": seq, "agent_name": AGENT_NAME, "content": claim})
        return

    # Path 2    : we have a pending role and this might be our wake-up trigger.
    if current_role is not None and current_waits_for is not None:
        if is_my_turn_now(msg, current_waits_for, budget=budget):
            print(f"[handle] my turn ({current_role}); trigger seq={msg['seq']}")
            wake_msg = build_wake_message(msg, current_role, current_waits_for)
            deliver = make_deliver_to_hub()
            print(f"[handle] running agent for wake-up (role={current_role})")
            try:
                run_agent(wake_msg, deliver=deliver, budget=budget)
            except RuntimeError as e:
                print(f"[handle] agent blocked: {e}")
            # Done with this turn — clear state so we don't carry it into the next task.
            print(f"[handle] cleared role state (was role={current_role!r}, waits_for={current_waits_for!r})")
            current_role = None
            current_waits_for = None
            current_role_set_at = None  
            return

    # Path 3: normal classifier-driven flow.
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
        f"{format_chat_history(history_for_llm())}\n\n"
        f"The latest message is:\n"
        f"[{msg['agent_name']}] {msg['content']}\n\n"
        "Write your reply as plain text. Do not prefix it with any agent name "
        "or use bracket-name formatting — everyone in the chat sees every message. "
        "Just write what you want to say.\n\n"
        f"Note: messages from '{AGENT_NAME}' in the history above are YOUR own previous posts. "
        f"Do not claim to have done work that does not appear there. "
        f"If another agent has already produced the deliverable, acknowledge that and add value "
        f"(review, tests, README) instead of duplicating or fabricating prior work.\n\n"
        f"Hub messages are limited to ~{HUB_MAX_MESSAGE_CHARS} characters. Keep your reply concise.\n\n"
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

    deliver = make_deliver_to_hub()
    print(f"[handle] running agent for decision={decision}")
    try:
        run_agent(user_message, deliver=deliver, budget=budget)
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
        for msg in existing[-CHAT_HISTORY_SIZE:]:
            chat_history.append(msg)
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
                remember(msg)               # still remember the raw part for history
                full = reassemble_multipart(msg)
                if full is None:
                    # partial piece; wait for the rest before acting
                    last_seen = max(last_seen, msg["seq"])
                    continue
                handle_message(full)        # act on the complete (possibly reassembled) message
                last_seen = max(last_seen, msg["seq"])
    except KeyboardInterrupt:
        print("\n[chat_loop] shutting down")
        stop_event.set()


if __name__ == "__main__":
    main()