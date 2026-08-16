# ==============================================================================
# STAGE 1: Build Frontend SPA (React 19 + Bun)
# ==============================================================================
FROM oven/bun:alpine AS frontend-builder
WORKDIR /build

# Copy dependency manifests & install
COPY frontend/package.json frontend/bun.lock* ./
RUN bun install --frozen-lockfile || bun install

# Copy source frontend & build ke app/static
COPY frontend/ ./
RUN bun run build

# ==============================================================================
# STAGE 2: Python Backend Runtime (FastAPI + ChromaDB + PyTorch CPU)
# ==============================================================================
FROM python:3.11-slim

WORKDIR /app

# Install runtime system utilities
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python requirements with PyTorch CPU-only first for efficiency
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt

# Pre-download model embedding agar container tidak unduh dari
# HuggingFace saat runtime (cold start cepat, aman untuk server offline).
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')"

# Pre-download reranker cross-encoder (P2-06) — sama alasannya.
RUN python -c "from sentence_transformers import CrossEncoder; CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')"

# Copy application source code & command runner
COPY app/ ./app/
COPY database/ ./database/
COPY cortex.py ./
COPY .env.example ./.env.example

# Copy compiled static frontend SPA assets from Stage 1
COPY --from=frontend-builder /app/static ./app/static

# Initialize data and upload folders
RUN mkdir -p /app/data /app/uploads /app/data/chroma_db

# Default environment configuration
ENV PYTHONUNBUFFERED=1 \
    PERSIST_DIR=/app/data/chroma_db \
    UPLOAD_DIR=/app/uploads \
    DB_PATH=/app/data/chat.db

EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start the Cortex web server
CMD ["python", "cortex.py", "serve", "--host", "0.0.0.0", "--port", "8000"]
