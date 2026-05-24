FROM python:3.11-slim

# Set working directory inside container
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . ./synology/

# Create placeholders for frontend mounting
RUN mkdir -p /app/frontend

# Expose API port
EXPOSE 9090

# Force stdout/stderr to be unbuffered to get logs in real-time
ENV PYTHONUNBUFFERED=1

# Set the working directory to where main.py resides
WORKDIR /app/synology

# Run the backend script
CMD ["python", "main.py"]
