FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE=ingest.settings.prod

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends \
        postgresql-client \
        build-essential \
        curl \
        libpq-dev \
        python3-dev \
        gcc \
        g++ \
        pkg-config \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*
# TEMPORARILY DISABLED - ML-specific dependencies (libblas-dev, liblapack-dev, gfortran)
# Uncomment when re-enabling embedding models

# Install Python build tools first
RUN python -m pip install --upgrade pip setuptools==69.5.1 wheel

# Install Python dependencies
COPY deployment/requirements*.txt ./
ARG INSTALL_DEV=false
RUN if [ "$INSTALL_DEV" = "true" ]; then \
        pip install --no-cache-dir --timeout=600 --retries=3 -r requirements-dev.txt; \
    else \
        pip install --no-cache-dir --timeout=600 --retries=3 -r requirements.txt; \
    fi

# Copy project
COPY . .

# Copy entrypoint script
COPY deployment/docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Prestart functionality is now integrated into entrypoint.sh

# Create non-root user
RUN adduser --disabled-password --gecos '' appuser

# Create staticfiles and models directory with proper permissions
RUN mkdir -p /app/staticfiles /app/models
RUN chmod -R 755 /app/staticfiles /app/models

# TEMPORARILY DISABLED - Model downloads disabled due to large size
# Download required Hugging Face models into /app/models at build time
# We place them as /app/models/intfloat__multilingual-e5-base and /app/models/intfloat__multilingual-e5-large
# to match code that checks for model_name.replace('/', '__')
# RUN python - << 'PY'
# from huggingface_hub import snapshot_download
# import os
# 
# target_dir = "/app/models"
# os.makedirs(target_dir, exist_ok=True)
# 
# models = [
#     "intfloat/multilingual-e5-base",
#     "intfloat/multilingual-e5-large",
# ]
# 
# for repo_id in models:
#     local_name = repo_id.replace('/', '__')
#     local_dir = os.path.join(target_dir, local_name)
#     # Download snapshot directly into our target directory without symlinks
#     snapshot_download(
#         repo_id=repo_id,
#         local_dir=local_dir,
#         local_dir_use_symlinks=False,
#         ignore_patterns=["*.safetensors.index.json", "*.md", "LICENSE", "*.msgpack"]
#     )
# print("Models downloaded to:", os.listdir(target_dir))
# PY

# Set ownership and permissions for all app files including .env
RUN chown -R appuser:appuser /app
RUN chmod 644 /app/.env 2>/dev/null || true

USER appuser

# Expose port
EXPOSE 8000

# Run entrypoint
ENTRYPOINT ["/entrypoint.sh"]
