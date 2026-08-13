from __future__ import annotations

import io
import json

import pytest
from app.validation import ALLOWED_MIME, UploadValidationError, sniff_mime, validate_upload


def test_allowed_mime_constant():
    assert "application/json" in ALLOWED_MIME
    assert "application/pdf" in ALLOWED_MIME


def test_sniff_json_and_png():
    assert sniff_mime(b'{"ok": true}') == "application/json"
    assert sniff_mime(b"\x89PNG\r\n\x1a\nrest") == "image/png"
    assert sniff_mime(b"%PDF-1.7") == "application/pdf"
    assert sniff_mime(b"\xff\xd8\xff\xe0") == "image/jpeg"
    assert sniff_mime(b"MZ\x90") == "application/octet-stream"


def test_validate_json_ok():
    payload = json.dumps({"conversations": []}).encode()
    assert validate_upload(payload, filename="export.json", declared_mime="application/json") is True
    assert validate_upload(io.BytesIO(payload), filename="export.json") is True


def test_validate_rejects_exe_and_mismatch():
    with pytest.raises(UploadValidationError, match="Unsupported"):
        validate_upload(b"MZ executable", filename="x.bin")
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
    with pytest.raises(UploadValidationError, match="Extension"):
        validate_upload(png, filename="not-an-image.json")


def test_validate_rejects_oversize():
    data = b'{"a": 1}'
    with pytest.raises(UploadValidationError, match="too large") as exc:
        validate_upload(data, max_bytes=4)
    assert exc.value.status_code == 413


def test_validate_rejects_empty():
    with pytest.raises(UploadValidationError, match="Empty"):
        validate_upload(b"")


def test_require_json_rejects_png():
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
    with pytest.raises(UploadValidationError, match="JSON export required"):
        validate_upload(png, filename="x.png", require_json_object=True)
