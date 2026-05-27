from provider import chat
from sandbox import run_bash, edit_file
from config import SYSTEM_PROMPT, MAX_ITERATIONS, TOOLS
import json
from sessions import start_session, save_session


def execute_tool_call(tool_call):
    """Execute a tool call and return the output"""
    name = tool_call["function"]["name"]
    args_json = tool_call["function"]["arguments"]

    try:
        args = json.loads(args_json)
    except json.JSONDecodeError as e:
        return f"[error: invalid JSON in tool arguments: {e}]"

    if name == "bash":
        command = args.get("command", "")
        if not command:
            return "[error: bash called with no command]"
        return run_bash(command)

    if name == "edit_file":
        path = args.get("path")
        old_text = args.get("old_text")
        new_text = args.get("new_text")
        if path is None or old_text is None or new_text is None:
            return "[error: edit_file requires path, old_text, and new_text]"
        return edit_file(path, old_text, new_text)

    return f"[error: unknown tool '{name}']"

def run_agent(user_goal, deliver, budget=None):
    """
    Run a ReAct turn. Calls deliver(text) once when the model produces a final
    user-facing reply. Does not call deliver for internal/harness states.
    Returns None.
    """
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_goal},
    ]
    session_path = start_session(user_goal)
    print(f"[agent] session log: {session_path}")

    for iteration in range(MAX_ITERATIONS):
        assistant_msg = chat(messages, tools=TOOLS, budget=budget)
        print(f"\n--- iteration {iteration} ---")
        print("MODEL:", assistant_msg)

        messages.append(assistant_msg)

        tool_calls = assistant_msg.get("tool_calls")
        if not tool_calls:
            save_session(session_path, messages)
            content = assistant_msg.get("content") or ""
            content = content.strip()
            if content:
                deliver(content)
            return

        for tool_call in tool_calls:
            result = execute_tool_call(tool_call)
            print(f"TOOL RESULT ({tool_call['function']['name']}):", result)
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call["id"],
                "content": result,
            })

        save_session(session_path, messages)

    save_session(session_path, messages)
    print("[agent] max iterations reached, no reply delivered")

    messages.append({
        "role": "user",
        "content": (
            "You've hit the iteration limit. Stop calling tools. "
            "In ONE short chat message, summarize what you did, what works, "
            "and what (if anything) is unfinished. Reply with text only — no tool calls."
        ),
    })
    final = chat(messages, tools=None, budget=budget)
    content = (final.get("content") or "").strip()
    if content:
        deliver(content)
    else:
        deliver("[agent] hit iteration limit without producing a summary.")


if __name__ == "__main__":
    goal = input("What should the agent do? ")
    print("\n=== AGENT REPLY ===")
    run_agent(goal, deliver=print)