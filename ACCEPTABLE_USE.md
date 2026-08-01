# Acceptable Use

Domain Analyzer is an infrastructure inspection tool for self-hosted use. Run it only against public domains and infrastructure that you own or are explicitly authorized to inspect.

## Allowed use

Examples of appropriate use include:

- checking the security and availability posture of your own public domains;
- troubleshooting DNS, TLS, HTTP, RDAP, and network configuration;
- performing a low-volume assessment with permission from the target owner;
- developing and testing the application against controlled public test domains.

## Prohibited use

Do not use the project to:

- scan, enumerate, or monitor targets without authorization;
- evade rate limits, provider restrictions, network controls, or abuse protections;
- disrupt services, exhaust resources, or generate traffic intended to cause harm;
- collect personal data or confidential information beyond what is necessary for an authorized assessment;
- misrepresent the operator, target owner, or purpose of the analysis;
- expose an unprotected instance as a public scanning service.

The application rejects private, loopback, link-local, reserved, and unsafe redirect targets, but those safeguards do not replace authorization, an edge gateway, or responsible operational limits.

## Operator responsibility

The instance operator is responsible for access control, TLS, rate limits, resource limits, logs, provider terms, applicable law, and the targets selected by users. Review the [privacy notice](PRIVACY.md) before processing requests from other people.

