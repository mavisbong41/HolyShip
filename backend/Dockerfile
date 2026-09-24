FROM python:3.13-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

COPY backend /app/backend
COPY alembic.ini /app/alembic.ini
COPY data/bundle /app/data/bundle

CMD sh -c "alembic upgrade heads && uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8000}"
