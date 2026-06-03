#!/usr/bin/env bash
set -Eeuo pipefail

mkdir -p "${DATA_DIR:-/data}" "${BACKUP_DIR:-/backups}" /var/log/asterisk /var/run/asterisk

if [[ -d /opt/asterisk-defaults && ! -f /etc/asterisk/asterisk.conf ]]; then
  cp -a /opt/asterisk-defaults/. /etc/asterisk/
fi

if command -v asterisk >/dev/null 2>&1; then
  asterisk -f -vvv &
fi

exec uvicorn app.main:app --host 0.0.0.0 --port "${WEB_PORT:-8080}"
