import time
import threading
from collections import deque


class Budget:
    """Tracks token spending and request rate.
    Both fields are tunable in real time.
    Thread-safe via an internal lock."""

    def __init__(self, max_tokens, max_requests_per_minute):
        self.max_tokens = max_tokens
        self.used_tokens = 0
        self.max_requests_per_minute = max_requests_per_minute
        self._request_times = deque()  # timestamps of recent requests
        self._posting_enabled = True
        self._lock = threading.Lock()

    def check_and_record(self, estimated_tokens=0):
        """Check whether a new request is allowed under both caps.
        Returns (allowed: bool, reason: str).
        If allowed, records the request time. Token usage is added later via add_usage()."""
        with self._lock:
            # Token cap check
            if self.used_tokens + estimated_tokens > self.max_tokens:
                return False, (
                    f"token cap reached "
                    f"({self.used_tokens}/{self.max_tokens})"
                )

            # Rate limit check: count requests in the last 60 seconds
            now = time.time()
            while self._request_times and now - self._request_times[0] > 60:
                self._request_times.popleft()
            if len(self._request_times) >= self.max_requests_per_minute:
                return False, (
                    f"rate limit reached "
                    f"({len(self._request_times)}/{self.max_requests_per_minute} per minute)"
                )

            # Allowed; record this request's time
            self._request_times.append(now)
            return True, ""

    def add_usage(self, tokens):
        """Record actual tokens consumed by a completed call."""
        with self._lock:
            self.used_tokens += tokens

    def set_max_tokens(self, new_max):
        with self._lock:
            self.max_tokens = new_max

    def set_rate_limit(self, new_rate):
        with self._lock:
            self.max_requests_per_minute = new_rate

    def snapshot(self):
        """Return a dict of current state, for printing."""
        with self._lock:
            return {
                "used_tokens": self.used_tokens,
                "max_tokens": self.max_tokens,
                "requests_last_minute": len(self._request_times),
                "max_requests_per_minute": self.max_requests_per_minute,
                "posting_enabled": self._posting_enabled,
            }
    
    def disable_posting(self, reason):
        with self._lock:
            if self._posting_enabled:
                self._posting_enabled = False
                return(f"[budget] posting disabled: {reason}")

    def is_posting_enabled(self):
        with self._lock:
            return self._posting_enabled