# INTENTLOCK — System Architecture

> Status: proposed architecture for the wHACKiest 2026 prototype. Components and guarantees are not considered implemented until verified by tests.

## 1. Architectural principle

**LLMs interpret. Deterministic code validates and decides. The controlled browser executes. The verifier checks the outcome.**

The language model must never be the final authority for whether a consequential browser action is permitted. It may propose a task contract and candidate facts; schemas, evidence checks, and policy code enforce the rules.

## 2. High-level components

### A. Web client — Next.js + TypeScript

Responsibilities:

- Accept a natural-language task.
- Display the proposed intent contract in plain language.
- Require explicit confirmation before starting a browser session.
- Show evidence records, policy decisions, approvals, and task status.
- Allow the user to stop a session and explicitly amend a contract.

The client is not trusted to enforce policy. The backend is authoritative.

### B. API and session orchestrator — Python + FastAPI

Responsibilities:

- Create task sessions.
- Call the contract compiler.
- Validate and persist confirmed contract versions.
- Coordinate browser execution, evidence extraction, policy checks, and final verification.
- Expose an audit timeline to the client.

### C. Intent contract compiler — LLM + Pydantic

The model converts the user's request into a *proposed* structured contract. Pydantic and application validation reject malformed or ambiguous values.

Example contract:

```json
{
  "task_id": "demo-task-001",
  "version": 1,
  "goal": "Find and compare refundable hotels",
  "constraints": {
    "max_total_price": {"amount": 5000, "currency": "INR"},
    "max_distance_km": 5,
    "refundable_required": true,
    "allowed_domains": ["hotel-a.local", "hotel-b.local"],
    "prohibited_actions": ["book", "pay", "share_personal_data"]
  },
  "confirmation": {
    "status": "confirmed",
    "confirmed_at": "server timestamp"
  }
}
```

The example is illustrative. Runtime validation must define currency, tax inclusion, distance origin, cancellation meaning, allowed domains, and action categories explicitly.

Before confirmation, the user can edit the proposal. After confirmation:

- The server canonicalises the contract and calculates a cryptographic hash.
- The confirmed version is stored with its hash and confirmation event.
- A webpage or model output cannot mutate that version.
- Any user-authorised change creates a new version and an audit event.
- Each action is evaluated against the active confirmed version.

A hash detects changes; it does not itself enforce immutability. Access controls and append-only/versioned records are also required.

### D. Browser executor — Playwright

Responsibilities:

- Launch an isolated browser context for each demo task.
- Navigate only to the allow-listed demo origins.
- Read page structure and accessibility information.
- Propose or execute actions only through the controlled action adapter.
- Capture pre-action and post-action state.
- Avoid storing real credentials or performing real purchases.

**Important enforcement boundary:** Every agent-controlled action must pass through the adapter. Do not expose an unrestricted Playwright page, arbitrary JavaScript execution, or raw browser debugging endpoint to the LLM. If a route bypasses the adapter, the policy guarantee does not cover it.

### E. Evidence provenance engine

For each decision-critical claim, create an evidence record containing:

- Claim type and normalised value.
- Source URL and origin.
- Page/offer/room identifier where available.
- Capture timestamp.
- Supporting DOM text or structured field.
- Relevant page-state snapshot or test fixture reference.
- Verification status: `verified`, `conflicting`, `insufficient`, or `invalid`.
- Extractor and validation method.

For the hotel demo:

| Claim | Required evidence |
|---|---|
| Total price | Selected offer and final checkout breakdown, including fees/taxes |
| Refundability | Cancellation conditions attached to the selected room/rate |
| Distance | Verified address plus a defined coordinate/distance calculation |
| Availability | Current selected-offer/checkout state |
| Completion | Final page state; no booking completion when booking is prohibited |

A marketing badge alone is not sufficient evidence of refundability. When sources conflict or required evidence is missing, the system must not label the claim verified.

The prototype should prefer structured fields and deterministic checks on controlled sites. LLM extraction can propose candidate values, but deterministic validation and source association must decide whether they are accepted.

### F. Policy enforcement gateway — deterministic Python rules

The gateway receives a typed action proposal and evaluates it against:

1. Active confirmed contract version.
2. Current browser origin and session.
3. Action category and target.
4. Required evidence and its verification status.
5. Approval state, if applicable.

Possible decisions:

- `ALLOW`: action is within scope and required preconditions hold.
- `DENY`: action violates a hard constraint or prohibited action.
- `PAUSE`: user confirmation or additional evidence is required.

No model-generated text can grant permission. The executor must receive a valid policy decision token/reference before performing the action. Decisions should be bound to the task, contract version, action, and relevant state, and expire quickly.

High-impact actions such as payment, booking confirmation, account changes, or personal-data disclosure are prohibited in the MVP. The demo should stop before them.

### G. Final-state verifier

After each meaningful action and at task completion:

- Re-read the current page state.
- Re-check price, cancellation, distance, domain and prohibited-action constraints.
- Detect page changes that invalidate earlier evidence.
- Confirm no forbidden action was executed through the controlled executor.
- Produce a result with supporting evidence and unresolved uncertainties.

A task can be reported as successful only when all mandatory constraints pass. Otherwise report rejected, incomplete, or needs-review.

### H. Audit and persistence

Planned storage:

- AWS Lambda: remotely hosted policy decision endpoint.
- DynamoDB: task versions, policy events and audit records.
- SQLite: local development and offline demonstration fallback.

Each audit event should include a unique event ID, task ID, contract version/hash, timestamp, action summary, evidence references, decision, and reason. Use idempotency keys/conditional writes to prevent duplicate records on retries.

The local rules engine must implement the same policy semantics as the cloud service. If neither can provide a decision, sensitive actions fail closed.

## 3. End-to-end workflow

1. User submits a task.
2. LLM proposes a structured contract.
3. Schema and semantic validation run.
4. User reviews and confirms the exact contract.
5. Server versions and hashes the contract.
6. Playwright opens an isolated, allow-listed demo site.
7. Page content is treated as untrusted data, not instructions.
8. Browser action adapter sends each proposed action to the policy gateway.
9. Evidence engine validates decision-critical claims.
10. Gateway returns allow, deny, or pause.
11. Executor performs only allowed actions and captures resulting state.
12. Verifier rechecks all hard constraints.
13. Audit receipt reports what was done, blocked, verified, or left uncertain.

## 4. Proposed repository structure

```text
INTENTLOCK/
├── README.md
├── docs/
│   ├── ARCHITECTURE.md
│   └── THREAT_MODEL.md
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── contracts/
│   │   ├── evidence/
│   │   ├── policy/
│   │   ├── sessions/
│   │   └── verification/
│   └── tests/
├── browser/
│   ├── executor/
│   ├── adapters/
│   └── tests/
├── frontend/
├── demo-sites/
│   ├── hotel-a/
│   ├── hotel-b/
│   └── hotel-c/
├── tests/
│   ├── clean/
│   └── adversarial/
└── scripts/
```

## 5. 24-hour MVP boundaries

### P0 — required

- Contract schema, review, confirmation, version and hash.
- One controlled Playwright action adapter.
- Deterministic allow/deny/pause gateway.
- Evidence checks for selected room cancellation and final total price.
- Final constraint verification and an audit receipt.
- Three controlled hotel demo sites: clean, misleading claim, and adversarial instruction.

### P1 — only after P0 is stable

- AWS Lambda policy endpoint and DynamoDB event store.
- Side-by-side baseline/protected evaluation.
- Spoken explanations via ElevenLabs (output only).

### Explicitly out of scope

- Real hotel bookings or payments.
- Real credentials or personal data.
- Arbitrary website coverage.
- Unrestricted cross-origin browsing.
- CAPTCHA bypass or access-control circumvention.
- Claims of complete prompt-injection prevention.

## 6. Evaluation

Use the same model, instructions, browser tools, sites, and test cases for baseline and protected runs.

Initial planned set: 10 clean and 10 adversarial scenarios, with three paired repetitions per configuration. Report sample size and measured values.

Metrics:

- Constraint preservation rate.
- Prohibited-action execution rate.
- Evidence completeness/accuracy.
- Benign task completion rate.
- False-rejection rate.
- Task duration and recovery rate.

Do not report target values as achieved results. Record actual results, failures, and limitations.

## 7. Reliability and security principles

- Treat website text, DOM content, images, and page metadata as untrusted.
- Keep model output separate from policy authority.
- Enforce all browser actions at one controlled adapter boundary.
- Restrict demo domains and outbound network access.
- Use isolated browser contexts.
- Keep secrets and personal data out of logs.
- Fail closed for sensitive actions when policy state is unavailable.
- Re-verify evidence when a page or selected offer changes.
- Keep a local demonstration path in case cloud services fail.
