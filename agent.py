from provider import chat
from sandbox import run_bash

MAX_ITERATIONS = 20
SYSTEM_PROMPT = """You are a Python-based software engineering assistant running in a sandboxed Docker container. You help the user with software engineering tasks by reasoning about the problem and, when useful, running bash commands inside the sandbox.

You have access to one tool: bash.

When you want to run a bash command, output a tool call in EXACTLY this format, and nothing else in that message:

<tool>bash</tool>
<command>
your command here
</command>

Rules for tool calls:
- The tags must appear exactly as shown, lowercase, no extra spaces.
- The command goes between <command> and </command>, on its own lines.
- Do not put any other text in the same message as a tool call. No prose before or after.
- You may use multiline commands.

When you are not running a tool, just reply normally in plain prose. That signals you are done with tools for this turn and giving your final answer to the user.

Example of a tool call:
<tool>bash</tool>
<command>
ls -la /workspace
</command>

Example of a final answer:
The workspace is currently empty. Would you like me to create a starter file?

After you run a command, you will see the output as a new message. Then you can either run another command, or give your final answer.

Only work on software engineering tasks. If asked about unrelated topics, politely decline and steer back to the assignment.
"""

def parse_reply(reply):
    """Given the model's raw reply, return (kind, payload):
      - ("final", text)        if no tool call detected
      - ("tool", command_str)  if a valid tool call is found
      - ("error", message)     if a tool call is malformed (tag missing)
      """
    if "<tool>" not in reply:
        return ("final", reply.strip())

    required_tags = ["<tool>", "<command>", "</tool>", "</command>"]
    for tag in required_tags:
        if tag not in reply:
            return ("error", f"tool call missing {tag}")
    
    #searching for tools and commands
    command_start = reply.find("<command>")
    command_end = reply.find("</command>")
    command_str = reply[command_start + len("<command>"):command_end].strip()
    return ("tool", command_str)

def run_agent(user_goal):
    """Run the agent loop, given a list of messages (user and assistant)"""

    messages = [    
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_goal},
    ]

    
    for iterations in range(MAX_ITERATIONS):
        reply = chat(messages)
        print(f"iteration {iterations}:")
        print("MODEL:", reply)
        
        messages.append({"role": "assistant", "content": reply})

        kind, payload = parse_reply(reply)
    
        if kind == "final":
            return payload

        elif kind == "tool":
            output = run_bash(payload)
            print("TOOL OUTPUT:", output)
            messages.append({"role": "user", "content": output})

        elif kind == "error":
            print("PARSE ERROR:", payload)
            messages.append({"role": "user", "content": f"[parse error] {payload}"})
        
    return "[max iterations reached]"


if __name__ == "__main__":
    goal = input("What should the agent do? ")
    final = run_agent(goal)
    print("\n=== FINAL ANSWER ===")
    print(final)