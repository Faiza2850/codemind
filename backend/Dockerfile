FROM python:3.11-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Create data directories
RUN mkdir -p /app/data/uploads /app/data/indexes

# Pre-download CodeBERT so it's baked into the image
RUN python3 -c "from transformers import AutoTokenizer, AutoModel; \
    AutoTokenizer.from_pretrained('microsoft/codebert-base'); \
    AutoModel.from_pretrained('microsoft/codebert-base')" || true

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]