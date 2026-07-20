"""Tests for the public-demo protection middleware (build step 8): small
request-size limits and basic rate limiting. Uses a throwaway app instance
per test — never the shared production `app` singleton — so exhausting a
rate-limit budget here can't bleed into other tests in the same session."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from invoiceguardian.api.middleware import RateLimitMiddleware, RequestSizeLimitMiddleware


def _make_app(
    *, max_body_bytes: int = 1024, limit: int = 3, window_seconds: float = 60.0
) -> FastAPI:
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, limit=limit, window_seconds=window_seconds)
    app.add_middleware(RequestSizeLimitMiddleware, max_body_bytes=max_body_bytes)

    @app.get("/ping")
    def ping() -> dict[str, str]:
        return {"pong": "ok"}

    return app


def test_requests_under_the_limit_pass_through() -> None:
    client = TestClient(_make_app())
    for _ in range(3):
        assert client.get("/ping").status_code == 200


def test_requests_over_the_rate_limit_get_429() -> None:
    client = TestClient(_make_app(limit=3))
    codes = [client.get("/ping").status_code for _ in range(5)]
    assert codes == [200, 200, 200, 429, 429]


def test_oversized_request_body_gets_413() -> None:
    client = TestClient(_make_app(max_body_bytes=10))
    response = client.get("/ping", headers={"content-length": "999999"})
    assert response.status_code == 413


def test_request_within_size_limit_passes() -> None:
    client = TestClient(_make_app(max_body_bytes=10))
    response = client.get("/ping", headers={"content-length": "5"})
    assert response.status_code == 200
