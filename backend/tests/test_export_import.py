from __future__ import annotations

import sqlite3

from app.db import init_db
from app.exim import export_archive, import_archive

from scripts.seed_test_db import seed_connection


def test_export_import_roundtrip(tmp_path):
    src = sqlite3.connect(str(tmp_path / "src.db"))
    src.row_factory = sqlite3.Row
    init_db(src)
    seed_connection(src)
    dest_file = tmp_path / "archive.jsonl"
    exported = export_archive(src, dest_file)
    assert exported["messages"] == 2
    assert dest_file.read_text(encoding="utf-8").splitlines()[0].find("omnimind.archive.export") > 0

    dst = sqlite3.connect(str(tmp_path / "dst.db"))
    dst.row_factory = sqlite3.Row
    init_db(dst)
    imported = import_archive(dst, dest_file)
    assert imported["messages"] == 2
    again = import_archive(dst, dest_file)
    assert again["messages"] == 2
    assert dst.execute("SELECT COUNT(*) FROM messages").fetchone()[0] == 2
    src.close()
    dst.close()
