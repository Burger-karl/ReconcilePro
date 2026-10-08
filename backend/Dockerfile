FROM python:3.12-slim

# Don't write .pyc files; print logs straight away (no buffering) so docker logs are live.
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

WORKDIR /app

# Copy only pyproject.toml first, so the dependency layer is cached until it changes.
# ".[dev]" also installs pytest, so tests can run inside the container.
COPY pyproject.toml .
RUN pip install --no-cache-dir ".[dev]"

COPY . .

EXPOSE 8000
# Production command (Render). docker-compose overrides it with --reload for local dev.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
