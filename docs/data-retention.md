# Data Retention

This document describes the current retention posture of the project.
It is an honest description of the present system, not a claim of completed
production-grade lifecycle management.

## Retention Principles

- keep only data needed for workflow execution and audit
- prefer structured derived signals over raw scraped content
- treat local demo/runtime data differently from source-controlled fixtures
- keep secrets out of source control
- separate implemented retention behavior from planned automation

## Data Classes and Current Posture

### Event ledger

Examples:

- candidate ingest events
- qualification and compliance outputs
- drafts, approvals, provider send lifecycle events
- reply triage events
- learning feedback events

Current posture:

- retained indefinitely by default
- append-only by design
- used for replay, audit, and deterministic state reconstruction

Implication:

- no automated deletion job exists today
- deletion requests require careful treatment because the ledger is the audit system of record

### Logs and traces

Examples:

- structured application logs
- optional local console traces

Current posture:

- not managed by a repository retention job
- local console tracing is ephemeral unless the operator redirects output elsewhere
- should avoid secrets and unnecessary personal data where possible

### Secrets and config

Examples:

- `.env`
- provider API keys
- admin API keys

Current posture:

- `.env` is ignored by git
- `.env.example` is the only tracked example
- secrets are expected through environment variables
- no automated secret rotation or expiry enforcement exists in-repo

### Demo and local runtime data

Examples:

- `data/ledger.jsonl`
- local exports, traces, tree dumps
- demo-seed output in local developer environments

Current posture:

- treated as local runtime data, not source code
- ignored through repo hygiene rules
- can be reset manually by deleting local runtime files or recreating the local database

### Backups and recovery

Current posture:

- backup scheduling and retention are not automated by this repo
- PostgreSQL/Redis persistence strategy depends on deployment choices outside the app code
- recovery expectations must be defined by the deployment environment

## Data Subject Rights Posture

### Direct marketing objection

Implemented today:

- unsubscribe is recorded through reply triage
- unsubscribe projects into marketing suppression
- future sends are blocked by policy

### Erasure / deletion request

Implemented today:

- no automated deletion pipeline

Planned posture:

- keep limited audit history where legally required
- pseudonymise or redact operationally unnecessary personal fields where possible
- remove or redact auxiliary stores, exports, and caches before touching core audit history
- define backup handling and restore-window expectations explicitly

### Access / export request

Implemented today:

- event history can be queried by entity for internal review

Planned posture:

- formal export tooling with authenticated requester validation

### Correction / rectification

Implemented today:

- no dedicated rectification workflow
- corrections would currently be represented by additional append-only events rather than silent edits

## Planned Automation

Not yet implemented:

- retention windows enforced by scheduled jobs
- automated draft expiry
- automated pseudonymisation
- backup retention/deletion workflows
- authenticated subject-rights request handling

## Legal Review Boundary

This system is privacy-aware and data-minimisation-aware, but production retention
and deletion posture still requires legal and security review for the target jurisdiction.
