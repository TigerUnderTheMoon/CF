# syntax=docker/dockerfile:1

# ── Builder ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_VERSION=1.8.5 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# 1. Install system build deps and Poetry into a dedicated virtual env
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/* \
    && python -m venv /opt/venv \
    && pip install --no-cache-dir --upgrade pip setuptools wheel \
    && pip install --no-cache-dir poetry==${POETRY_VERSION}

# 2. Copy dependency declarations first → layer cache
COPY pyproject.toml poetry.lock* ./

# 3. Lock & install production dependencies only (no dev, no root)
RUN poetry lock --no-interaction \
    && poetry install --without dev --no-root --no-interaction --no-ansi

# ── Runtime ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH="/app"

WORKDIR /app

# 4. Create non-root user with stable UID/GID to avoid permission issues
RUN groupadd --gid 1000 fma \
    && useradd --uid 1000 --gid fma --create-home --home-dir /home/fma fma \
    && mkdir -p /app/outputs \
    && chown -R fma:fma /app /home/fma

# 5. Copy only the virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# 6. Copy source code owned by non-root user
COPY --chown=fma:fma . .

USER fma

CMD ["python", "-m", "pytest", "-q"]
