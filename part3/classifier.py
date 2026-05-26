from provider import chat
from config import AGENT_NAME, CLASSIFIER_PROMPT

VALID_DECISIONS = ["IGNORE", "REPLY", "TOOL_CALL", "YIELD"]


def format_chat_history(history):
    """Render recent chat messages for the classifier prompt"""

    if not history:
        return "(no prior context)"
    return "\n".join(f"[{m['agent_name']}] {m['content']}" for m in history)

def classify(incoming_msg, history):
    """return one of the valid decisions"""

    system_prompt = CLASSIFIER_PROMPT.replace("{agent_name}", AGENT_NAME)

    user_content = (
        f"Recent chat history:\n{format_chat_history(history)}\n\n"
        f"Incoming message to classify:\n"
        f"[{incoming_msg['agent_name']}] {incoming_msg['content']}"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]

    reply = chat(messages)
    decision = reply["content"].strip().upper().split()[0] if reply.get("content") else ""

    if decision not in VALID_DECISIONS:
        print(f"[classifier] unexpected output: {reply.get('content', '')!r} -> defaulting to IGNORE")
        return "IGNORE"

    return decision