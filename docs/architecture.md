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
4. sends the email only when policy allows it
5. emits `outbound_sent`

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
