from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

import main


client = TestClient(main.app)


def test_unexpected_backend_exception_returns_generic_error(monkeypatch):
    def raise_runtime_error(self):
        raise RuntimeError("Provider payload leaked: api_key=abc123 secret=topsecret")

    monkeypatch.setattr(main.GraphBuilder, "build_graph", raise_runtime_error)

    response = client.post("/plan", json={"question": "Plan a trip"})

    assert response.status_code == 500
    payload = response.json()
    assert payload["error"] == main.GENERIC_ERROR_MESSAGE
    assert "api_key" not in response.text.lower()
    assert "topsecret" not in response.text.lower()
    assert "Provider payload leaked" not in response.text


def test_raw_exception_details_are_not_exposed_in_response(monkeypatch):
    def raise_runtime_error(self):
        raise RuntimeError("Groq provider error: invalid authorization header")

    monkeypatch.setattr(main.GraphBuilder, "build_graph", raise_runtime_error)

    response = client.post("/plan", json={"question": "Plan a trip"})

    assert response.status_code == 500
    assert response.json()["error"] == main.GENERIC_ERROR_MESSAGE
    assert "authorization header" not in response.text.lower()
    assert "Groq provider error" not in response.text


def test_sse_error_event_does_not_expose_raw_exception_details(monkeypatch):
    def raise_runtime_error(self):
        raise RuntimeError("raw stack trace or provider details should stay server-side")

    monkeypatch.setattr(main.GraphBuilder, "build_graph", raise_runtime_error)

    response = client.post("/plan/stream", json={"question": "Plan a trip"})

    assert response.status_code == 200
    body = "".join(response.iter_text())
    assert main.GENERIC_ERROR_MESSAGE in body
    assert "raw stack trace or provider details should stay server-side" not in body


def test_cors_allows_localhost_frontend_origin():
    response = client.options(
        "/plan",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_cors_uses_explicit_origins_and_not_wildcard():
    cors_middleware = next(
        middleware for middleware in main.app.user_middleware if middleware.cls is CORSMiddleware
    )

    assert cors_middleware.kwargs["allow_credentials"] is True
    assert "*" not in cors_middleware.kwargs["allow_origins"]
    assert "http://localhost:5173" in cors_middleware.kwargs["allow_origins"]
    assert "http://127.0.0.1:5173" in cors_middleware.kwargs["allow_origins"]
