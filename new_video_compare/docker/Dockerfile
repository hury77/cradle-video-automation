# New Video Compare - Celery Workers Container
FROM python:3.9-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app

# Install system dependencies for video/audio processing
RUN apt-get update && apt-get install -y \
    # FFmpeg and media libraries
    ffmpeg \
    # OpenCV dependencies
    libsm6 \
    libxext6 \
    libxrender-dev \
    libglib2.0-0 \
    libgl1-mesa-glx \
    libgthread-2.0-0 \
    # Video codec libraries
    libavcodec-dev \
    libavformat-dev \
    libswscale-dev \
    libv4l-dev \
    libxvidcore-dev \
    libx264-dev \
    # Image processing libraries
    libjpeg-dev \
    libpng-dev \
    libtiff-dev \
    # Scientific computing
    libatlas-base-dev \
    liblapack-dev \
    libopenblas-dev \
    # Audio processing
    libsndfile1-dev \
    libasound2-dev \
    # System utilities
    pkg-config \
    curl \
    wget \
    git \
    # Cleanup
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Set work directory
WORKDIR /app

# Copy and install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories with proper permissions
RUN mkdir -p /app/media /app/temp /app/logs \
    && chmod 755 /app/media /app/temp /app/logs

# Create non-root user for security
RUN groupadd -r celeryuser && useradd -r -g celeryuser celeryuser
RUN chown -R celeryuser:celeryuser /app
USER celeryuser

# Health check for Celery workers
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD celery -A backend.celery_config inspect ping || exit 1

# Default command (will be overridden in docker-compose.yml)
CMD ["celery", "-A", "backend.celery_config", "worker", "--loglevel=info"]