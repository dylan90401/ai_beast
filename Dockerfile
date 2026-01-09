# =============================================================================
# AI Beast - Optimized Multi-Stage Dockerfile
# =============================================================================
# Build targets:
#   - base: System dependencies
#   - dependencies: Python packages
#   - development: Full dev environment
#   - production: Minimal runtime image
#
# Usage:
#   Development: docker build --target development -t ai-beast:dev .
#   Production:  docker build --target production -t ai-beast:latest .
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1: Base - System dependencies
# -----------------------------------------------------------------------------
FROM python:3.12-slim as base

# Prevent Python from writing bytecode and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies in a single layer
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Core utilities
    curl \
    wget \
    git \
    # Build tools (for some Python packages)
    build-essential \
    # SQLite for database
    libsqlite3-dev \
    # For healthchecks
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user for security
RUN groupadd --gid 1000 beast \
    && useradd --uid 1000 --gid beast --shell /bin/bash --create-home beast

WORKDIR /app

# -----------------------------------------------------------------------------
# Stage 2: Dependencies - Python packages
# -----------------------------------------------------------------------------
FROM base as dependencies

# Copy only dependency files for better layer caching
COPY requirements.txt ./
COPY requirements-dev.txt ./

# Install production dependencies
RUN pip install --upgrade pip setuptools wheel \
    && pip install -r requirements.txt

# -----------------------------------------------------------------------------
# Stage 3: Development - Full development environment
# -----------------------------------------------------------------------------
FROM dependencies as development

# Install development dependencies
RUN pip install -r requirements-dev.txt

# Copy application code
COPY --chown=beast:beast . .

# Install package in editable mode
RUN pip install -e .

# Development-specific settings
ENV AI_BEAST_ENV=development \
    AI_BEAST_DEBUG=1

# Create directories for volumes
RUN mkdir -p /app/data /app/models /app/logs /app/outputs \
    && chown -R beast:beast /app

USER beast

# Expose ports
EXPOSE 8787 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8787/health || exit 1

CMD ["python", "-m", "apps.dashboard.dashboard"]

# -----------------------------------------------------------------------------
# Stage 4: Builder - Build production artifacts
# -----------------------------------------------------------------------------
FROM dependencies as builder

# Copy application code
COPY . .

# Install package
RUN pip install --no-deps .

# Compile Python files for faster startup
RUN python -m compileall -b modules apps beast 2>/dev/null || true

# -----------------------------------------------------------------------------
# Stage 5: Production - Minimal runtime image
# -----------------------------------------------------------------------------
FROM python:3.12-slim as production

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    AI_BEAST_ENV=production

# Install only runtime dependencies (no build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    netcat-openbsd \
    libsqlite3-0 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user
RUN groupadd --gid 1000 beast \
    && useradd --uid 1000 --gid beast --shell /bin/bash --create-home beast

WORKDIR /app

# Copy Python packages from dependencies stage
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy only necessary application files
COPY --from=builder --chown=beast:beast /app/modules ./modules
COPY --from=builder --chown=beast:beast /app/apps ./apps
COPY --from=builder --chown=beast:beast /app/beast ./beast
COPY --from=builder --chown=beast:beast /app/config ./config
COPY --from=builder --chown=beast:beast /app/pyproject.toml ./
COPY --from=builder --chown=beast:beast /app/VERSION ./

# Create directories for runtime data
RUN mkdir -p /app/data /app/logs /app/outputs \
    && chown -R beast:beast /app

USER beast

EXPOSE 8787

# Production health check
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8787/health || exit 1

CMD ["python", "-m", "apps.dashboard.dashboard"]
