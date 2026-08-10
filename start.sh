#!/usr/bin/env bash
# start.sh

# Start the Django-Q cluster in the background
echo "Starting Django-Q cluster..."
python manage.py qcluster &

# Start Gunicorn in the foreground
echo "Starting Gunicorn..."
gunicorn moneta.wsgi --bind 0.0.0.0:$PORT
