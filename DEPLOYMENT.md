# Self-Hosted Deployment

This guide describes a production-oriented deployment of Domain Analyzer. It assumes that the backend, worker, Redis, frontend, and edge proxy are operated by the same trusted administrator.

Domain Analyzer does not provide user authentication or target ownership verification. Do not expose it as an unrestricted public scanning service. Put authentication, authorization, TLS termination, request filtering, and a shared rate limit at the edge before allowing access from other people.

## Prerequisites

- Docker Engine with Docker Compose v2;
- a trusted edge proxy or load balancer that terminates TLS;
- a DNS name for the frontend and, when using a separate origin, for the API;
- outbound network access to the configured RDAP, DNS, GeoIP, and target-domain services.

Keep Docker, the host operating system, and the edge proxy patched. Restrict host access to trusted operators.

## Configure the backend

Create the environment file from the example:

```bash
cp back/.env.example back/.env
```

Set these values in `back/.env` before starting the services:

```dotenv
DOCS=False
DEV_MODE=False
CORS_ORIGINS=["https://app.example.com"]
APP_PORT=127.0.0.1:8000
```

Use the exact public frontend origins in `CORS_ORIGINS`. Do not use a wildcard. Binding `APP_PORT` to `127.0.0.1` keeps the backend reachable only through a local edge proxy; use a different private address only when the proxy runs on a separate protected network.

Keep the default `REDIS_URL=redis://redis:6379/0` when using the included Compose configuration. Redis has no published host port and must remain inaccessible from public networks.

Review and size these limits for the available host resources and expected authorized traffic:

- `RATE_LIMIT_REQUESTS` and `RATE_LIMIT_WINDOW_SECONDS`;
- `ANALYSIS_MAX_CONCURRENCY` and `CELERY_WORKER_CONCURRENCY`;
- `ANALYSIS_TIMEOUT_SECONDS`, `CELERY_TASK_SOFT_TIME_LIMIT_SECONDS`, and `CELERY_TASK_TIME_LIMIT_SECONDS`;
- `ANALYSIS_JOB_TTL_SECONDS`, `CELERY_RESULT_EXPIRES_SECONDS`, and log retention.

When a Redis outage must reject analysis requests, set `RATE_LIMIT_REDIS_FALLBACK_ENABLED=False`. Otherwise, the optional local fallback can enforce a per-process limit while Redis is unavailable.

## Start the backend services

From the repository root, build and start the API, worker, and Redis:

```bash
docker compose -f back/docker-compose.yml up -d --build
docker compose -f back/docker-compose.yml ps
```

The application and worker containers run as a non-root user with read-only filesystems, dropped Linux capabilities, `no-new-privileges`, and resource limits. Preserve those settings when adapting the Compose file.

Verify process health and dependencies from the host:

```bash
curl --fail http://127.0.0.1:8000/api/health
curl --fail http://127.0.0.1:8000/api/health/ready
```

The liveness endpoint checks only the API process. The readiness endpoint also requires Redis and a responsive worker. Investigate failed readiness checks before routing traffic to the API:

```bash
docker compose -f back/docker-compose.yml logs --follow app worker redis
```

## Build and publish the frontend

The frontend receives its API URL at build time. Build it with the exact public API origin:

```bash
docker build \
  --build-arg VITE_API_URL=https://api.example.com \
  --tag domain-analyzer-front:local \
  front

docker run \
  --detach \
  --name domain-analyzer-front \
  --restart unless-stopped \
  --publish 127.0.0.1:8080:80 \
  domain-analyzer-front:local
```

Values prefixed with `VITE_` are embedded in browser assets. Never use them for secrets. Serve the resulting image behind the edge proxy. If the proxy routes `/api` on the same origin as the frontend, build with that frontend origin as `VITE_API_URL` instead.

## Configure the edge

Configure the edge proxy to:

- terminate TLS and redirect plain HTTP to HTTPS;
- require access control before forwarding API requests;
- forward the public API origin to `http://127.0.0.1:8000` or another private backend address;
- forward the frontend origin to the frontend container on port 80;
- keep `/api/metrics` restricted to trusted monitoring systems;
- apply request-body, connection, and request-rate limits suitable for the deployment;
- avoid forwarding Redis, the Docker socket, or container-management endpoints.

Only expose the API endpoints that are needed. Keep `DOCS=False` unless the interactive schema is intentionally available to authenticated users.

## Data, logs, and updates

Redis stores asynchronous job metadata and results with configured TTLs. Its AOF volume, application logs, edge logs, metrics, and backups can retain domains, identifiers, and analysis metadata. Protect them and define retention and deletion procedures before accepting requests from other people. See [PRIVACY.md](PRIVACY.md) for the default data flows.

Before deploying an update, run the documented checks in a non-production environment, back up data only when operationally required, rebuild the images, and verify both health endpoints after the rollout. Review `back/.env` whenever `.env.example` changes; never commit the local environment file or place secrets in frontend build arguments.

For operational boundaries and vulnerability-reporting guidance, see [ACCEPTABLE_USE.md](ACCEPTABLE_USE.md) and [SECURITY.md](SECURITY.md).
