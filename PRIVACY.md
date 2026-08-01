# Privacy Notice for Self-Hosted Instances

This document describes the default data flows of Domain Analyzer. It is an operational template for the person or organization running an instance, not legal advice or a complete privacy notice for every deployment.

## Instance responsibility

Each installation is operated independently. The instance operator controls the deployment, configuration, Redis data, application logs, reverse proxy, monitoring, backups, and retention periods. The operator is responsible for adapting this notice to local law and for informing people whose data may be processed by the instance.

Domain Analyzer has no built-in user accounts, authentication, or ownership verification. It is not designed as a shared multi-tenant service.

## Data received and generated

An instance may receive or generate:

- the domain supplied in a synchronous request or asynchronous job;
- the `Idempotency-Key` header, whose Redis lookup key is stored as a SHA-256 digest;
- a generated request ID, analysis ID, and Celery task ID;
- the client address used by the request rate limiter. Redis rate-limit keys use a SHA-256 digest of that address;
- analysis results, statuses, timestamps, cancellation flags, and normalized errors;
- structured operational logs and process-local metrics.

The application does not intentionally store raw upstream response bodies or credentials. Logs can contain the requested domain, request and task identifiers, check names, statuses, and durations. Configure log access and retention accordingly.

## Retention and deletion

Asynchronous job metadata and Celery results are stored in Redis with configurable TTLs (`ANALYSIS_JOB_TTL_SECONDS` and `CELERY_RESULT_EXPIRES_SECONDS`). Redis persistence, including the Compose AOF volume, can extend practical retention until the data expires and is removed from the persistence layer.

The application does not use PostgreSQL or another durable report database by default. To remove data, the instance operator must account for Redis keys, Redis persistence, application and proxy logs, monitoring storage, backups, and container volumes.

## External requests

An analysis can send requests to the target domain and configured infrastructure providers, including:

- IANA RDAP bootstrap and RDAP servers;
- DNS resolvers and DNS propagation providers;
- the configured GeoIP provider;
- the target domain over HTTP, TLS, and TCP ports.

External providers and target operators may receive the instance's network address, the target domain, timing information, and normal protocol metadata. Review provider terms, configure trusted endpoints, and disclose these transfers when required.

## Operator controls

Before exposing an instance to other people, the operator should:

- terminate TLS and apply access control at a trusted edge;
- set exact `CORS_ORIGINS` values and keep Redis off the public network;
- choose conservative TTLs, log retention, rate limits, and concurrency limits;
- avoid sending secrets in frontend build variables or request data;
- restrict access to logs, metrics, Redis, backups, and monitoring systems.

