# Privacy Boundaries

This document defines the data classes handled by the system and the current
privacy boundary between implemented behavior and planned controls.

## Data Classes

### Workflow / event data

Stored in the append-only ledger:

- candidate details
- qualification outputs
- compliance findings
- drafts and approval decisions
- send lifecycle events
- reply triage outcomes
- learning feedback

Purpose:

- deterministic workflow execution
- replay and audit
- operator review

### Provider metadata

Examples:

- provider name
- provider message ID
- accepted / failed timestamps
- failure reasons

Purpose:

- auditability of outbound side effects
- reconciliation and debugging

### Reply text and user-provided content

Examples:

- inbound reply text
- reply snippets
- reply classifications

Purpose:

- deterministic triage
- suppression / objection handling
- downstream learning signals

Boundary:

- reply text is workflow data and may enter the ledger today
- further minimisation or redaction is planned, not implemented

### Operational logs and traces

Examples:

- JSON application logs
- optional trace/span IDs
- local console tracing output

Purpose:

- runtime debugging
- operator/developer observability

Boundary:

- logs/traces are not the source of truth
- the ledger remains the durable audit system

### Secrets and config

Examples:

- admin API key
- provider credentials
- HMAC secret
- environment configuration

Boundary:

- expected from environment variables or local `.env`
- not intended to be stored in source control

### Demo and seed data

Examples:

- local demo seed outputs
- local `data/ledger.jsonl`

Boundary:

- portfolio/demo only
- should not be treated as production operational records

### AI-ready derived content

Current state:

- not implemented as a dedicated data class

Planned later:

- if AI features are introduced, AI-ready derived content should be treated as a
  separate class with explicit minimisation, retention, and prompt-safety controls

## Suppression vs Deletion

### Suppression

Implemented today:

- config-based entity/domain suppression
- unsubscribe-driven marketing suppression

Meaning:

- block future outreach
- retain existing audit history

### Deletion / erasure

Implemented today:

- no automated deletion workflow

Planned posture:

- remove or redact non-essential operational copies first
- evaluate pseudonymisation of retained audit records where lawful and practical
- define backup handling expectations
- document legal basis for any retained history

## Data Minimisation Posture

Implemented today:

- enrichment stores structured signals instead of full-page archives
- provider flow stores metadata rather than full provider payload dumps
- suppression can be enforced without deleting audit history

Still planned:

- stricter minimisation for reply text retention
- export/redaction tooling
- formal privacy review for real deployment

## Legal Honesty

This repository is designed to show privacy-aware engineering posture.
It should not be represented as fully GDPR compliant or ready for regulated production use without additional legal, privacy, and security review.
