# syntax=docker/dockerfile:1
# ─────────────────────────────────────────────────────────────────────────────
# TitanSwarm — Production Image
# Target: linux/amd64 (DigitalOcean Droplet — standard x86_64)
# Python: 3.12-slim
# ─────────────────────────────────────────────────────────────────────────────

FROM python:3.12-slim

# Prevent .pyc files and enable unbuffered stdout/stderr (logs appear live)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# ── System dependencies ───────────────────────────────────────────────────────
# Required by: Playwright (PDF generation), lxml, Pillow, SQLite
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libnss3 \
    libnspr4 \
    libdbus-1-3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    libx11-xcb1 \
    libxcb-dri3-0 \
    gcc \
    g++ \
    git \
    curl \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# ── Python dependencies ───────────────────────────────────────────────────────
COPY requirements-prod.txt .

# Install CPU-only PyTorch first (separate index), then everything else
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
        torch==2.10.0 \
        --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements-prod.txt

# ── Playwright: install Chromium only (smallest, enough for PDF generation) ──
RUN python -m playwright install chromium --with-deps

# ── Application source ────────────────────────────────────────────────────────
COPY src/ ./src/
COPY templates/ ./templates/
COPY data/ ./data/

# Runtime directories (overridden by volume mounts in docker-compose.yml)
RUN mkdir -p /app/output /app/data /app/db

EXPOSE 8501

CMD ["streamlit", "run", "src/ui/app.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true", "--browser.gatherUsageStats=false"]
