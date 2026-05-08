FROM python:3.12-slim AS base
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl \
    fonts-dejavu fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# DEVOPS-002 (FAZ H): Non-root user (CIS Docker Benchmark 4.1)
# UID 10001 statik — K8s securityContext.runAsUser ile uyumlu
RUN groupadd -r -g 10001 kfinans && \
    useradd -r -u 10001 -g kfinans -d /app -s /sbin/nologin kfinans

COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[dev]"

# ── development ──────────────────────────────────────────────────────────────
FROM base AS development
COPY . .
RUN chown -R kfinans:kfinans /app
USER kfinans
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ── production ────────────────────────────────────────────────────────────────
FROM base AS production
RUN pip install --no-cache-dir -e "."
COPY . .
RUN chown -R kfinans:kfinans /app
USER kfinans
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
