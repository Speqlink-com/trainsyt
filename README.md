# TrainSyt API

FastAPI authentication service for the Jubilee Learning Hub. The default stack runs PostgreSQL 16, applies Alembic migrations, seeds the first super administrator, and then starts the API.

## Run with Docker

Copy `.env.example` to `.env` and replace every placeholder secret. The local `.env` in this workspace is already configured for development.

```bash
docker compose up --build
```

The API is available at `http://127.0.0.1:8000`, with readiness at `/health/ready` and OpenAPI documentation at `/docs`.

Authentication emails use Zuri's direct Zoho SMTP pattern: configure `ZOHO_EMAIL`, `ZOHO_APP_PASSWORD`, `EMAIL_FROM`, `SMTP_HOST=smtp.zoho.com`, `SMTP_PORT=587`, and `SMTP_STARTTLS=true`. Set `EMAIL_DELIVERY_MODE=smtp` for real delivery. Tests and local workflows that must not send email can use `EMAIL_DELIVERY_MODE=console`; message contents and security codes are never written to logs.

Test the configured sender without creating a user:

```bash
docker compose exec api python -m app.scripts.test_email
```

Pass an optional recipient address to test delivery to a specific mailbox.

For reload-on-change development:

```bash
docker compose -f compose.yml -f compose.dev.yml up --build
```

For production settings:

```bash
docker compose -f compose.yml -f compose.prod.yml up --build -d
```

Production startup deliberately fails if secure cookies, SMTP, strong JWT/bootstrap secrets, or a strong seeded-admin password are missing. Put TLS in front of the API and set `CORS_ORIGINS`, `TRUSTED_HOSTS`, `FRONTEND_URL`, and optionally `COOKIE_DOMAIN` to the deployed domains.

## Database lifecycle

The `migrate` service waits for PostgreSQL, runs `alembic upgrade head`, and executes `python -m app.scripts.seed_admin`. The seed is idempotent: it creates `SEED_ADMIN_EMAIL` only when absent and never overwrites an existing password.

Useful commands:

```bash
docker compose run --rm migrate
docker compose exec api alembic current
docker compose exec postgres psql -U trainsyt -d trainsyt
```

Create migrations locally after changing models:

```bash
uv run alembic revision --autogenerate -m "describe change"
uv run alembic upgrade head
uv run alembic check
```

## Authentication contract

Authentication uses short-lived access JWTs and rotating refresh JWTs in `HttpOnly` cookies. State-changing authenticated requests also require the readable `csrf_token` cookie value in the `X-CSRF-Token` header. The browser client must send requests with credentials enabled.

Main endpoints:

- `POST /api/auth/login`
- `POST /api/auth/first-time-password-change`
- `POST /api/auth/refresh`
- `POST /api/auth/logout`
- `GET /api/auth/check-auth`
- `PUT /api/auth/change-password`
- `POST /api/auth/forgot-password`
- `POST /api/auth/reset-password`
- `GET|POST /api/auth/users` for administrators
- `POST /api/auth/users/{id}/resend-invitation` for administrators
- `PATCH /api/auth/users/{id}/status` for administrators

Administrators create accounts through `POST /api/auth/users`. A random temporary password is emailed through the configured SMTP provider. The invited user must replace it at first login before a normal session is issued. Deactivation, password changes, password resets, and refresh-token replay revoke active sessions.

## QR training attendance

Administrators can assign programmes to active trainers, while trainers can create and manage their own programmes. Every programme receives an unguessable public code used by its shareable QR link. Participants do not need a platform account: the link accepts their name, email, phone, role, and role-specific code, prevents duplicate identities, enforces role eligibility and capacity, then issues a short-lived signed receipt used to mark attendance. The API rejects attendance before the scheduled meeting time even if a client bypasses the browser controls.

The API process also runs a persisted reminder scheduler. Every minute it finds programmes entering the configured 60-minute window and emails the assigned trainer plus registered participants. Successful deliveries are recorded on the programme/registration so restarts and later polling cycles do not resend them. Configure this with `TRAINING_REMINDERS_ENABLED`, `TRAINING_REMINDER_MINUTES`, `TRAINING_REMINDER_POLL_SECONDS`, and `APP_TIMEZONE`.

Authenticated trainer and administrator endpoints:

- `GET|POST /api/trainings`
- `GET /api/trainings/trainers`
- `GET|PATCH|DELETE /api/trainings/{id}` (update/delete are administrator-only)
- `PATCH /api/trainings/{id}/status`
- `GET /api/trainings/attendance`
- `GET /api/trainings/attendance/export.xlsx`

Public QR endpoints:

- `GET /api/public/trainings/{public_code}`
- `POST /api/public/trainings/{public_code}/registrations`
- `POST /api/public/trainings/{public_code}/attendance`

Trainer queries and Excel exports are always restricted to programmes assigned to that trainer. Administrator exports may cover all programmes. The `.xlsx` response contains the joined and present counts plus a filterable participant register with typed date/time cells.

## Local checks

```bash
uv sync --all-groups
uv run ruff check .
uv run pytest -q
```

The tests use an isolated SQLite database while production and Docker use PostgreSQL through `psycopg`.

## VPS deployment

Production deployment through the VPS GitHub runner is defined in `.github/workflows/deploy.yml`. It builds an immutable image, backs up PostgreSQL, applies Alembic migrations, seeds the administrator idempotently, and health-checks the API. See [docs/deployment.md](docs/deployment.md) for the one-time server, Cloudflare, and GitHub environment setup.
