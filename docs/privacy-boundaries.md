# Privacy Boundaries

This document defines the main data classes in the system and the current
boundary between implemented behavior and planned controls.

## Data Classes

### Workflow and event data

Stored in the append-only ledger:

- candidate details
- qualification outputs
- approvals and outbound send lifecycle events
- suppression records
- subject-rights requests and status changes
- reply triage outcomes
- retention-review and redaction events
- learning feedback

Purpose:

- deterministic workflow execution
- replay and audit
- operator review

### Provider metadata

Examples:

- provider name
- provider message ID
- requested/accepted/failed timestamps
- failure reason

Purpose:

- outbound auditability and reconciliation

### Reply text and user-provided content

Examples:

- inbound reply text
- reply text snippets
- operator notes on suppression/subject requests

Implemented boundary:

- reply text can enter the ledger at ingest time
- reply text/snippets can later be redacted through additive events
- projections, sanitized timelines, and exports should prefer the redacted view

Planned later:

- broader field-level minimisation and pseudonymisation

### Suppression and subject-rights state

Examples:

- entity/domain/email suppressions
- objection-to-marketing, erasure, rectification, and access-export requests

Purpose:

- block future outreach
- give operators an explicit workflow record instead of ad hoc notes
- support privacy-aware audit/export posture

### Operational logs and traces

Examples:

- JSON logs
- trace/span IDs
- local console tracing

Boundary:

- useful for runtime diagnosis, not the source of truth
- should avoid secrets and unnecessary personal data

### Secrets and config

Examples:

- `ADMIN_API_KEY`
- provider credentials
- HMAC secret
- environment configuration

Boundary:

- expected from environment variables or local `.env`
- not intended for source control

### Demo and runtime artifacts

Examples:

- local `data/ledger.jsonl`
- generated exports
- caches, traces, and local seed outputs

Boundary:

- runtime/operator data, not source code
- should be handled separately from tracked fixtures

### AI-ready derived content

Current state:

- not implemented as a separate data class

Planned later:

- if AI features are added, derived prompt/context data should have explicit
  minimisation, logging, and retention controls

## Suppression vs Deletion

### Suppression

Implemented today:

- config-based suppression
- first-class suppression registry in the ledger
- unsubscribe and objection-to-marketing enforcement through suppression events

Meaning:

- future outreach is blocked
- historical audit state is preserved

### Deletion / erasure

Implemented today:

- no destructive mutation of historical ledger events
- erasure is modeled as explicit subject-request state plus additive redaction
  for reply text where supported

Still planned:

- broader pseudonymisation
- backup handling
- legal basis review for retained audit history

## Legal Honesty

This repository demonstrates a privacy-aware and compliance-aware engineering
posture. It should not be represented as fully GDPR compliant or ready for
regulated production use without additional legal, privacy, and security review.
