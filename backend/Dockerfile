# ──────────────────────────────────────────────────
# Debate Coach Backend — Multi-stage Docker Build
# ──────────────────────────────────────────────────
# Stage 1: Build frontend (Vite → static files)
# Stage 2: Python runtime with static files baked in
# ──────────────────────────────────────────────────

# ── Stage 1: Build the frontend ──────────────────
FROM node:20-alpine AS frontend-build

WORKDIR /build

# Install deps first (layer cache)
COPY web/package.json web/package-lock.json ./
RUN npm ci

# Copy source and build
COPY web/ ./
COPY shared/ /shared/
RUN npm run build

# ── Stage 2: Python backend + static frontend ───
FROM python:3.12-slim AS runtime

# System deps
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps (layer cache)
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend/ ./backend/
COPY shared/ ./shared/

# Copy built frontend from stage 1
COPY --from=frontend-build /build/dist ./static/

# Set Python path so `from backend.app...` imports work
ENV PYTHONPATH=/app
ENV HOST=0.0.0.0
ENV PORT=8000

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

CMD ["python", "-m", "uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
