# Threat Model

This document captures the main assets, trust boundaries, implemented
mitigations, and current gaps in the platform.

## Primary Assets

- outbound messaging capability
- append-only event ledger
- suppression and subject-rights workflow state
- reply text and operator-provided notes
- provider credentials and admin API keys
- projected entity state and internal export summaries

## Trust Boundaries

1. External caller -> API ingress
2. Operator browser -> server-rendered admin UI
3. Application -> file ledger / database ledger
4. Application -> Redis queue / worker runtime
5. Application -> outbound email provider
6. Application -> local logs/traces/runtime artifacts

## Main Threats and Current Mitigations

### Unauthorized administrative actions

Threat:
an unauthorized caller triggers approvals, sends, suppressions, redactions, or export actions.

Implemented today:

- non-dev admin/API write routes can require `ADMIN_API_KEY`
- candidate ingress uses HMAC validation outside dev
- administrative state changes are written to the append-only ledger

Residual risk:

- the operator UI does not yet enforce authentication or RBAC
- shared-key admin protection is weaker than user-scoped authorization

### Duplicate or repeated outbound sending

Threat:
retries, queue replays, or operator mistakes produce multiple sends.

Implemented today:

- deterministic event IDs
- provider send lifecycle events
- already-sent protection
- first-class suppression enforcement in the sender policy path
- queue workers reuse the same deterministic runners

Residual risk:

- concurrency control is still application-level rather than based on distributed locks

### Direct-marketing objection not being enforced

Threat:
an unsubscribe, objection, or manual suppression is recorded but a later send still goes out.

Implemented today:

- first-class suppression records for entity/domain/email targets
- reply-triage unsubscribe creates a suppression record
- approved/completed objection-to-marketing requests create a suppression record
- sender policy consults both config suppression and the suppression registry

Residual risk:

- there is not yet authenticated operator identity or approval routing around suppression changes

### Privacy-sensitive reply content persisting too broadly

Threat:
reply text remains visible longer than necessary in operator views or exports.

Implemented today:

- reply text is identified as retention-sensitive
- retention review emits additive events
- redaction is applied as an overlay event, not a hidden mutation
- entity timelines and export summaries use sanitized payloads after redaction

Residual risk:

- raw historical reply text still exists in the append-only ledger
- only reply text/snippets have code-first redaction today; broader field coverage is still planned

### Ledger tampering or inconsistent replay

Threat:
historical evidence is altered or replay becomes unreliable.

Implemented today:

- append-only event history
- deterministic event generation
- file-mode hash-chain verification

Residual risk:

- immutable storage controls and backup integrity guarantees are not yet implemented

### Secret leakage

Threat:
credentials leak into source control, logs, or runtime exports.

Implemented today:

- `.env` ignored by git
- `.env.example` sanitized
- logs emphasize IDs/metadata instead of dumping full payloads by default
- exports are internal/admin only and structured

Residual risk:

- no KMS/secret-manager integration yet
- local developer handling of env files and console output still matters

## Demo vs Operational Boundary

- The platform is suitable for portfolio demonstration and internal prototyping.
- It is not yet a production-ready, internet-exposed admin system.
- Legal review would still be required before representing the current
  redaction/suppression/export posture as sufficient for regulated deployment.
