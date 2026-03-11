FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    curl \
    build-essential \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --upgrade pip wheel \
    && pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/ \
    && pip config set global.trusted-host mirrors.aliyun.com \
    && pip config set global.timeout 300 \
    && pip config set global.retries 6 \
    && pip config set global.disable-pip-version-check true \
    && pip config set global.max-depth 10

COPY requirements.txt .
RUN pip install --no-cache-dir --progress-bar off \
    --prefer-binary \
    --use-deprecated=legacy-resolver \
    -r requirements.txt

COPY . .

RUN mkdir -p /app/data /app/uploads /app/logs

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
