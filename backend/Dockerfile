# Adaptive Memory Engine (AME) - Backend Production Image

# Stage 1: Build compilation
FROM python:3.10-slim as builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --user --no-cache-dir -r requirements.txt

# Stage 2: Runtime image production execution
FROM python:3.10-slim as runner

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy packages from compilation stage
COPY --from=builder /root/.local /root/.local
COPY . .

ENV PATH=/root/.local/bin:$PATH
ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["uvicorn", "app.presentation.main:app", "--host", "0.0.0.0", "--port", "8000"]
