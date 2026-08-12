from app.redactor import PIIRedactor


def test_min_redacts_email_and_phone():
    r = PIIRedactor("min")
    text, fields = r.redact("Email me at ada@example.com or 415-555-1212")
    assert "[EMAIL_REDACTED]" in text
    assert "[PHONE_REDACTED]" in text
    assert "email" in fields
    assert "phone" in fields


def test_none_keeps_pii():
    r = PIIRedactor("none")
    text, fields = r.redact("ada@example.com")
    assert text == "ada@example.com"
    assert fields == []


def test_log_secret_redaction():
    r = PIIRedactor("min")
    out = r.redact_secrets_from_logs({"api_key": "sk_live_xxx", "ok": 1})
    assert out["api_key"] == "[REDACTED]"
    assert out["ok"] == 1
