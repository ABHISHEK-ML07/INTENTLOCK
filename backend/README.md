# INTENTLOCK Backend — Prototype v0.1

This is the first executable backend slice: a deterministic prototype contract compiler, Pydantic validation, SQLite contract storage, FastAPI endpoints, and a deterministic action-policy evaluator.

**Important:** The current compiler is deliberately rule-based and supports a narrow hotel-search phrasing. It does not call an LLM yet. An LLM adapter may later propose structured fields, but its output must still pass schema validation, user confirmation, and deterministic policy checks.

## Requirements

- Python 3.11+

## Setup (Windows PowerShell)

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run

```powershell
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000/docs for interactive API documentation.

## 1. Propose a contract

Send POST /contracts/propose:

```json
{
  "task": "Find a refundable hotel within 5 km for under ₹5,000 total. Do not book or pay.",
  "allowed_domains": ["hotels.demo.local"]
}
```

The response is a **proposal**, not permission to act. Review the extracted constraints and make sure clarification_required is empty.

## 2. Confirm the contract

Send POST /contracts/{contract_id}/confirm:

```json
{ "confirmed_by": "user" }
```

A proposal with unresolved clarification items cannot be confirmed. The MVP also requires the price ceiling to be explicitly defined as a total-price limit including fees and taxes.

## 3. Evaluate an action

Send POST /policy/evaluate with a confirmed contract_id and an action. For recommend_offer, include evidence records matching the same resource_id/offer for every required claim:

- total_price (must explicitly include fees and taxes)
- refundability
- distance_km

Evidence must be marked verified, must identify a source URL and origin, and must come from a domain in the confirmed allow-list. Missing or conflicting evidence causes a pause; a verified hard-constraint violation is denied.

## Decisions

- **allow** — the action passes deterministic checks.
- **deny** — the action violates a hard constraint or prohibited action.
- **pause** — more evidence or approval is required.

The MVP prohibits real booking, payment, and personal-data disclosure by default.

## Tests

```powershell
pytest -q
```

The test suite covers conservative contract parsing, confirmation gating, prohibited actions, domain matching, source-origin validation, price/refundability evidence, and API behavior.

## Limitations

- This API does not yet drive a browser. Playwright integration and a single controlled action adapter are the next implementation step.
- Every agent-controlled browser action must eventually pass through that adapter; actions that bypass it are outside the policy guarantee.
- Evidence status is currently supplied to the policy engine. The evidence collector still needs to be built and tested against controlled demo sites.
- No authentication is implemented. Keep the API bound to localhost during development; do not expose it publicly.
- The prototype does not process real bookings or payments and must not use real credentials or personal data.
