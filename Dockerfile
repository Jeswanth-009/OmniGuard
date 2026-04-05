# OmniGuard API Gateway Dockerfile
# Multi-stage build for optimized production image

FROM python:3.11-slim as builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /build/wheels -r requirements.txt

# Production stage
FROM python:3.11-slim as production

# Create non-root user for security
RUN groupadd -r omniguard && useradd -r -g omniguard omniguard

WORKDIR /app

# Copy wheels from builder stage
COPY --from=builder /build/wheels /wheels
COPY --from=builder /build/requirements.txt .

# Install dependencies
RUN pip install --no-cache /wheels/*

# Copy application code
COPY app/ ./app/

# Set ownership
RUN chown -R omniguard:omniguard /app

# Switch to non-root user
USER omniguard

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health', timeout=5)" || exit 1

# Run with uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
