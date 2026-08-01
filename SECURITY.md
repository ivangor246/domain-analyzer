# Security Policy

## Scope

Domain Analyzer is intended for inspecting public domain infrastructure. The backend rejects private, loopback, link-local, reserved, and otherwise non-public analysis targets, and it validates redirect destinations before making HTTP requests.

The service is not an authorization or asset-ownership system. Only analyze domains that you own or are explicitly authorized to inspect.

## Reporting a vulnerability

Do not disclose a suspected vulnerability in a public issue. Send a private report to the repository maintainers with:

- a short description and impact;
- reproducible steps or a minimal proof of concept;
- affected commit, configuration, or dependency;
- any suggested mitigation.

Do not include secrets, personal data, or live target data in a report.

## Operational boundaries

- Keep `back/.env` and production secrets outside Git.
- Build the backend from `back/`; its Docker build context excludes `.env` files, local environments, tests, and caches.
- Keep the backend API and worker containers non-root with read-only filesystems, dropped Linux capabilities, no-new-privileges, and explicit memory/PID limits.
- Configure exact trusted frontend origins through `CORS_ORIGINS`.
- Put authentication, TLS termination, request filtering, and a shared rate limiter in front of the API before public deployment.
- Keep the in-memory rate limiter enabled even when a gateway also applies limits.
- Review provider terms and acceptable-use requirements before enabling the service for third parties.
