#!/bin/bash
set -e

mkdir -p /app/data

if [ "$PROCESS_TYPE" = "web" ]; then
    echo "Applying database migrations..."
    python manage.py migrate --noinput
    
    echo "Configuring Django-Q schedules..."
    python manage.py setup_schedules

    echo "Creating superuser (if variables are set)..."
    python manage.py createsuperuser --noinput || true

    echo "Starting Gunicorn (Web Server)..."
    exec gunicorn moneta.wsgi:application --bind 0.0.0.0:8000 --workers 3
    
elif [ "$PROCESS_TYPE" = "worker" ]; then
    echo "Starting Django-Q worker (Background Tasks)..."
    exec python manage.py qcluster
    
else
    echo "Error: PROCESS_TYPE not defined or invalid. Use 'web' or 'worker'."
    exit 1
fi
