"""Public-demo protections (CLAUDE.md): small request-size limits and basic
rate limiting. Hand-rolled rather than a new dependency — this is a single
process serving six canned GET endpoints, not a service that needs
distributed/Redis-backed limiting.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

DEFAULT_MAX_BODY_BYTES = 1 * 1024 * 1024  # 1 MB — generous for an app with no POST bodies
DEFAULT_RATE_LIMIT = 60  # requests
DEFAULT_RATE_WINDOW_SECONDS = 60.0


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_body_bytes: int = DEFAULT_MAX_BODY_BYTES) -> None:
        super().__init__(app)
        self.max_body_bytes = max_body_bytes

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                if int(content_length) > self.max_body_bytes:
                    return JSONResponse({"detail": "Request body too large."}, status_code=413)
            except ValueError:
                pass
        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Fixed-window-ish limiter keyed by client IP: at most `limit` requests
    per `window_seconds`, tracked in memory."""

    def __init__(
        self,
        app,
        limit: int = DEFAULT_RATE_LIMIT,
        window_seconds: float = DEFAULT_RATE_WINDOW_SECONDS,
    ) -> None:
        super().__init__(app)
        self.limit = limit
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        client_ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        hits = self._hits[client_ip]
        while hits and now - hits[0] > self.window_seconds:
            hits.popleft()
        if len(hits) >= self.limit:
            return JSONResponse({"detail": "Rate limit exceeded."}, status_code=429)
        hits.append(now)
        return await call_next(request)
