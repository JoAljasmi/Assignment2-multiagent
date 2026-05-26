"""Reads commands from stdin and updates the budget in real time.
Runs as a separate thread alongside the main polling loop.

Commands:
    status            - print current budget state
    tokens N          - set max_tokens to N
    rate N            - set max_requests_per_minute to N
    help              - show commands
"""


def run_console(budget, stop_event):
    print("[console] type 'help' for commands")
    while not stop_event.is_set():
        try:
            line = input().strip()
        except EOFError:
            return

        if not line:
            continue

        if line == "help":
            print("[console] commands: status | tokens N | rate N | help")
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
        else:
            print(f"[console] unknown command: {line}")