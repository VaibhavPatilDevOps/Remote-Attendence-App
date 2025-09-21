# Use official Python base image
FROM python:3.12-slim

# Set working directory
WORKDIR /usr/src/app

# Install system dependencies (optional: for psycopg2, MySQL, etc.)
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for caching
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose application port (adjust if different)
EXPOSE 5000

# Run the application
CMD ["python", "app.py"]
