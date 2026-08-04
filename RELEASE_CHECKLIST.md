# Release Validation Checklist

Use this checklist to validate a release candidate before publishing it. It does not replace the deployment-specific controls described in [DEPLOYMENT.md](DEPLOYMENT.md).

## Repository and documentation

- Confirm that `git status --short` contains only intended changes.
- Confirm that `LICENSE` contains the Apache License 2.0 text and that `back/pyproject.toml` declares `Apache-2.0`.
- Review [README.md](README.md), [SECURITY.md](SECURITY.md), [PRIVACY.md](PRIVACY.md), [ACCEPTABLE_USE.md](ACCEPTABLE_USE.md), and [DEPLOYMENT.md](DEPLOYMENT.md) for current commands, defaults, and operational guidance.
- Confirm that no `.env` file, credential, local log, cache, or generated build artifact is included in the candidate.

## Backend and API contract

Run these commands from the repository root:

```bash
make check
make coverage
make api-types-check
```

The coverage command must meet the configured threshold. The API type check ensures that the committed frontend types match the backend OpenAPI schema.

## Frontend

Run:

```bash
make front-check
make front-build
```

Verify the production build manually in a browser with the intended `VITE_API_URL`. Test a successful analysis, an invalid domain, an asynchronous job with progress, cancellation, a partial-result response, and local JSON and Markdown exports.

## Containers and runtime

Create a local backend environment file when it does not already exist:

```bash
cp back/.env.example back/.env
```

Then run:

```bash
make compose-smoke
docker build --tag domain-analyzer-back:release-check back
docker build --build-arg VITE_API_URL=http://localhost:8000 --tag domain-analyzer-front:release-check front
```

The Compose smoke test validates the API, Redis, and worker readiness in an isolated project and removes its temporary containers and volume on completion.

## Dependency and supply-chain review

- Run `npm --prefix front audit --audit-level=high` with access to the npm registry.
- Confirm that the latest successful GitHub Actions Security workflow completed the frontend `npm audit` and backend `pip-audit` checks.
- Review dependency updates and provider terms before changing default upstream services.
- Keep Docker base images and GitHub Actions revisions under Dependabot review.

## Deployment readiness

- Use exact trusted origins in `CORS_ORIGINS` and set `DOCS=False` unless documentation is intentionally exposed to authorized users.
- Keep Redis private and place TLS, authentication, request filtering, and shared rate limiting at the edge.
- Set conservative rate, concurrency, timeout, TTL, and log-retention values for the available resources and authorized traffic.
- Confirm health and readiness checks after deployment and restrict access to metrics, logs, backups, and Redis data.
