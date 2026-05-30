# Multi-Agent Software Engineering Agent

A Python AI agent built from scratch over three iterations for an AI engineering
course. No agent frameworks (LangChain, LangGraph, etc.) allowed — every
component is hand-rolled: the ReAct loop, the tool-calling harness, the context
management, the safety filtering, the multi-agent coordination.

The repo contains all three parts so the evolution is visible.

## The three parts

### Part 1: A ReAct agent with home-rolled function calling
[`part1/`](./part1)

A single-turn agent that takes a goal, reasons about it, and runs bash commands
inside a sandboxed Docker container until it produces a final answer. Tool
calls happen through plain text: the model outputs `<tool>bash</tool>` and
`<command>...</command>` tags, and the harness parses them with string ops —
no JSON, no SDK function-calling features. The point was to feel the bones
of an agent loop before any abstraction.

Key files:
- `agent.py` — the ReAct loop and tag parser
- `sandbox.py` — `docker exec` wrapper with `y/n` approval
- `provider.py` — direct HTTP call to OpenRouter

### Part 2: Structured tool calls, file editing, session persistence
[`part2/`](./part2)

Switched from text-tag parsing to OpenAI-style structured `tool_calls`, but
the agent loop, context management, and tool execution are still hand-rolled.
Added:
- A second tool, `edit_file`, that replaces exactly one occurrence of a string
  in a file (with strict path containment under `/workspace`).
- A regex-based `DANGEROUS_PATTERNS` filter that blocks destructive shell
  commands before they even reach the approval prompt.
- Output truncation at `MAX_OUTPUT_CHARS`, with a visible marker so the model
  knows to issue more targeted commands.
- System prompt loaded from `config.json` rather than hardcoded.
- Persistent session history written to timestamped JSON files.
- Multi-round tool calling — the model decides when to yield by returning a
  response with no tool calls.

### Part 3: Multi-agent collaboration over a shared hub
[`part3/`](./part3)

The agent joins a shared group chat with other students' agents. No more
console conversation — input comes from the chat hub, and the local console
is used only for approving sandboxed commands. Everything from Part 2 still
applies, plus a lot of new structure to make multi-agent collaboration
actually work.

What got added:

- **Three-path message routing.** Each incoming message flows through
  role detection → wake-up check → general classifier. The bot reacts
  differently to role assignments, deliverable hand-offs, and casual chat.
- **LLM-based intent classifier.** Decides `IGNORE` / `REPLY` / `TOOL_CALL` /
  `YIELD` for every message before any expensive ReAct loop runs. Prevents
  the reply-storm where every agent answers every message.
- **Role + dependency state.** When assigned a role like "developer waiting
  for the planner," the bot briefly claims it in chat and then stays silent
  until the planner's deliverable lands, instead of inventing its own spec.
- **Standby mode.** When a human says "all agents stop," the bot detects it
  and silently drops every subsequent message until told to resume.
- **Live-controllable rate and token limits.** A console thread accepts
  commands (`tokens N`, `rate N`, `standby`, `resume`, `status`) to retune
  budgets mid-run without restarting. Same thread routes `y/n` approvals
  to `run_bash` through a `queue.Queue` to avoid stdin races.
- **Outgoing secrets filter.** Every message scanned before posting; API
  keys, `.env` contents, the hub password, and similar patterns are blocked.
- **Chunked posting.** Replies longer than the hub's 4096-char limit are
  split at paragraph or line boundaries and posted with rate-limit-respecting
  delays.
- **Multi-part reassembly.** When other agents split their deliverables
  (`(part 1/3)`, `(part 2/3)`, etc.), the bot buffers parts and acts only
  when the full message is reconstructed.
- **Pinned chat history.** Important messages (humans, direct mentions,
  role claims, code drops) survive the rolling-window eviction.
- **Trimming that preserves the system prompt.** When the message list grows
  too long, middle entries are dropped, never `messages[0]`.

Key files:
- `chat_loop.py` — polls the hub, routes messages through the three paths
- `classifier.py` — small LLM call that picks engagement category
- `agent.py` — ReAct loop with tool calls (carried from Part 2)
- `sandbox.py` — `docker exec` + safety filter (carried from Part 2)
- `hub.py` — posts/fetches with rate-limit and length guards
- `budget.py` — live-tunable token + request-rate caps
- `console_control.py` — owns stdin, routes `y/n` and console commands
- `approval.py` — queue bridge between `run_bash` and the console thread
- `secrets_filter.py` — outgoing-message scan for credential leaks

## Setup

Requirements: Python 3.11+, Docker, an OpenRouter API key.

```bash
git clone <repo>
cd part3
python -m venv .venv
.venv\Scripts\activate    # or `source .venv/bin/activate` on Linux/Mac
pip install -r requirements.txt

# Start the sandboxed container
docker run -d --name agent-sandbox --network none python:3.11 sleep infinity

# Configure
cp .env.example .env       # fill in OPENROUTER_API_KEY, HUB_URL, etc.

# Run
python chat_loop.py
```

Type `help` at the console for runtime commands. Same setup for `part1/`
and `part2/`, minus the hub configuration.

## Design choices worth noting

**Tag parsing in Part 1 → structured tool calls in Part 2.** Doing it the
hard way first made the trade-offs obvious. Tag parsing is fragile: any
extra prose around the tags breaks the harness, and the model has no
structured way to express arguments. Structured tool calls handle both
cleanly, but you only appreciate what you're getting if you've felt the
pain of the other.

**LLM-based detection for fuzzy intent, regex for hard safety.** The
classifier and role detector use small LLM calls (they need to understand
meaning). Dangerous-command filtering is regex (no judgment involved). Mix
the two and you get the wrong properties from each.

**Private workspace, shared chat.** Each agent has its own Docker
container, so files don't transfer between agents — the chat is the only
shared medium. The bot is explicitly prompted to paste full code in chat
rather than reference paths other agents can't see.

**Two threads owning stdin is a bug.** An earlier Part 3 version had both
the approval prompt and the console reading from `input()`, which raced.
Fixed by giving the console exclusive stdin access and having `run_bash`
request approval through a `queue.Queue`.

## What I learned

Building this by hand made the failure modes of agent systems concrete:
identity drift when prompt placeholders aren't substituted, deadlock when
wait-conditions never clear, silent dropout when rate-limit handling
conflates "transient" with "permanent," reply-storms when every agent
answers every message. Each one needed a real fix in code, not a
configuration tweak.

The lesson I keep coming back to: agent frameworks hide exactly the
things you most need to understand. The harness, the loop, the context
truncation, the safety filtering — these aren't implementation details,
they're the design. Building them yourself once is worth more than reading
ten tutorials.