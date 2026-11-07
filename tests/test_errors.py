import io
import logging

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.auth import User, get_current_user
from backend.db import get_db
from backend.main import app


class Boom:
    def __init__(self, exc): self.exc = exc
    def select(self, *a, **k): raise self.exc


@pytest.fixture
def client():
    app.dependency_overrides[get_current_user] = lambda: User("A", "a@x.com")
    yield
    app.dependency_overrides.clear()


def test_upstream_http_error_is_502_without_leaking(client, caplog):
    resp = httpx.Response(500, request=httpx.Request("GET", "https://x.supabase.co/rest/v1/profiles?secret=1"),
                          text="SECRET-BODY")
    app.dependency_overrides[get_db] = lambda: Boom(httpx.HTTPStatusError("bad", request=resp.request, response=resp))
    with caplog.at_level(logging.ERROR, logger="calorific"):
        r = TestClient(app).get("/api/profile")
    assert r.status_code == 502 and "unavailable" in r.json()["detail"]
    assert "SECRET" not in r.text and "SECRET" not in caplog.text and "secret=1" not in caplog.text
    assert "status=500" in caplog.text


def test_network_error_is_502(client):
    app.dependency_overrides[get_db] = lambda: Boom(httpx.ConnectError("down"))
    assert TestClient(app).get("/api/profile").status_code == 502


def test_unexpected_exception_is_generic_500(client, caplog):
    app.dependency_overrides[get_db] = lambda: Boom(RuntimeError("password=hunter2"))
    with caplog.at_level(logging.ERROR, logger="calorific"):
        r = TestClient(app, raise_server_exceptions=False).get("/api/profile")
    assert r.status_code == 500 and r.json() == {"detail": "Something went wrong. Please try again."}
    assert "hunter2" not in r.text and "hunter2" not in caplog.text and "RuntimeError" in caplog.text


def test_oversized_photo_rejected_before_auth_or_parsing():
    c = TestClient(app)
    big = b"\xff\xd8\xff" + b"0" * 2_100_000
    r = c.post("/api/analyze/photo", files={"image": ("a.jpg", io.BytesIO(big), "image/jpeg")})
    assert r.status_code == 413 and "too large" in r.json()["detail"]


def test_photo_without_content_length_rejected():
    def chunks():
        yield b"--x\r\n"
    r = TestClient(app).post("/api/analyze/photo", content=chunks(), headers={"content-type": "multipart/form-data; boundary=x"})
    assert r.status_code == 411


def test_other_routes_unaffected_by_upload_limit():
    assert TestClient(app).get("/api/health").status_code == 200
    assert TestClient(app).post("/api/analyze/text", json={"text": "x" * 5}).status_code == 401
