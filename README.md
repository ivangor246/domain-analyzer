# Domain Analyzer

Domain Analyzer is an asynchronous FastAPI service that collects technical information about a domain and returns it as one structured response. The repository is organized for an independent backend and a future frontend application.

## Current capabilities

For a validated domain, the backend can collect:

- RDAP registration data, status, registrar, nameservers, and domain dates;
- DNS records: A, AAAA, MX, TXT, CNAME, NS, SOA, CAA, and PTR;
- DNS propagation results from public resolvers;
- GeoIP and ASN data for resolved IP addresses;
- HTTP and HTTPS reachability, redirects, response timing, and selected headers;
- TLS protocol, cipher, certificate details, validity, and fingerprint;
- TCP status for common service ports;
- TCP connection latency for ports 80 and 443.

If one external check is unavailable, the response still contains the successful results and lists the failed checks in `analysis_errors`.
Reports include UTC analysis timestamps, total and per-check durations, and sanitized public source identifiers for freshness review.

Some results depend on the availability of the target domain and external services, including IANA RDAP bootstrap data, DNS resolvers, and the GeoIP provider.

For safety, the backend only analyzes domains that resolve to public IP addresses. Private, loopback, link-local, reserved targets, and unsafe HTTP redirects are rejected.

## Repository layout

```text
.
├── back/
│   ├── src/app/             # FastAPI application
│   ├── pyproject.toml       # Backend dependencies and tooling
│   ├── poetry.lock
│   ├── Dockerfile
│   ├── docker-compose.yml   # API, Celery worker, and Redis
│   └── entrypoint.sh
├── front/                   # Vite + TypeScript + React application
├── AGENTS.md                # Instructions for AI agents
├── Makefile                 # Repository-level backend commands
└── README.md
```

The frontend and backend are intentionally kept in separate directories and are expected to run independently.

## Requirements

- Python 3.13 or newer;
- Poetry 2.x for local backend development;
- Docker and Docker Compose for containerized development.

## Backend configuration

Create the local environment file before running the backend:

```bash
cp back/.env.example back/.env
```

The settings model loads `.env` when the command is run from `back/` and `back/.env` when it is run from the repository root. Production-safe defaults are used when a value is not provided.

The current configuration supports:

- `DOCS=True` — enables the OpenAPI, Swagger UI, and ReDoc endpoints;
- `DEV_MODE=True` — enables development behavior when running through Compose;
- `TITLE` — customizes the service title shown by FastAPI;
- provider URLs and `HTTP_USER_AGENT` — configure upstream endpoints and request identity;
- `REDIS_URL` — configure the Redis broker and result backend used by the background worker;
- `REDIS_TIMEOUT_SECONDS` — bound Redis connection and command timeouts;
- `ANALYSIS_TIMEOUT_SECONDS` — set the global deadline for one domain analysis;
- `CELERY_*` — configure worker concurrency, task time limits, logging, and result retention;
- `ANALYSIS_JOB_TTL_SECONDS` — configure how long queued-analysis metadata remains available in Redis;
- `ANALYSIS_MAX_CONCURRENCY` and `ANALYSIS_CONCURRENCY_*` — configure the distributed Redis lease, retry delay, and retry limit for active analyses;
- provider timeouts, retry counts, exponential backoff, jitter, `Retry-After` limits, circuit-breaker thresholds, bounded provider-cache size, cache TTLs, response-size, redirect, domain, DNS, GeoIP, and RDAP limits.
- `RATE_LIMIT_*` — configure the request window, Redis backend, and local fallback for analysis requests;
- `CORS_ORIGINS` — configure the explicit frontend origins allowed to call the API.

RDAP and GeoIP caches are process-local, bounded, and disabled by setting `PROVIDER_CACHE_ENABLED=False`. Only successfully parsed provider records are cached; target HTTP responses are never cached.

The complete list of supported settings and safe defaults is available in `back/.env.example`.

Do not commit `back/.env` or place secrets in the repository.

## Run with Docker

From the repository root:

