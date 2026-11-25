# INTENTLOCK Backend — Prototype v0.2

The backend now includes:
- Pydantic intent-contract models and a deterministic proposal compiler
- User confirmation and contract hashing
- Deterministic ALLOW / DENY / PAUSE policy evaluation
- Three synthetic local hotel pages
- A Playwright runner that checks each local navigation and evaluates evidence-backed offers
- Pytest unit/API tests and a Playwright end-to-end test

**Compiler status:** The current compiler is deterministic and deliberately narrow. It does not call an LLM yet. Model output is not policy authority; a future LLM adapter must still produce a proposal that passes schema validation and explicit user confirmation.

## Requirements

- Python 3.11+
- Chromium installed by Playwright

## Setup (Windows PowerShell)

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m playwright install chromium
```

## Start the API and synthetic demo sites

```powershell
uvicorn app.main:app --reload
```

Open:
- API documentation: http://localhost:8000/docs
- Hotel demo index: http://localhost:8000/demo

The three sites are:

| Site | Scenario | Expected result |
|---|---|---|
| hotel-a | Refundable offer, ₹4,499 final total, 3.2 km | ALLOW |
| hotel-b | Marketing says free cancellation; selected rate is non-refundable | DENY |
| hotel-c | Hidden untrusted page instruction; ₹5,299 final total | DENY |

All pages are synthetic, hosted by the local FastAPI app. No real booking, payment, credentials, or personal data are used.

## Run the Playwright demonstration

### 1. Propose a contract

Send POST /contracts/propose:

```json
{
  "task": "Find a refundable hotel within 5 km for under ₹5,000 total. Do not book or pay.",
  "allowed_domains": ["localhost"]
}
```

Review the returned contract. Ensure clarification_required is empty.

### 2. Confirm it

Send POST /contracts/{contract_id}/confirm:

```json
{ "confirmed_by": "demo-user" }
```

### 3. Run the browser demo

Send POST /browser/run-demo:

```json
{ "contract_id": "THE_CONFIRMED_CONTRACT_ID" }
```

The runner:
1. Requires a confirmed contract with localhost in the allow-list.
2. Opens only http://localhost:8000/demo/... pages.
3. Checks each navigation with the policy engine before loading it.
4. Extracts hotel name, room ID, advertised price, selected-room policy, final checkout total, and distance from the synthetic pages.
5. Creates evidence records associated with each offer and its source URL.
6. Evaluates each offer against the confirmed constraints.
7. Detects the scripted hidden instruction on hotel-c and treats it as untrusted page content. It never sends that text to an LLM or executes it.
8. Submits a simulated booking action to the deterministic policy engine and verifies that it is denied. The booking action is never dispatched to the browser.
9. Returns an evidence-linked report with ALLOW / DENY outcomes.

The browser runner intentionally rejects non-localhost hosts and non-HTTP schemes. The optional INTENTLOCK_DEMO_BASE_URL setting is still restricted to localhost on port 8000.

## API endpoints

- GET /health
- GET /demo
- GET /demo/{hotel_id}
- GET /demo/{hotel_id}/policy
- GET /demo/{hotel_id}/checkout
- POST /contracts/propose
- GET /contracts/{contract_id}
- POST /contracts/{contract_id}/confirm
- POST /policy/evaluate
- POST /browser/run-demo

## Run tests

```powershell
pytest -q
```

The suite includes contract parsing, confirmation gating, prohibited actions, domain restrictions, evidence validation, synthetic site content, browser safety gates, and an end-to-end Playwright scenario that launches the local API and Chromium.

## Important limitations

- This is a controlled hackathon demonstration, not a production browser-security product.
- The compiler is rule-based; no LLM is integrated yet.
- Evidence is extracted from our own synthetic pages. This does not establish that arbitrary third-party websites are truthful.
- The hidden-instruction check is a scripted demo indicator, not a general prompt-injection detector.
- Policy enforcement applies only to actions routed through the controlled interface. A future real agent integration must not expose unrestricted browser control or alternate network tools to the model.
- No authentication is implemented. Keep the API bound to localhost; do not expose it publicly.
- Real bookings, payments, personal credentials, and personal-data disclosure are out of scope.
