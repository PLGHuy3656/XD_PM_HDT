FROM python:3.11-slim

WORKDIR /app

# Install curl for container HEALTHCHECK
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source & schema
COPY app ./app
COPY database ./database
COPY .env.example ./.env.example

ENV PYTHONUNBUFFERED=1 \
    SERVICE_PORT=8001 \
    SERVICE_HOST=0.0.0.0

EXPOSE 8001

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
  CMD curl --fail http://localhost:8001/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