```bash
make up       # Build and start the backend, worker, and Redis
make dev      # Start Compose watch mode with development settings
make logs     # Show backend logs
make stop     # Stop running services
make rm       # Stop services and remove volumes
make clear    # Remove services, volumes, images, and orphans
```

The API is available at `http://localhost:8000`.

Application logs are emitted as one JSON object per line. Each response includes an `X-Request-ID` header. For asynchronous jobs, the request ID is carried into the Celery task and logged together with the analysis ID, task ID, check name, status, and duration, so one analysis can be followed across API, worker, and provider-check logs.

The analysis endpoints return HTTP 429 after the configured number of requests from one client address within the rate-limit window. Redis is used by default so the limit is shared across backend processes. Set `RATE_LIMIT_REDIS_FALLBACK_ENABLED=True` to keep a per-process fallback when Redis is temporarily unavailable; disable the fallback when rejecting requests is preferable to weakening the limit.

Local frontend requests from `http://localhost:5173` are allowed by default. Set `CORS_ORIGINS` to the exact development or production origins used by the deployment; wildcard origins are intentionally not required.

## Run locally

```bash
cd back
poetry install
poetry run uvicorn app.main:create_app \
  --factory \
  --host 127.0.0.1 \
  --port 8000 \
  --reload \
  --app-dir src
```

## API

Check that the API process is alive without triggering any external analysis:

```bash
curl 'http://localhost:8000/api/health'
```

The liveness endpoint returns `{"status":"ok"}` and does not depend on Redis or a worker. Check deployment readiness separately:

```bash
curl -i 'http://localhost:8000/api/health/ready'
```

The readiness endpoint checks Redis and at least one responsive Celery worker. It returns HTTP 200 with `{"status":"ready", ...}` when both dependencies are available, or HTTP 503 with `{"status":"not_ready", ...}` otherwise.

Process-local Prometheus-compatible metrics are available at:

```bash
curl 'http://localhost:8000/api/metrics'
```

The endpoint reports HTTP requests, rate-limit decisions, analysis durations, check outcomes, Celery job outcomes, and the Redis-backed queued-job depth. `domain_analyzer_analysis_queue_available` is `0` and the depth is `-1` when Redis cannot be queried. Metric labels do not contain domains, request IDs, or analysis IDs. Other metrics are process-local; a multi-process deployment should scrape each backend process or aggregate them at the monitoring layer.

API errors use a consistent JSON shape:

```json
{
  "code": "invalid_domain",
  "message": "Invalid domain format"
}
```

Validation errors may also include a `details` array with the invalid request locations.

Analyze a domain with:

```bash
curl 'http://localhost:8000/api/domain?d=example.com'
```

Invalid domains return HTTP 400. An unsuccessful RDAP lookup is reported in `analysis_errors` while other checks
continue when possible.

The compatible synchronous endpoint `GET /api/domain` completes the available checks in one request and returns partial results when individual providers fail.
Each analysis also has a global deadline controlled by `ANALYSIS_TIMEOUT_SECONDS`; checks that exceed it are cancelled and reported in `analysis_errors` while completed checks are preserved.

For long-running requests, queue an asynchronous analysis:

```bash
curl -X POST 'http://localhost:8000/api/analyses' \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: example-analysis-1' \
  -d '{"domain":"example.com"}'
```

The response contains an analysis identifier and starts in the `queued` state. Poll its status and result with:

```bash
curl 'http://localhost:8000/api/analyses/<analysis-id>'
```

The status changes through `queued`, `running`, and a terminal `completed`, `failed`, or `cancelled` state. While a job is queued or running, its `progress` array reports each check as `queued`, `running`, `successful`, `partial`, or `failed`, with a duration when the check has finished. A queued or running job can be cancelled with `POST /api/analyses/<analysis-id>/cancel`. Job metadata and Celery results expire automatically; PostgreSQL is not required for this workflow.

Active analyses use a Redis-backed distributed concurrency limit. When all slots are occupied, Celery retries queued tasks after `ANALYSIS_CONCURRENCY_RETRY_SECONDS`; after `ANALYSIS_CONCURRENCY_MAX_RETRIES` attempts the job becomes failed. Leases expire automatically after `ANALYSIS_CONCURRENCY_LEASE_SECONDS`, which must be longer than `ANALYSIS_TIMEOUT_SECONDS`.

