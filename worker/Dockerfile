FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for layer caching
COPY worker/requirements.txt ./worker/requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r worker/requirements.txt

# Copy worker code
COPY worker/ ./worker/

# Copy server models (needed for database operations)
COPY server/app/models/ ./app/models/
COPY server/app/__init__.py ./app/__init__.py

# Set Python path to find app modules
ENV PYTHONPATH=/app

# Run the worker
CMD ["python", "-m", "worker.main"]
