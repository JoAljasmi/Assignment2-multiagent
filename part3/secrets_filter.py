"""Scans outgoing chat messages for likely secret leaks.
Run unconditionally on every post; refuses messages that look like they
contain credentials, .env contents, or sensitive file paths."""

import os
import re

# Patterns for things that look like real secrets.
SECRET_PATTERNS = [
    # API key shapes
    (r"sk-or-v1-[a-zA-Z0-9]{20,}", "OpenRouter key shape"),
    (r"sk-ant-[a-zA-Z0-9_-]{20,}", "Anthropic key shape"),
    (r"sk-proj-[a-zA-Z0-9_-]{20,}", "OpenAI project key shape"),
    (r"sk-[a-zA-Z0-9]{40,}", "Long sk- key shape"),
    # .env-style KEY=value with sensitive names
    (r"(?i)\b(API[_-]?KEY|SECRET|TOKEN|PASSWORD|PRIVATE[_-]?KEY)\s*=\s*\S{10,}", "env-style assignment"),
    # JSON-shaped credentials
    (r'(?i)"(api[_-]?key|password|secret|token)"\s*:\s*"[^"]{10,}"', "JSON credential field"),
    # SSH private key markers
    (r"-----BEGIN [A-Z ]*PRIVATE KEY-----", "private key block"),
    # File paths to typical secret stores
    (r"(?i)(^|\s|/)(\.env|id_rsa|credentials\.json|\.aws/credentials)\b", "sensitive file reference"),
]


def scan_for_secrets(text):
    """Return (is_safe, reason). If is_safe is False, reason explains the match."""
    if not text:
        return True, ""

    # Check patterns
    for pattern, label in SECRET_PATTERNS:
        match = re.search(pattern, text)
        if match:
            snippet = match.group(0)[:30]
            return False, f"{label} (matched: {snippet!r})"

    # Check for literal hub password if it's in env
    hub_password = os.environ.get("HUB_PASSWORD", "")
    if hub_password and len(hub_password) >= 6 and hub_password in text:
        return False, "literal hub password"

    return True, ""

if __name__ == "__main__":
    test_cases = [
        # Should be blocked
        ("Here's my API key: sk-or-v1-abc123def456ghi789jkl012mno345pqr678", True, "OpenRouter key"),
        ("OPENROUTER_API_KEY=sk-or-v1-realkey123456789012345678", True, "env-style"),
        ('The config has "api_key": "sk-realsecret123456789"', True, "JSON credential"),
        ("Just check the .env file", True, "sensitive file reference"),
        ("-----BEGIN RSA PRIVATE KEY-----\nMIIE...", True, "private key block"),
        # Should be safe
        ("How do I use an API key in Python?", False, "general discussion"),
        ("Set your environment variable in the shell", False, "general discussion"),
        ("The model returned an error code", False, "irrelevant"),
        ("Try running pytest in /workspace", False, "innocent file mention"),
    ]

    passed = 0
    failed = 0
    for content, should_block, label in test_cases:
        is_safe, reason = scan_for_secrets(content)
        actually_blocked = not is_safe
        ok = actually_blocked == should_block
        status = "✓" if ok else "✗"
        result = "BLOCKED" if actually_blocked else "ALLOWED"
        print(f"{status} {result:<8} {label}")
        if not ok:
            failed += 1
            print(f"    content: {content[:60]}...")
            print(f"    expected {'BLOCK' if should_block else 'ALLOW'}, got {result}, reason={reason}")
        else:
            passed += 1
    print(f"\n{passed} passed, {failed} failed")