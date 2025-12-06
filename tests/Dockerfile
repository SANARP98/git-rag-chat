# Integration Test Runner Dockerfile

FROM python:3.11-slim

# Set working directory
WORKDIR /tests

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Docker CLI for container inspection
RUN curl -fsSL https://get.docker.com -o get-docker.sh && \
    sh get-docker.sh && \
    rm get-docker.sh

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy test files
COPY integration/ ./integration/
COPY fixtures/ ./fixtures/
COPY run_all_tests.py .

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV RAG_API_URL=http://rag-pipeline:8001

# Run tests
CMD ["python", "run_all_tests.py"]
