# System Architecture

## Overview

Supply Program Engine is a secure outbound automation system designed to:

- ingest candidate companies
- enrich safe public website and domain signals
- evaluate scoring and compliance signals
- generate outreach drafts
- require explicit human approval
- send outbound communication through a controlled pipeline

The system is designed using **event sourcing principles** with a tamper-evident ledger.

---

# Core Components

## API Layer

Technology:

- FastAPI
- HTMX operator console
- server rendered templates (Jinja2)

Responsibilities:

- candidate ingestion
- operator UI
- approval actions
- system health endpoints
- metrics exposure

---

## Event Ledger

All system activity is written to an **append-only event ledger**.

Characteristics:

- append-only JSONL or Postgres-backed storage
- deterministic event IDs
- hash chaining for integrity verification
- immutable audit trail

Example events:

- `candidate_ingested`
- `enrichment_started`
- `enrichment_completed`
- `enrichment_failed`
- `scored`
- `compliance_checked`
- `draft_created`
- `outbound_approved`
- `outbox_ready`
- `outbound_send_blocked`
- `outbound_provider_send_requested`
- `outbound_provider_send_accepted`
- `outbound_provider_send_failed`
- `outbound_sent`

This ledger acts as the **system of record**.

---

## Projections

The system derives read models from the event stream.

Example projection:

`PipelineState`

This allows:

- fast UI queries
- deterministic state reconstruction
- auditability

Enrichment projections expose structured company intelligence such as:

- website presence
- domain
- contact page detection
- construction and distributor keyword signals
- likely B2B fit

---

## Outbound Sender

The sender processes events with type:
`outbox_ready`

The sender:

1. validates idempotency
2. evaluates deterministic suppression / policy rules
3. emits `outbound_send_blocked` when policy conditions fail
4. sends through a provider abstraction and records provider lifecycle events
5. emits `outbound_sent` only after provider acceptance

External side effects are therefore always tied to ledger events.

---

## Enrichment Engine

The enrichment stage processes `candidate_ingested` events and emits one of:

- `enrichment_started`
- `enrichment_completed`
- `enrichment_failed`

The phase is intentionally bounded:

- safe public website fetch only when a website exists
- title and meta description extraction
- deterministic keyword heuristics
- structured payloads only, not raw page-content blobs

Qualification and outbound drafting may consume completed enrichment signals when available, but the enrichment stage remains replayable and idempotent on its own.

---

## Reply Triage

Inbound replies are ingested through a deterministic reply-triage stage.

The stage emits:

- `reply_received`
- `reply_classified`
- `lead_interested`
- `lead_rejected`
- `unsubscribe_recorded`
- `reply_triage_failed`

Phase 20 keeps classification intentionally bounded:

- normalized lowercase text only
- transparent keyword and phrase matching
- no model inference

Reply ingestion can link by `entity_id`, `draft_id`, or provider `message_id`, and duplicate payloads resolve to the same deterministic event IDs so replay and retries remain safe.

---

## Learning Feedback

The learning stage is a deterministic analytics layer built on top of existing workflow outcomes.

The stage emits:

- `outcome_recorded`
- `scoring_feedback_generated`
- `source_performance_updated`
- `template_performance_updated`

Phase 21 is intentionally bounded:

- no rule rewriting
- no model inference
- no self-modifying behavior
- structured feedback labels only

The runner derives outcome categories from existing send and reply state such as:

- `sent_no_reply`
- `reply_interested`
- `reply_rejected`
- `unsubscribe`
- `out_of_office`

It then emits compact source, segment, and template feedback signals such as source quality, template effectiveness, and reply signal strength while preserving replayability and idempotency.

---

## Queue and Worker Runtime

Phase 22 adds a bounded queue-backed worker runtime for background execution.

The design is intentionally simple:

- queue abstraction first
- Redis backend for asynchronous task transport
- in-memory fallback for local development and tests
- existing phase runners remain the business-logic entrypoints

Initial queued task types include:

- `enrichment_run`
- `sender_run`
- `learning_run`

Workers dequeue a task, dispatch it to the corresponding deterministic `run_once` phase runner, and rely on the existing ledger/idempotency protections to avoid duplicate side effects.

Manual `run-once` API endpoints remain available for local operation, replay, and debugging, so the queue runtime coexists with the synchronous paths rather than replacing them.

---

## Observability and Tracing

Phase 23 adds lightweight runtime tracing around the main workflow boundaries.

The tracing layer is intentionally separate from the ledger:

- ledger events remain the durable audit record
- logs remain the operational event stream
- spans provide ephemeral runtime visibility across API, queue, worker, and phase boundaries

Instrumentation is kept at workflow edges such as:

- candidate ingress
- enrichment
- qualification/orchestration
- outbound draft generation
- approval and send
- provider send
- reply triage
- learning
- queue enqueue
- worker dispatch

When enabled, spans are annotated with existing identifiers like `correlation_id`, `entity_id`, `event_type`, `task_type`, and `provider_name`.

Local development stays safe through a no-op fallback when OpenTelemetry packages or collectors are not present, and a console exporter can be used when the SDK is available.

---

## Operator Console

The console is implemented with:

- HTMX
- server-side rendering
- Tailwind CSS

Operators can:

- inspect entities
- review compliance findings
- review drafts
- approve or reject outreach
- trigger send operations

No automated sending occurs without human approval.

---

# Deployment Model

The system is designed for deployment using:

- Docker Compose
- PostgreSQL
- Caddy reverse proxy
- private access via VPN or identity-aware proxy

The admin console is **not intended to be public**.

---

# Security Model

Key principles:

- append-only audit log
- idempotent external actions
- explicit human approval gate
- deterministic send policy gate before irreversible outbound actions
- deterministic event IDs
- minimal external surface area
