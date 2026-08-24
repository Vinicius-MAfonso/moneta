#!/usr/bin/env bash
set -e

PORT_NUMBER="${PORT:-8080}"

echo "==> Running database migrations..."
python manage.py migrate --noinput || true

echo "==> Setting up Django-Q background schedules..."
python manage.py setup_schedules || true

echo "==> Creating superuser if env vars are present..."
python manage.py createsuperuser --noinput || true

# Start Gunicorn web server in foreground
echo "==> Starting Gunicorn on port ${PORT_NUMBER}..."
exec gunicorn moneta.wsgi:application \
    --bind 0.0.0.0:${PORT_NUMBER} \
    --workers 2 \
    --threads 4 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -
