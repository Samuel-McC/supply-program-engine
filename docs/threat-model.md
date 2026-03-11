# Threat Model

## Assets

Critical assets in the system include:

- outbound messaging capability
- candidate data
- scoring signals
- approval decisions
- event ledger
- external email provider credentials

---

# Trust Boundaries

Major trust boundaries:

1. External internet → API ingress
2. Operator browser → admin console
3. Application → email provider
4. Application → database

---

# Threat Actors

Possible attackers include:

- malicious internet clients
- compromised operator accounts
- supply chain dependency attacks
- prompt injection via scraped content
- internal misuse

---

# Key Abuse Cases

## Unauthorized Email Sending

Risk:

An attacker sends mass outbound emails.

Mitigation:

- approval gate required
- idempotency checks
- audit logging
- role separation

---

## Prompt Injection via Scraped Content

Risk:

LLM prompt manipulation through scraped data.

Mitigation:

- treat scraped content as untrusted input
- separate instructions from evidence
- structured model outputs
- policy validation before sending

---

## Ledger Tampering

Risk:

Modification of historical events.

Mitigation:

- append-only event model
- hash chaining verification
- immutable log design

---

## Duplicate Sends

Risk:

multiple messages sent to the same recipient.

Mitigation:

- idempotency keys
- outbox event model
- send status verification

---

## Credential Leakage

Risk:

secrets committed to repository.

Mitigation:

- `.env` excluded via gitignore
- CI secret scanning
- environment-based secret injection