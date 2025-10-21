# syntax=docker/dockerfile:1

# Use a slim Python base image
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
	PYTHONUNBUFFERED=1 \
	PIP_NO_CACHE_DIR=1 \
	DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# System dependencies commonly required for scientific Python stacks and PyQt/matplotlib
RUN apt-get update \
	&& apt-get install -y --no-install-recommends \
	   build-essential \
	   gcc \
	   g++ \
	   git \
	   curl \
	   libgl1 \
	   libglib2.0-0 \
	   libxrender1 \
	   libxext6 \
	   libsm6 \
	   libgomp1 \
	&& rm -rf /var/lib/apt/lists/*

# Copy only requirements first to leverage Docker cache
COPY requirements.txt ./

# Install Python dependencies
# gunicorn is added here to run the app in production; gevent is already in requirements
RUN pip install --no-cache-dir -r requirements.txt \
	&& pip install --no-cache-dir gunicorn

# Copy the rest of the application code
COPY . .

# Create runtime directories that the app expects and ensure permissions
RUN mkdir -p /app/tools/filtered \
	&& mkdir -p /app/database \
	&& mkdir -p /app/pdbs \
	&& mkdir -p /app/psfs

# Optional: create a non-root user for better security
RUN useradd -m appuser \
	&& chown -R appuser:appuser /app
USER appuser

# Environment defaults (override at runtime with -e)
ENV HOST=0.0.0.0 \
	PORT=5001 \
	DEBUG=0 \
	PROJECT_ROOT=/app \
	QT_QPA_PLATFORM=offscreen \
	MPLBACKEND=Agg

# Expose the Flask port
EXPOSE 5001

# Health check hitting the lightweight health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD curl -fsS http://localhost:5001/v2/health || exit 1

# Default command: run via gunicorn using the WSGI entry point
# You can switch to the Flask dev server by overriding the CMD at runtime
CMD ["gunicorn", "-w", "2", "-k", "gevent", "-b", "0.0.0.0:5001", "wsgi_v2:application"]

