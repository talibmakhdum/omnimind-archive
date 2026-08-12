"""Configurable PII redaction (none / min / max)."""

from __future__ import annotations

import re
from typing import Any


class PIIRedactor:
    PATTERNS = {
        "email": {
            "regex": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
            "replacement": "[EMAIL_REDACTED]",
            "level": "min",
        },
        "phone": {
            "regex": r"\b(?:\+?1[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})\b",
            "replacement": "[PHONE_REDACTED]",
            "level": "min",
        },
        "ssn": {
            "regex": r"\b(?!000|666|9\d{2})\d{3}-(?!00)\d{2}-(?!0{4})\d{4}\b",
            "replacement": "[SSN_REDACTED]",
            "level": "min",
        },
        "credit_card": {
            "regex": r"\b(?:\d{4}[-\s]?){3}\d{4}\b",
            "replacement": "[CC_REDACTED]",
            "level": "min",
        },
        "api_key": {
            "regex": r"(?:sk_|api_key=|token=)[A-Za-z0-9_-]{20,}",
            "replacement": "[API_KEY_REDACTED]",
            "level": "min",
        },
        "url_with_pii": {
            "regex": r"https?://[^\s]+@[^\s]+",
            "replacement": "[URL_REDACTED]",
            "level": "max",
        },
        "ip_address": {
            "regex": r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b",
            "replacement": "[IP_REDACTED]",
            "level": "max",
        },
        "address": {
            "regex": r"\b\d+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln|Court|Ct)\b",
            "replacement": "[ADDRESS_REDACTED]",
            "level": "max",
        },
    }

    def __init__(self, redact_level: str = "min"):
        self.redact_level = redact_level
        self.active_patterns: list[tuple[str, re.Pattern[str], str]] = []
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        self.active_patterns = []
        if self.redact_level == "none":
            return
        for key, pattern_def in self.PATTERNS.items():
            if self.redact_level == "min" and pattern_def["level"] != "min":
                continue
            self.active_patterns.append(
                (key, re.compile(pattern_def["regex"], re.IGNORECASE), pattern_def["replacement"])
            )

    def redact(self, text: str) -> tuple[str, list[str]]:
        redacted_text = text
        redacted_fields: list[str] = []
        for key, pattern, replacement in self.active_patterns:
            if pattern.search(redacted_text):
                redacted_text = pattern.sub(replacement, redacted_text)
                redacted_fields.append(key)
        return redacted_text, redacted_fields

    def redact_secrets_from_logs(self, log_dict: dict[str, Any]) -> dict[str, Any]:
        keys_to_redact = {"api_key", "secret_key", "password", "token", "cookie"}
        return {k: ("[REDACTED]" if k.lower() in keys_to_redact else v) for k, v in log_dict.items()}
