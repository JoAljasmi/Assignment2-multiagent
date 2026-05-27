"""Bridge between run_bash (needs y/n) and the console thread (owns stdin)."""
import queue

# run_bash puts the command here when it wants approval
pending = queue.Queue()
# console puts the user's y/n response here
responses = queue.Queue()