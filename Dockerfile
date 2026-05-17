# syntax=docker/dockerfile:1.6

# ----- Stage 1: build React dashboard -----
# Node 22 needed: pnpm-lock.yaml was generated with pnpm 11.x which requires Node >= 22.13
FROM node:22-alpine AS frontend-builder
WORKDIR /build

# Recreate repo layout so vite.config.ts's relative outDir "../echo/static/dashboard" works
RUN mkdir -p /build/frontend /build/echo/static

COPY frontend/package.json frontend/pnpm-lock.yaml /build/frontend/
WORKDIR /build/frontend
# pnpm 11 hard-errors on "ignored builds" (esbuild postinstall blocked by default).
# Modern esbuild (>=0.18) ships prebuilt binaries via @esbuild/<platform> optional deps,
# so its postinstall script is no longer required — skip it with --ignore-scripts.
RUN corepack enable && pnpm install --frozen-lockfile --ignore-scripts

COPY frontend/ /build/frontend/
RUN pnpm build
# Produces /build/echo/static/dashboard/

# ----- Stage 2: Python runtime -----
FROM python:3.11-slim AS runtime
WORKDIR /app

# System packages for cryptography, psycopg2-binary, audio (Whisper input)
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies via pyproject.toml
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e .

# App code
COPY echo/ ./echo/
COPY alembic/ ./alembic/
COPY alembic.ini ./
COPY entrypoint.sh ./
RUN chmod +x ./entrypoint.sh

# React dashboard build output from Stage 1
COPY --from=frontend-builder /build/echo/static/dashboard/ ./echo/static/dashboard/

EXPOSE 8006
ENTRYPOINT ["./entrypoint.sh"]
