# syntax=docker/dockerfile:1.7

FROM ghcr.io/astral-sh/uv:0.11.16 AS uv
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/opt/venv/bin:${PATH}"

WORKDIR /app

COPY --from=uv /uv /uvx /bin/
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
COPY main.py ./

RUN groupadd --gid 10001 trainsyt \
    && useradd --uid 10001 --gid 10001 --create-home --shell /usr/sbin/nologin trainsyt \
    && chown -R trainsyt:trainsyt /app

USER trainsyt
EXPOSE 8000

# One worker intentionally owns the persisted email-reminder scheduler.
# Scale-out should first move that scheduler into a dedicated worker service.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers", "--forwarded-allow-ips=*", "--no-access-log", "--limit-concurrency", "500", "--backlog", "1024"]
