# Threat Model

This document captures the main trust boundaries, abuse cases, implemented
mitigations, and known gaps for the current system.

## Primary Assets

- outbound messaging capability
- append-only event ledger
- approval decisions and actor-supplied reasons
- provider credentials and admin API keys
- reply text and provider metadata
- projected entity state used by operators

## Trust Boundaries

1. External caller -> API ingress
2. Operator browser -> server-rendered admin UI
3. Application -> PostgreSQL / file ledger
4. Application -> Redis queue
5. Application -> outbound email provider
6. Application -> local logs and tracing output

## Main Threats and Current Mitigations

### Unauthorized administrative actions

Threat:
approval, send, queue, or replay actions are triggered by an unauthorized party.

Implemented today:

- non-dev admin API endpoints require `ADMIN_API_KEY`
- HMAC protection exists for candidate ingress outside dev
- approval and send actions create auditable events

Residual risk:

- the UI does not yet enforce authentication or role checks
- shared-key admin protection is not equivalent to user-level authorization

### Duplicate or repeated outbound sending

Threat:
retries, race conditions, or worker replays trigger extra sends.

Implemented today:

- deterministic event IDs
- replay-safe phase runners
- already-sent protection
- policy gate before irreversible sends
- provider lifecycle events before final `outbound_sent`

Residual risk:

- concurrency control is still application-level rather than backed by formal distributed locks

### Direct-marketing objection not being enforced

Threat:
an unsubscribe or objection is recorded but future outreach still occurs.

Implemented today:

- reply triage records `unsubscribe_recorded`
- unsubscribe projects into explicit marketing suppression state
- policy blocks future send attempts for suppressed entities/domains and unsubscribe-derived suppression

Residual risk:

- dedicated operator-managed suppression workflows are still planned rather than implemented

### Ledger tampering or inconsistent replay

Threat:
historical workflow evidence is altered or replay becomes unreliable.

Implemented today:

- append-only event ledger
- deterministic event generation
- hash-chain verification for file-backed ledger mode

Residual risk:

- immutable storage controls, backup integrity validation, and formal change-management procedures are not yet implemented

### Secret leakage

Threat:
credentials are committed to the repo, exposed in logs, or copied into demo artifacts.

Implemented today:

- `.env` ignored by git
- `.env.example` sanitized
- structured logs emphasize IDs over full payload logging

Residual risk:

- no secret manager / KMS integration yet
- local developer handling of `.env` files still depends on process discipline

### Supply chain compromise

Threat:
malicious dependency or vulnerable package enters the build.

Implemented today:

- CI runs `bandit`
- CI runs `pip-audit`
- dependency versions are pinned in `requirements.txt`

Residual risk:

- no SBOM generation
- no automated provenance/attestation pipeline
- no dedicated secret-scanning workflow yet

### Privacy and data rights mismatch

Threat:
the append-only audit model conflicts with deletion expectations or stores more personal data than needed.

Implemented today:

- deterministic workflow stores structured signals instead of raw enrichment blobs
- unsubscribe-driven suppression exists
- documentation now distinguishes suppression from deletion

Residual risk:

- no automated erasure, pseudonymisation, or retention jobs yet
- reply text currently lives in the ledger when ingested
- legal review is still required for real deployments

## Demo vs Operational Risk

- Demo seed data is intended for local walkthroughs and should not be mixed with operational data.
- Local `data/ledger.jsonl`, logs, traces, and `.env` files are runtime artifacts, not source code.
- The current platform is suitable for portfolio demonstration and internal prototyping, not production internet exposure without additional controls.
