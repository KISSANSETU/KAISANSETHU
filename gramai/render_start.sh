#!/usr/bin/env bash
# Render start command. The free tier has no persistent disk, so the demo
# database is rebuilt whenever the instance restarts.
set -e

if [ ! -f gramai.db ]; then
  echo "[BOOT] No database found - seeding"
  python seed.py
  python migrate_quality.py
else
  echo "[BOOT] Database present"
fi

exec uvicorn app:app --host 0.0.0.0 --port "${PORT:-8000}"
