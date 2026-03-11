# Security Controls Matrix

This document maps implemented controls to security standards.

---

# Authentication

Planned controls:

- OIDC authentication provider
- MFA enforced at identity provider
- secure session cookies
- CSRF protection

---

# Authorization

Role model:

Operator roles include:

- reviewer
- approver
- sender

Actions such as approval and sending require authenticated sessions.

---

# Audit Logging

All significant system actions are recorded in the event ledger.

Logged events include:

- ingestion
- scoring
- draft creation
- approval decisions
- send attempts
- send completion

Audit records include:

- actor
- timestamp
- decision reason
- correlation ID

---

# Idempotency

Mutating operations use deterministic IDs.

Duplicate events are rejected by the ledger.

External side effects are gated through the outbox pattern.

---

# Supply Chain Security

The project implements:

- GitHub Actions security scanning
- Bandit static analysis
- pip-audit dependency scanning

Planned additions:

- Dependabot updates
- SBOM generation

---

# Infrastructure Security

Deployment uses:

- Docker containers
- non-root runtime
- minimal network exposure
- private admin access

Backups and recovery procedures are documented separately.