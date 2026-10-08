# TrainSyt VPS deployment

The production deployment follows the SafeSport pattern: GitHub-hosted CI runs tests, then the VPS self-hosted runner builds and pushes an immutable image, backs up PostgreSQL, applies Alembic migrations, seeds the administrator idempotently, recreates the API, and verifies its health.

The configured origins are:

- Frontend: `https://jb.training.speqlink.com`
- API: `https://trainsyt.speqlink.com`
- Authentication cookies: host-only through the frontend's same-origin `/backend` proxy

## One-time VPS preparation

The workflow deploys to `/home/deploy/apps/trainsyt`. On `deploy@vmi3226662`, prepare its TLS directory without copying certificates into Git:

```bash
install -d -m 700 /home/deploy/apps/trainsyt/certs
# Add the Cloudflare Origin Certificate files as:
# /home/deploy/apps/trainsyt/certs/cert.pem
# /home/deploy/apps/trainsyt/certs/key.pem
chmod 600 /home/deploy/apps/trainsyt/certs/key.pem
chmod 644 /home/deploy/apps/trainsyt/certs/cert.pem
```

The existing `actions-runner-jubilee` runner must be online for this repository and have the standard `self-hosted`, `linux`, and `x64` labels. Its `deploy` user needs permission to use Docker.

The stack publishes Nginx TLS on host port `2096` by default so it does not collide with SafeSport (`2053`) or Jubilee BizLead (`8443`).

## Cloudflare setup

Before enabling the public health check:

1. Create a proxied DNS record for `trainsyt.speqlink.com` pointing to the VPS public IP.
2. Create or install a Cloudflare Origin Certificate covering `trainsyt.speqlink.com` (or `*.speqlink.com`) as `cert.pem` and `key.pem` in the directory above.
3. Add a Cloudflare Origin Rule that routes `trainsyt.speqlink.com` to HTTPS port `2096`, matching the pattern already used by the other VPS applications.
4. Use Full (strict) SSL mode.
5. Confirm `https://trainsyt.speqlink.com/health/ready` returns a ready response.
6. Set the GitHub production environment variable `TRAINSYT_PUBLIC_HEALTHCHECK_ENABLED=true`.

Until step 6, deployments still perform a mandatory health check inside the API container. This permits the first deployment before the public DNS route exists.

In the Vercel frontend project, keep `NEXT_PUBLIC_API_URL=/backend`, set `API_PROXY_TARGET=https://trainsyt.speqlink.com`, and redeploy the frontend after the API DNS record is active.

## GitHub production environment

Create a GitHub environment named `production`, then configure these environment secrets:

- `TRAINSYT_DOCKERHUB_TOKEN`
- `TRAINSYT_POSTGRES_PASSWORD` — at least 32 URL-safe characters (`A-Z`, `a-z`, `0-9`, `_`, `-`)
- `TRAINSYT_JWT_SECRET` — at least 32 random characters
- `TRAINSYT_INITIAL_ADMIN_SECRET_KEY` — a different random value of at least 32 characters
- `TRAINSYT_SEED_ADMIN_PASSWORD` — set to `Admin123`; it is accepted only as a forced-change bootstrap password
- `TRAINSYT_ZOHO_EMAIL`
- `TRAINSYT_ZOHO_APP_PASSWORD`
- `TRAINSYT_EMAIL_FROM`

Optional environment variables:

- `TRAINSYT_HTTPS_PORT` — defaults to `2096`
- `TRAINSYT_SEED_ADMIN_FIRST_NAME` — defaults to `System`
- `TRAINSYT_SEED_ADMIN_LAST_NAME` — defaults to `Administrator`
- `TRAINSYT_PUBLIC_HEALTHCHECK_ENABLED` — set to `true` only after Cloudflare is ready

The deployment seeds `comsiwende@gmail.com` as the super administrator. Its initial `Admin123` password does not create a normal authenticated session: the first successful login receives only a short-lived password-change token and must set a strong replacement password immediately. Subsequent deployments never reset an existing administrator's password. The backend permits at most six active administrator accounts in total, including this seeded super administrator.

The frontend sends API calls through its same-origin `/backend` proxy. This keeps the readable CSRF cookie available to the frontend while the access and refresh JWT cookies remain HttpOnly, without exposing authentication cookies to unrelated Speqlink subdomains.

## Deployment lifecycle

A push to `main` or a manual workflow dispatch runs `.github/workflows/deploy.yml`. Runtime secrets are written only to `/home/deploy/apps/trainsyt/.env.prod` with mode `600`. PostgreSQL is not published on a host port. Before every migration, the workflow writes a compressed database dump under `/home/deploy/apps/trainsyt/backups`.

Useful VPS checks:

```bash
cd /home/deploy/apps/trainsyt
docker compose --env-file .env.compose -f docker-compose.prod.yml ps
docker compose --env-file .env.compose -f docker-compose.prod.yml logs --tail 150 trainsyt-api
docker exec trainsyt-api alembic current
curl --fail --insecure https://127.0.0.1:2096/health/ready
```

The seed command never overwrites an existing administrator password. Rotate an existing production administrator through the application rather than changing the GitHub seed password.
