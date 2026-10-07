from unittest.mock import MagicMock

from fastapi.testclient import TestClient

import main

client = TestClient(main.app)


def test_health_db_down(monkeypatch):
    def boom(*args, **kwargs):
        raise Exception("boom")

    monkeypatch.setattr(main.psycopg2, "connect", boom)
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["db"] == "error: boom"
    assert body["db_version"] is None


def test_health_db_connected(monkeypatch):
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value.fetchone.return_value = (
        "PostgreSQL 16.1 on x86_64",
    )
    monkeypatch.setattr(main.psycopg2, "connect", lambda *a, **k: conn)
    body = client.get("/api/health").json()
    assert body["db"] == "connected"
    assert body["db_version"] == "PostgreSQL 16.1"


def test_upload_empty_file_rejected():
    r = client.post("/api/s3/upload", files={"file": ("a.txt", b"")})
    assert r.status_code == 400


def test_upload_too_large_rejected(monkeypatch):
    monkeypatch.setattr(main, "MAX_UPLOAD_SIZE", 5)
    r = client.post("/api/s3/upload", files={"file": ("a.txt", b"0123456789")})
    assert r.status_code == 413


def test_upload_ok(monkeypatch):
    s3 = MagicMock()
    s3.generate_presigned_url.return_value = "https://example.com/signed"
    monkeypatch.setattr(main, "s3_client", s3)
    r = client.post("/api/s3/upload", files={"file": ("a.txt", b"hello", "text/plain")})
    body = r.json()
    assert r.status_code == 200
    assert body["key"].startswith("uploads/") and body["key"].endswith(".txt")
    assert body["size"] == 5
    assert body["url"] == "https://example.com/signed"
    s3.upload_fileobj.assert_called_once()
