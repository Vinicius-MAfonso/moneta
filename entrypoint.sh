#!/bin/bash
set -e

# Garante que o diretório data exista (para o sqlite)
mkdir -p /app/data

if [ "$PROCESS_TYPE" = "web" ]; then
    echo "Aplicando migrações do banco de dados..."
    python manage.py migrate --noinput
    
    echo "Configurando agendamentos do Django-Q..."
    python manage.py setup_schedules

    echo "Criando super usuário (se variáveis estiverem setadas)..."
    python manage.py createsuperuser --noinput || true

    echo "Iniciando Gunicorn (Servidor Web)..."
    exec gunicorn moneta.wsgi:application --bind 0.0.0.0:8000 --workers 3
    
elif [ "$PROCESS_TYPE" = "worker" ]; then
    echo "Iniciando worker do Django-Q (Background Tasks)..."
    exec python manage.py qcluster
    
else
    echo "Erro: PROCESS_TYPE não definido ou inválido. Use 'web' ou 'worker'."
    exit 1
fi
