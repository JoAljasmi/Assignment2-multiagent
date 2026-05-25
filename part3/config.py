import json
from pathlib import Path
import os
from dotenv import load_dotenv

CONFIG_PATH = Path(__file__).parent / "config.json"
load_dotenv(Path(__file__).parent.parent / ".env")
HUB_PASSWORD = os.getenv("HUB_PASSWORD")

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    _config = json.load(f)

# Provider
PROVIDER_URL = _config["provider"]["url"]
MODEL = _config["provider"]["model"]

# Agent
MAX_ITERATIONS = _config["agent"]["max_iterations"]

# Sandbox
CONTAINER_NAME = _config["sandbox"]["container_name"]
TIMEOUT_SECONDS = _config["sandbox"]["timeout_seconds"]
MAX_OUTPUT_CHARS = _config["sandbox"]["max_output_chars"]

# Tools
TOOLS = _config["tools"]

# System prompt
_prompt = _config["system_prompt"]
SYSTEM_PROMPT_RAW = "\n".join(_prompt) if isinstance(_prompt, list) else _prompt
SYSTEM_PROMPT = SYSTEM_PROMPT_RAW.replace("{max_output_chars}", str(MAX_OUTPUT_CHARS))

# Hub
HUB_URL = _config["hub"]["url"]
AGENT_NAME = _config["hub"]["agent_name"]
POLL_INTERVAL = _config["hub"]["poll_interval_seconds"]
