from requests import session
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

    return f"[error: unknwon tool '{name}']"

def run_agent(user_goal):
    """Run the agent loop, given a list of messages (user and assistant)"""

    messages = [    
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_goal},
    ]
    session_path = start_session()
    print(f"session log: {session_path}")

    for iterations in range(MAX_ITERATIONS):
        assistant_message = chat(messages, tools=TOOLS)
        print(f"iteration {iterations}:")
        print("MODEL:", assistant_message)
        
        messages.append(assistant_message)

        tool_calls = assistant_message.get("tool_calls")
        if not tool_calls:
            save_session(session_path, messages)
            return assistant_message.get("content", "") or "[empty final reply]"

        for tool_call in tool_calls:
            result = execute_tool_call(tool_call)
            print(f"Tool result: ({tool_call['function']['name']}):", result)
            messages.append({"role": "tool", "tool_call_id": tool_call["id"], "content": result})

        save_session(session_path, messages)
        
    save_session(session_path, messages)
    return "[max iterations reached]"


if __name__ == "__main__":
    goal = input("What should the agent do? ")
    final = run_agent(goal)
    print("\n=== FINAL ANSWER ===")
    print(final)