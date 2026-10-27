# ==========================================
# Stage 1: Build Tailwind CSS & Assets
# ==========================================
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install Node.js & build tools for Tailwind CSS compilation
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gcc \
    libpq-dev \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Install Tailwind npm dependencies & compile CSS
RUN python manage.py tailwind install --no-input
RUN python manage.py tailwind build
RUN python manage.py collectstatic --no-input

# ==========================================
# Stage 2: Lean Production Runtime Image
# ==========================================
FROM python:3.12-slim AS runner

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app

# Install only runtime Postgres/C libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code and compiled static assets from builder stage
COPY . .
COPY --from=builder /app/staticfiles /app/staticfiles
COPY --from=builder /app/theme/static/css /app/theme/static/css

EXPOSE 8080

CMD ["sh", "-c", "python manage.py migrate --noinput && (python manage.py createsuperuser --noinput || true) && exec gunicorn moneta.wsgi:application --bind 0.0.0.0:${PORT:-8080} --workers 2 --threads 4 --timeout 120 --access-logfile - --error-logfile -"]
