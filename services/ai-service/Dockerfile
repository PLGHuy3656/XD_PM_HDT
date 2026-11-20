FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY services/ai-service/requirements.txt .
RUN pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu torch torchvision \
    && pip install --no-cache-dir -r requirements.txt

# Copy ai-pipeline library and configs to /ai-pipeline
COPY ai-pipeline /ai-pipeline
# INT02: reproducible SYNTHETIC demo fixtures (generated, never committed) for DEMO_VIDEO sessions
RUN python /ai-pipeline/scripts/generate_test_fixtures.py

# Copy ai-service source to /app
COPY services/ai-service/app ./app
COPY services/ai-service/database ./database
COPY services/ai-service/demo ./demo
COPY services/ai-service/eval ./eval
COPY services/ai-service/.env.example ./.env.example

ENV AI_LOAD_CONFIGURED_CAMERAS=true \
    RABBITMQ_ENABLED=true \
    AI_RUNTIME_INTERNAL_ENABLED=false \
    AI_CAMERA_CONTROL_REQUIRE_AUTH=true

EXPOSE 8003

HEALTHCHECK --interval=10s --timeout=5s --retries=5 --start-period=15s \
    CMD curl -f http://localhost:8003/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8003"]
