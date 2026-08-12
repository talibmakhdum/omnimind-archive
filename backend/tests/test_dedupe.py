import sqlite3

import pytest

from app.db import init_db
from app.dedupe import DedupeEngine, canonicalize_content, compute_fingerprint


def test_canonicalize_content():
    input_text = "Hello\r\nWorld\n\n\nFoo  \n  Bar"
    expected = "Hello\nWorld\n\nFoo\nBar"
    assert canonicalize_content(input_text) == expected


def test_compute_fingerprint():
    fp1 = compute_fingerprint("Hello", "2024-01-15T10:00:00Z", "chatgpt")
    fp2 = compute_fingerprint("Hello", "2024-01-15T10:00:00Z", "chatgpt")
    assert fp1 == fp2
    fp3 = compute_fingerprint("Goodbye", "2024-01-15T10:00:00Z", "chatgpt")
    assert fp1 != fp3


@pytest.fixture
def dedupe_engine(tmp_path):
    conn = sqlite3.connect(str(tmp_path / "test.db"))
    init_db(conn)
    return DedupeEngine(conn)


def test_dedupe_new_message(dedupe_engine):
    mid, is_dup = dedupe_engine.dedupe(
        content="Hello world",
        timestamp="2024-01-15T10:00:00Z",
        session_id="sess_1",
        source_platform="chatgpt",
        platform_message_id=None,
        export_file="test.json",
    )
    assert mid
    assert not is_dup


def test_dedupe_duplicate_message(dedupe_engine):
    mid1, is_dup1 = dedupe_engine.dedupe(
        content="Hello world",
        timestamp="2024-01-15T10:00:00Z",
        session_id="sess_1",
        source_platform="chatgpt",
        platform_message_id=None,
        export_file="test.json",
    )
    assert not is_dup1
    mid2, is_dup2 = dedupe_engine.dedupe(
        content="Hello world",
        timestamp="2024-01-15T10:00:00Z",
        session_id="sess_1",
        source_platform="chatgpt",
        platform_message_id=None,
        export_file="test.json",
    )
    assert mid1 == mid2
    assert is_dup2
