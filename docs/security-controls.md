# Security Controls

This document describes the current security posture of the repository and runtime.
It is intentionally split between controls that are implemented today and controls
that are planned for later phases.

This project should be described as privacy-aware and GDPR-aware, not as
"GDPR compliant." Real deployment still requires legal, privacy, and security review.

## Implemented Today

### Authentication and Authorization

- Sensitive non-dev API write endpoints can be gated by a shared `ADMIN_API_KEY`.
- Candidate ingress uses HMAC request signing outside `ENV=dev`.
- The server-rendered operator UI does not yet implement user authentication,
  sessions, or RBAC.
- Approval and send actions are tracked with actor fields where the workflow
  captures them, but actor identity is not yet backed by authenticated sessions.

### Audit and Traceability

- Business workflow state changes are written to an append-only event ledger.
- Events include `correlation_id`, `entity_id`, timestamps, and structured payloads.
- Approval and rejection events include actor and reason fields.
- Logs are structured JSON and include `correlation_id` when provided.
- Lightweight tracing can attach runtime trace/span IDs to logs when enabled.

### Idempotency and Duplicate Protection

- Mutating workflow events use deterministic event IDs.
- Phase runners are safe to re-run and skip duplicate event emission.
- Irreversible outbound sends are gated by approval, policy checks, provider
  lifecycle events, and duplicate detection.
- Queue-backed execution reuses the same deterministic runners rather than
  introducing a separate non-idempotent code path.

### Direct Marketing Controls

- Config-based suppression exists through `SUPPRESSED_ENTITIES` and `SUPPRESSED_DOMAINS`.
- Reply triage records `unsubscribe_recorded`.
- Unsubscribe now sets an explicit marketing-suppressed state in projections and
  blocks future send attempts through policy evaluation.

### Secret Handling

- `.env` files are ignored by git.
- `.env.example` is sanitized and intended only as a local template.
- Runtime secrets are expected through environment variables.
- The repo avoids committing live API keys or provider credentials.

### Supply Chain and Build Posture

- GitHub Actions run tests on pull requests and main-branch changes.
- A dedicated security workflow runs `bandit` and `pip-audit`.
- Docker runs the app as a non-root user.
- Dependency versions are pinned in `requirements.txt`.

### Runtime and Infrastructure Posture

- The app defaults to local development mode unless configured otherwise.
- Docker Compose is intended for local developer use and does not represent a hardened deployment boundary.
- PostgreSQL and Redis are isolated to local-compose networking in the demo setup.
- The append-only ledger model supports replay and integrity-oriented verification in file mode.

## Planned Controls

### Authentication and Authorization

- Identity-backed operator authentication
- Session management
- RBAC for reviewer / approver / sender roles
- UI access controls for administrative actions

### Secrets and Key Management

- Secret manager or KMS integration
- Credential rotation procedures
- Separate credentials by environment

### Platform Hardening

- Network boundary hardening for real deployments
- Managed TLS termination and secure ingress
- Stronger backup encryption and restore validation
- SBOM generation and artifact attestation
- Dependency update automation
- Dedicated secret scanning in CI

### Privacy and Governance

- Authenticated audit trails tied to real user identities
- Formal retention/deletion workflows
- Access review and incident response processes

## Portfolio / Demo Caveats

- The current UI should be treated as an internal demo/admin surface, not an
  internet-exposed product.
- Shared-key admin protection is better than open write access, but it is not a
  substitute for real authentication and authorization.
- The event ledger is intentionally durable for replay and audit, which means
  privacy-sensitive lifecycle controls must be designed carefully before production use.