When `DOCS=True`, interactive API documentation is available at:

- `http://localhost:8000/api/docs` — Swagger UI;
- `http://localhost:8000/api/redoc` — ReDoc;
- `http://localhost:8000/api/docs.json` — OpenAPI schema.

## Quality checks

Run the backend checks from `back/`:

```bash
cd back
poetry check --lock
PYTHONPATH=src python -m unittest discover -s tests
poetry run ruff check src
poetry run ruff format --check src
```

From the repository root, the same checks are available through `make check`. Use `make coverage` to generate a local coverage report.

The backend test suite uses Python's standard `unittest` runner and avoids network-dependent checks by replacing external services with test doubles.

## Frontend

The frontend is an independent Vite + TypeScript + React application in `front/`. Configure the backend URL before running it:

```bash
cp front/.env.example front/.env
make front-install
make front-dev
```

Frontend checks and production build are independent from the backend:

```bash
make front-typecheck
make front-lint
make front-test
make front-build
```

Frontend API types are generated from the backend OpenAPI schema. After backend schema changes, regenerate them with:

```bash
make api-types
```

The command uses the FastAPI application directly and writes `front/src/api/generated.ts`. It requires backend dependencies to be installed with Poetry. For a running instance with `DOCS=True`, the frontend-only command can read the published schema with `OPENAPI_INPUT=http://localhost:8000/api/docs.json npm --prefix front run api:types`.

Run the backend and worker health smoke test through Compose after creating `back/.env`:

```bash
make compose-smoke
```

The smoke test uses an isolated Compose project and port `18000` by default, and removes its own containers and volumes on exit. Override `APP_PORT` or `COMPOSE_PROJECT_NAME` when needed.

The frontend validates successful analysis and job responses at runtime. If the API returns an incompatible payload, it shows a controlled error instead of rendering untrusted malformed data.

During asynchronous analysis, the frontend polls the job and shows the state and duration of each backend check.

Frontend tests cover polling cancellation, loading progress, partial reports, and key accessibility landmarks without requiring a browser test service.

Completed reports can be downloaded locally as JSON or Markdown. The export is generated in the browser and does not send the report to another service.

The report also includes a transparent, heuristic security-signal summary with severity labels and remediation suggestions. It is intentionally presented as a signal check, not as a complete security audit.

Build the frontend as a standalone production container:

```bash
docker build --build-arg VITE_API_URL=http://localhost:8000 -t domain-analyzer-front ./front
docker run --rm -p 4173:80 domain-analyzer-front
```

## Deployment notes

The backend and frontend are deployed independently. The backend image is built from `back/` and serves the API on port 8000. The frontend image is built from `front/`, serves the Vite output through Nginx on port 80, and receives `VITE_API_URL` at image build time.

Before a public deployment:

- build the backend from `back/` so its `.dockerignore` excludes local environment files and secrets;
- keep the backend API and worker containers non-root and retain their read-only filesystem, dropped capabilities, no-new-privileges setting, and resource limits unless the deployment requires an explicit override;
- set `CORS_ORIGINS` to exact trusted frontend origins;
- place authentication, TLS termination, and a shared rate limiter at the edge because the application limiter is per process;
- keep `DOCS=False` unless API documentation is intentionally exposed;
- provide no secrets through frontend variables, because `VITE_*` values are bundled into browser assets;
- confirm that external RDAP, DNS, GeoIP, and target-domain traffic is permitted by the deployment network;
- retain structured logs and avoid logging provider response bodies or personal data.

There is currently no built-in authentication or ownership verification. The service is an infrastructure inspection tool for authorized public targets, not a general-purpose scanning service. Review licensing, privacy, provider terms, and acceptable-use requirements before launch; no project license has been selected yet.

See [SECURITY.md](SECURITY.md), [PRIVACY.md](PRIVACY.md), and [ACCEPTABLE_USE.md](ACCEPTABLE_USE.md) for the security policy, self-hosted data-flow template, and acceptable-use boundaries. The project license is intentionally not selected yet.
