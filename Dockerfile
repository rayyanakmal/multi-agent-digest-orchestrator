FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install system dependencies for PDF generation.
# - WeasyPrint stack: cairo/pango/gdk-pixbuf/libffi
# - Playwright Chromium runtime libs
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    fonts-dejavu-core \
    libcairo2 \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libffi8 \
    libgdk-pixbuf-2.0-0 \
    shared-mime-info \
    libnss3 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxshmfence1 \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Install Playwright browser for PDF fallback path.
RUN python -m playwright install chromium

# Copy application code
COPY . .

# Runtime directories are mounted in compose but should always exist.
RUN mkdir -p /app/data /app/credentials

# Create non-root user for security
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# Set environment defaults
ENV RUN_MODE=once
ENV TZ=UTC
ENV PYTHONPATH=/app

# Run entrypoint
ENTRYPOINT ["python", "-m", "src.runtime.entrypoint"]
