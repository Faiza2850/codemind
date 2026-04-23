FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential curl git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/data/uploads /app/data/indexes

# Pre-cache CodeBERT model
RUN python3 -c "from transformers import AutoTokenizer, AutoModel; \
    AutoTokenizer.from_pretrained('microsoft/codebert-base'); \
    AutoModel.from_pretrained('microsoft/codebert-base')" || true

EXPOSE 10000

CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-10000}