FROM nvidia/cuda:12.1.0-base-ubuntu22.04

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 \
    python3.11-venv \
    ffmpeg \
    git \
    wget \
    gnupg2 \
    && apt-get install -y --only-upgrade gnupg2 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN python3.11 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN python -m pip install --no-cache-dir --upgrade \
    pip \
    "setuptools>=78.1.1" \
    "wheel>=0.38.1" \
 && pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directories for cache and sounds
RUN mkdir -p /app/cache /app/sounds /app/config

# Set Python to unbuffered mode for better logging
ENV PYTHONUNBUFFERED=1

# Run the application
CMD ["python", "main.py"]
