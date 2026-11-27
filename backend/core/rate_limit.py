import time
import threading
from typing import Dict, List, Optional
from fastapi import Request, HTTPException, status

class SlidingWindowRateLimiter:
    """
    Thread-safe sliding-window rate limiter tracking timestamps per client IP & path.
    Enforces window limit and burst limit.
    """
    def __init__(self, limit: int = 60, window_seconds: int = 60, burst_limit: int = 10, burst_seconds: int = 2):
        self.limit = limit
        self.window_seconds = window_seconds
        self.burst_limit = burst_limit
        self.burst_seconds = burst_seconds
        self.requests: Dict[str, List[float]] = {}
        self.lock = threading.Lock()

    def check(self, request: Request, custom_key: Optional[str] = None):
        client_ip = request.headers.get("x-forwarded-for")
        if client_ip:
            client_ip = client_ip.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "127.0.0.1"

        key = custom_key or f"{client_ip}:{request.url.path}"
        now = time.time()
        window_cutoff = now - self.window_seconds
        burst_cutoff = now - self.burst_seconds

        with self.lock:
            timestamps = self.requests.get(key, [])
            valid_timestamps = [ts for ts in timestamps if ts > window_cutoff]

            # Check burst limit
            recent_burst = [ts for ts in valid_timestamps if ts > burst_cutoff]
            if len(recent_burst) >= self.burst_limit:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail={"error": "Too many requests in a short burst. Please slow down.", "code": "RATE_LIMIT_EXCEEDED"}
                )

            # Check window limit
            if len(valid_timestamps) >= self.limit:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail={"error": "Rate limit exceeded. Please wait a moment.", "code": "RATE_LIMIT_EXCEEDED"}
                )

            valid_timestamps.append(now)
            self.requests[key] = valid_timestamps

# Rate limiter instances
# Global limiter: generous (120 req / 60s)
global_rate_limiter = SlidingWindowRateLimiter(limit=120, window_seconds=60, burst_limit=30, burst_seconds=2)

# Scan limiter: stricter (60 req / 60s, burst 8 / 2s)
scan_rate_limiter = SlidingWindowRateLimiter(limit=60, window_seconds=60, burst_limit=8, burst_seconds=2)

# Checkout limiter: stricter (30 req / 60s, burst 6 / 2s)
checkout_rate_limiter = SlidingWindowRateLimiter(limit=30, window_seconds=60, burst_limit=6, burst_seconds=2)

def check_scan_rate_limit(request: Request):
    scan_rate_limiter.check(request)

def check_checkout_rate_limit(request: Request):
    checkout_rate_limiter.check(request)
