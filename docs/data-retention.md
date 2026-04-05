# Data Retention

This document describes the current retention posture honestly. It explains
what the code does today and what still remains planned.

## Retention Principles

- keep append-only workflow history for replay and audit
- minimise sensitive raw content where practical
- prefer additive redaction over silent mutation
- keep runtime artifacts and secrets out of source control
- separate implemented controls from planned lifecycle automation

## Data Classes and Current Behavior

### Event ledger

Examples:

- candidate ingress events
- qualification, drafts, approvals, and sends
- suppression and subject-request workflow events
- reply triage, retention review, and redaction events
- learning feedback events

Current posture:

- retained indefinitely by default
- append-only by design
- source of truth for replay and audit

Implication:

- destructive deletion of historical ledger records is not implemented
- privacy-sensitive lifecycle handling is additive and overlay-based

### Reply text and user-provided content

Examples:

- inbound reply text
- reply text snippets
- operator-provided request notes

Current posture:

- reply text is treated as retention-sensitive
- retention review can mark reply content for redaction
- approved/completed erasure handling can trigger reply-text redaction
- redaction replaces reply text/snippets in projected views, sanitized timelines,
  and internal exports using `REDACTION_PLACEHOLDER`

Current limitation:

- raw historical reply text still remains in the append-only ledger
- broader pseudonymisation coverage is not yet implemented

### Logs and traces

Current posture:

- not managed by an in-repo retention scheduler
- local traces are optional and usually ephemeral
- logs/traces should avoid secrets and unnecessary personal data

### Secrets and config

Current posture:

- `.env` is ignored by git
- `.env.example` is sanitized
- no automated secret rotation or expiry enforcement exists in-repo

### Demo/runtime data

Examples:

- `data/ledger.jsonl`
- local exports and traces
- caches and generated artifacts

Current posture:

- treated as runtime data, not source code
- expected to be managed locally or by deployment tooling

## Subject-Rights and Retention Posture

### Direct marketing objection

Implemented today:

- unsubscribe and objection-to-marketing requests can create first-class suppression records
- future outreach is blocked through sender policy evaluation

### Erasure

Implemented today:

- erasure requests are explicit workflow state
- approved/completed erasure can trigger reply-text redaction through the
  retention runner
- projected state, exports, and entity timelines prefer the redacted view

Not implemented today:

- destructive deletion of core ledger history
- backup purge workflows
- broad field-by-field redaction beyond the current reply-text focus

### Access / export

Implemented today:

- internal/admin export can return projected entity state, sanitized event
  summary, suppression state, and subject-request state

Not implemented today:

- requester authentication portal
- delivery workflow for external data-subject requests

### Rectification

Implemented today:

- rectification requests can be tracked as explicit workflow state

Not implemented today:

- automated correction propagation or operator review tooling

## Planned Automation

- scheduled retention jobs beyond the current run-once utility
- broader pseudonymisation/redaction coverage
- backup retention and deletion controls
- authenticated access/export workflows

## Honest Boundary

The current system implements privacy-aware suppression, redaction, and export
behavior, but it does not implement full deletion semantics for an append-only
audit ledger. Real deployment still requires legal and security review.
