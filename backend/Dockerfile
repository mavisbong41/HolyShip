FROM python:3.13-slim

WORKDIR /app

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

COPY backend /app/backend
COPY alembic.ini /app/alembic.ini
COPY data/bundle /app/data/bundle

CMD sh -c "alembic upgrade head && uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8000}"
