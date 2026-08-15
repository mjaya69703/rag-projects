# ==========================================
# STAGE 1: Build Frontend SPA (React 19 + Bun)
# ==========================================
FROM oven/bun:alpine AS frontend-builder
WORKDIR /build

# Copy file dependency frontend & install
COPY frontend/package.json frontend/bun.lock* ./
RUN bun install --frozen-lockfile || bun install

# Copy source frontend & build ke app/static
COPY frontend/ ./
RUN bun run build

# ==========================================
# STAGE 2: Python Backend Runtime
# ==========================================
FROM python:3.13-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy & install Python requirements (PyTorch CPU-only).
# torch diinstall duluan dari index CPU; sentence-transformers lalu
# memakainya tanpa menarik build CUDA raksasa dari PyPI.
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt

# Copy backend application code
COPY app/ ./app/
COPY ingest.py ask.py query.py bulk_ingest.py run_dev.py ./

# Copy built static frontend assets dari Stage 1
COPY --from=frontend-builder /app/static ./app/static

# Buat folder data & uploads dengan permission yang sesuai
RUN mkdir -p uploads data data/chroma_db

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PERSIST_DIR=/app/data/chroma_db \
    UPLOAD_DIR=/app/uploads \
    DB_PATH=/app/data/chat.db

EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Command default untuk menjalankan FastAPI backend & menyajikan SPA
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
