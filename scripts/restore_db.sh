#!/usr/bin/env bash
# Restore SQLite (+ optional Chroma tarball). Stop API/worker first.
set -euo pipefail

DATA_DIR="${DATA_DIR:-.data}"
CHROMA_PERSIST_DIR="${CHROMA_PERSIST_DIR:-.chroma}"
DB_BACKUP="${1:?usage: restore_db.sh <archive.db> [chroma.tgz]}"
CHROMA_BACKUP="${2:-}"

mkdir -p "${DATA_DIR}"
cp -f "${DB_BACKUP}" "${DATA_DIR}/archive.db"

if [[ -n "${CHROMA_BACKUP}" ]]; then
  mkdir -p "${CHROMA_PERSIST_DIR}"
  tar -xzf "${CHROMA_BACKUP}" -C "${CHROMA_PERSIST_DIR}"
fi

echo "Restored ${DATA_DIR}/archive.db"
[[ -n "${CHROMA_BACKUP}" ]] && echo "Restored ${CHROMA_PERSIST_DIR}"
