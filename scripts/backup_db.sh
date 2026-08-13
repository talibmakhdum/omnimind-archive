#!/usr/bin/env bash
# Safe SQLite + Chroma backup (WAL-friendly).
set -euo pipefail

DATA_DIR="${DATA_DIR:-.data}"
CHROMA_PERSIST_DIR="${CHROMA_PERSIST_DIR:-.chroma}"
DEST="${1:-./backups}"
STAMP="$(date -u +%F)"
DB="${DATA_DIR}/archive.db"

mkdir -p "${DEST}"

if [[ ! -f "${DB}" ]]; then
  echo "No database at ${DB}" >&2
  exit 1
fi

if command -v sqlite3 >/dev/null 2>&1; then
  sqlite3 "${DB}" ".backup '${DEST}/archive-${STAMP}.db'"
else
  # Fallback: copy after a brief lock via Python
  python3 - <<PY
import sqlite3
src = sqlite3.connect("${DB}")
dst = sqlite3.connect("${DEST}/archive-${STAMP}.db")
src.backup(dst)
dst.close()
src.close()
PY
fi

if [[ -d "${CHROMA_PERSIST_DIR}" ]]; then
  tar -czf "${DEST}/chroma-${STAMP}.tgz" -C "${CHROMA_PERSIST_DIR}" .
fi

echo "Wrote ${DEST}/archive-${STAMP}.db"
[[ -f "${DEST}/chroma-${STAMP}.tgz" ]] && echo "Wrote ${DEST}/chroma-${STAMP}.tgz"
