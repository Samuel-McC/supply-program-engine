# Security Controls

This document describes the security and privacy controls implemented in code
today, plus controls that are still planned. It is intentionally conservative.
The project is privacy-aware and GDPR-aware, not represented as "GDPR compliant."

## Implemented Today

### Authentication and authorization

- Non-dev admin/API write routes can require `ADMIN_API_KEY`.
- Candidate ingress uses HMAC validation outside `ENV=dev`.
- The UI is still an internal/demo operator surface. It does not yet have user
  authentication, sessions, or RBAC.
- Actor fields are captured on approvals, subject-request updates, and manual
  suppressions when the caller provides them.

### Auditability and replay

- Business state changes are written to an append-only ledger.
- Workflow runners remain deterministic and replay-safe through stable event IDs.
- Approval, suppression, redaction, retention review, reply triage, provider
  send, and learning actions all remain additive events.
- Export generation is an internal/admin action with its own audit event.

### Idempotency and duplicate protection

- Runners skip duplicate event emission when the same unit of work is re-run.
- Irreversible sends are still gated by approval, policy checks, provider-send
  lifecycle events, and already-sent protection.
- Suppression records and subject-request status updates use deterministic event
  IDs so repeated requests do not multiply state transitions.

### Direct-marketing and data-control enforcement

- Config-based suppression still exists for simple local overrides.
- First-class suppression records now exist for `entity`, `domain`, and `email`
  targets with reasons such as `unsubscribe`, `manual_suppression`,
  `objection_to_marketing`, and `compliance_hold`.
- Reply-triage unsubscribe handling records both `unsubscribe_recorded` and a
  first-class suppression record.
- Subject requests are explicit workflow state, including
  `objection_to_marketing`, `erasure`, `access_export`, and `rectification`.
- Approved/completed objection-to-marketing requests automatically create a
  suppression record that blocks future outreach.

### Redaction and retention

- Historical ledger events are not mutated in place.
- Reply-text minimisation is implemented through additive
  `retention_reviewed` and `data_redaction_applied` events.
- Entity projections, sanitized timelines, and export summaries prefer the
  redacted overlay rather than exposing prior raw reply text.
- `REPLY_TEXT_RETENTION_DAYS` and `REDACTION_PLACEHOLDER` are configurable for
  local/runtime behavior.

### Secrets and operational hygiene

- `.env` is ignored by git and `.env.example` is sanitized.
- Runtime secrets are expected from environment variables or local developer
  env files, not committed source.
- Local runtime artifacts such as `data/ledger.jsonl`, caches, and traces are
  treated as runtime data rather than source code.

### Supply-chain and runtime posture

- CI runs tests and security checks (`bandit`, `pip-audit`).
- Dependencies are pinned in `requirements.txt`.
- The queue/worker model reuses the same business runners instead of introducing
  a separate non-audited execution path.
- Lightweight tracing is optional and local-safe.

## Planned Controls

- Real authentication, sessions, and RBAC for operator/admin actions
- Secret manager / KMS integration and credential rotation
- Formal backup retention/deletion procedures
- Broader pseudonymisation beyond reply text
- Automated lifecycle scheduling beyond the current run-once retention utility
- Deployment-level hardening, network boundaries, and access review processes

## Honest Boundary

- The append-only ledger remains the system of record for replay and audit.
- This means erasure is currently implemented as operational redaction and
  suppression-aware access/export handling, not destructive historical deletion.
- Real deployments would still need legal, privacy, and security review.
