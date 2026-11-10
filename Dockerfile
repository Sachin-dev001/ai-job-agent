# ==============================================================================
# AutoApply Production Dockerfile
# Optimized for Headless Playwright Chromium & FastAPI
# Compatible with Hugging Face Spaces (16GB RAM Free), Render, & Fly.io
# ==============================================================================

FROM mcr.microsoft.com/playwright/python:v1.49.0-noble

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000 \
    PYTHONPATH=/app/backend

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/requirements.txt

# Ensure Playwright browser binaries are present
RUN playwright install chromium
RUN playwright install-deps chromium

# Copy full application code
COPY backend /app/backend
COPY frontend /app/frontend

# Create non-root user for security (required by Hugging Face Spaces)
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Launch FastAPI ASGI server
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
