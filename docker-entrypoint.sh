#!/usr/bin/env bash
set -euo pipefail

echo "[entrypoint] running alembic upgrade head..."
python -m alembic upgrade head

echo "[entrypoint] starting app..."
exec python -m app.main
