#!/usr/bin/env bash
# exit on error
set -o errexit

echo "Installing Python dependencies..."
pip install -r requirements.txt

echo "Installing Tailwind dependencies..."
python manage.py tailwind install --no-input

echo "Building Tailwind CSS..."
python manage.py tailwind build

echo "Collecting static files..."
python manage.py collectstatic --no-input

echo "Running database migrations..."
python manage.py migrate
