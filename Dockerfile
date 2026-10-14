FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8001

CMD [
  "sh",
  "-c",
  "echo 'Applying database migrations...' >&2; if ! alembic upgrade head; then echo 'Database migration failed; refusing to start PesaSense-AI.' >&2; exit 1; fi; exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8001}"
]