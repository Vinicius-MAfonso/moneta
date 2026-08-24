#!/usr/bin/env bash
set -e

PORT_NUMBER="${PORT:-8080}"
PROCESS="${PROCESS_TYPE:-web}"

if [ "$PROCESS" = "web" ]; then
    echo "==> Running database migrations..."
    python manage.py migrate --noinput || true
    
    echo "==> Configuring Django-Q schedules..."
    python manage.py setup_schedules || true

    echo "==> Creating superuser if env vars are set..."
    python manage.py createsuperuser --noinput || true

    echo "==> Starting Gunicorn on port ${PORT_NUMBER}..."
    exec gunicorn moneta.wsgi:application \
        --bind 0.0.0.0:${PORT_NUMBER} \
        --workers 2 \
        --threads 4 \
        --timeout 120 \
        --access-logfile - \
        --error-logfile -
        
elif [ "$PROCESS" = "worker" ]; then
    echo "==> Starting dedicated Django-Q worker..."
    exec python manage.py qcluster
    
else
    echo "==> Running custom command: $@"
    exec "$@"
fi
