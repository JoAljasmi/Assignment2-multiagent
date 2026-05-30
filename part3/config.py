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

# Hub
HUB_URL = _config["hub"]["url"]
AGENT_NAME = _config["hub"]["agent_name"]
POLL_INTERVAL = _config["hub"]["poll_interval_seconds"]

# System prompt
_prompt = _config["system_prompt"]
SYSTEM_PROMPT_RAW = "\n".join(_prompt) if isinstance(_prompt, list) else _prompt
SYSTEM_PROMPT = SYSTEM_PROMPT_RAW.replace("{max_output_chars}", str(MAX_OUTPUT_CHARS))
SYSTEM_PROMPT = SYSTEM_PROMPT.replace("{agent_name}", AGENT_NAME)

# Classifier prompt
_classifier = _config["classifier_prompt"]
CLASSIFIER_PROMPT_RAW = "\n".join(_classifier) if isinstance(_classifier, list) else _classifier
CLASSIFIER_PROMPT = CLASSIFIER_PROMPT_RAW.replace("{max_output_chars}", str(MAX_OUTPUT_CHARS))

#tokens
MAX_TOKENS_DEFAULT = _config["agent"]["max_tokens_default"]
MAX_REQUESTS_PER_MINUTE_DEFAULT = _config["agent"]["max_requests_per_minute_default"]

MAX_RESPONSES_PER_RUN = _config["hub"]["max_responses_per_run"]
DRY_RUN = _config["hub"]["dry_run"]
