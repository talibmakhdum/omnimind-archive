"""Upload validation: size, extension, MIME sniffing (no libmagic required)."""

from __future__ import annotations

import json
from typing import BinaryIO

ALLOWED_MIME = {
    "image/png",
    "image/jpeg",
    "application/pdf",
    "application/json",
}

ALLOWED_EXTENSIONS = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".pdf": "application/pdf",
    ".json": "application/json",
}

_SIGNATURES: tuple[tuple[bytes, str], ...] = (
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"%PDF", "application/pdf"),
)

DEFAULT_MAX_BYTES = 10_000_000


class UploadValidationError(ValueError):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def _read_prefix(file_obj: BinaryIO | bytes, nbytes: int = 8192) -> tuple[bytes, bytes | None]:
    if isinstance(file_obj, (bytes, bytearray)):
        data = bytes(file_obj)
        return data[:nbytes], data
    pos = file_obj.tell()
    prefix = file_obj.read(nbytes)
    file_obj.seek(pos)
    return prefix, None


def sniff_mime(data: bytes) -> str:
    for signature, mime in _SIGNATURES:
        if data.startswith(signature):
            return mime
    stripped = data.lstrip(b"\xef\xbb\xbf \t\r\n")
    if stripped[:1] in (b"{", b"["):
        return "application/json"
    return "application/octet-stream"


def _extension_mime(filename: str | None) -> str | None:
    if not filename or "." not in filename:
        return None
    ext = "." + filename.rsplit(".", 1)[-1].lower()
    return ALLOWED_EXTENSIONS.get(ext)


def validate_upload(
    file_obj: BinaryIO | bytes,
    max_bytes: int = DEFAULT_MAX_BYTES,
    filename: str | None = None,
    declared_mime: str | None = None,
    require_json_object: bool = False,
) -> bool:
    """Return True when the upload is an allowed type and within size.

    Raises UploadValidationError on failure.
    """
    if max_bytes <= 0:
        raise UploadValidationError("max_bytes must be positive")

    prefix, full = _read_prefix(file_obj)
    if not prefix:
        raise UploadValidationError("Empty upload")

    if full is not None:
        size = len(full)
        body = full
    elif isinstance(file_obj, (bytes, bytearray)):
        size = len(file_obj)
        body = bytes(file_obj)
    else:
        pos = file_obj.tell()
        file_obj.seek(0, 2)
        size = file_obj.tell()
        file_obj.seek(pos)
        body = None

    if size > max_bytes:
        raise UploadValidationError(f"File too large ({size} > {max_bytes} bytes)", status_code=413)

    sniffed = sniff_mime(prefix)
    ext_mime = _extension_mime(filename)
    declared = (declared_mime or "").split(";")[0].strip().lower() or None

    if sniffed not in ALLOWED_MIME:
        raise UploadValidationError(f"Unsupported content type: {sniffed}")

    if ext_mime and ext_mime != sniffed:
        raise UploadValidationError(f"Extension does not match content ({ext_mime} vs {sniffed})")

    if declared and declared not in {"application/octet-stream", "binary/octet-stream"}:
        if declared not in ALLOWED_MIME:
            raise UploadValidationError(f"Unsupported declared MIME type: {declared}")
        if declared != sniffed:
            raise UploadValidationError(f"Declared MIME {declared} does not match content {sniffed}")

    if require_json_object and sniffed != "application/json":
        raise UploadValidationError("JSON export required")

    if require_json_object or sniffed == "application/json":
        payload = body if body is not None else prefix
        try:
            if body is None and not isinstance(file_obj, (bytes, bytearray)):
                pos = file_obj.tell()
                payload = file_obj.read()
                file_obj.seek(pos)
            json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise UploadValidationError("Invalid JSON payload") from exc

    return True
