"""Reads commands from stdin and updates the budget in real time.
Runs as a separate thread alongside the main polling loop.

Also routes y/n approval responses to run_bash via the approval queue —
since this thread is the only one that reads stdin, run_bash asks it for
approval instead of calling input() itself.

Commands:
    status            - print current budget state
    tokens N          - set max_tokens to N
    rate N            - set max_requests_per_minute to N
    disable_posting   - stop the agent from posting to the hub
    help              - show commands
"""
from approval import pending, responses


def run_console(budget, stop_event):
    print("[console] type 'help' for commands")
    while not stop_event.is_set():
        try:
            line = input().strip()
        except EOFError:
            return

        if not line:
            continue

        # If run_bash is waiting for y/n approval, treat this line as the
        # answer and route it back. Don't try to dispatch it as a console
        # command.
        if not pending.empty():
            try:
                pending.get_nowait()
            except Exception:
                pass
            responses.put(line)
            print(f"[console] approval response sent: {line!r}")
            continue

        if line == "help":
            print("[console] commands: status | tokens N | rate N | disable_posting | help")
        elif line == "status":
            print(f"[console] budget: {budget.snapshot()}")
        elif line.startswith("tokens "):
            try:
                value = int(line.split()[1])
                budget.set_max_tokens(value)
                print(f"[console] max_tokens set to {value}")
            except (ValueError, IndexError):
                print("[console] usage: tokens N")
        elif line.startswith("rate "):
            try:
                value = int(line.split()[1])
                budget.set_rate_limit(value)
                print(f"[console] max_requests_per_minute set to {value}")
            except (ValueError, IndexError):
                print("[console] usage: rate N")
        elif line == "disable_posting":
            budget.disable_posting("manual via console")
            print("[console] posting disabled")
        else:
            print(f"[console] unknown command: {line}")