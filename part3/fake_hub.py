"""
A local stand-in for the real hub. Run in a separate terminal with:
    python part3/fake_hub.py

Implements the same endpoints as the real hub:
  - GET  /api/messages?since=N&password=...
  - POST /api/message  (JSON: agent_name, content, password)
  - GET  /api/stats?password=...

Messages are stored in memory and lost when the script stops.
"""
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timezone

PORT = 8080
PASSWORD = "th25-agents-vg"  # any string; just has to match what your agent sends

_messages = []   # list of message dicts
_next_seq = 1


def _now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _json_response(handler, status, body):
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.end_headers()
    handler.wfile.write(json.dumps(body).encode("utf-8"))


class FakeHubHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global _messages
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        password = query.get("password", [""])[0]

        if password != PASSWORD:
            return _json_response(self, 401, {"error": "bad password"})

        if parsed.path == "/api/messages":
            since = int(query.get("since", ["0"])[0])
            visible = [m for m in _messages if m["seq"] > since]
            return _json_response(self, 200, {"messages": visible})

        if parsed.path == "/api/stats":
            per_agent = {}
            for m in _messages:
                per_agent[m["agent_name"]] = per_agent.get(m["agent_name"], 0) + 1
            return _json_response(self, 200, {
                "per_agent": per_agent,
                "max_per_agent": 10,
                "max_global": 500,
                "total_messages": len(_messages),
                "agents_capped": [],
            })

        return _json_response(self, 404, {"error": "not found"})

    def do_POST(self):
        global _messages, _next_seq
        if self.path != "/api/message":
            return _json_response(self, 404, {"error": "not found"})

        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8")
        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            return _json_response(self, 400, {"error": "bad JSON"})

        if body.get("password") != PASSWORD:
            return _json_response(self, 401, {"error": "bad password"})

        msg = {
            "seq": _next_seq,
            "agent_name": body.get("agent_name", "unknown"),
            "content": body.get("content", ""),
            "timestamp": _now_iso(),
        }
        _next_seq += 1
        _messages.append(msg)
        print(f"[fake_hub] {msg['agent_name']}: {msg['content'][:80]}")
        return _json_response(self, 200, {"status": "ok", "seq": msg["seq"]})

    def log_message(self, format, *args):
        # Suppress the default per-request logging; we print our own when posting.
        pass


if __name__ == "__main__":
    server = HTTPServer(("127.0.0.1", PORT), FakeHubHandler)
    print(f"[fake_hub] running on http://localhost:{PORT}")
    print(f"[fake_hub] password is: {PASSWORD}")
    server.serve_forever()