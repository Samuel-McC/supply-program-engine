# System Architecture

## Overview

Supply Program Engine is a secure outbound automation system designed to:

- ingest candidate companies
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
