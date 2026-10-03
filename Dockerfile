# syntax=docker/dockerfile:1.7

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt ./
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --timeout 300 -r requirements.txt

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
COPY main.py ./

RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin trainsyt \
    && chown -R trainsyt:trainsyt /app

USER trainsyt
EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]
