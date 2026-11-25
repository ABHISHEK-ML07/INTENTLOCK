# INTENTLOCK

**The Constraint Integrity Engine for the Autonomous Web**

INTENTLOCK is a hackathon prototype for preserving a user's confirmed constraints during autonomous browser tasks. It focuses on instruction integrity, information integrity and action integrity.

## Current implementation

- Deterministic natural-language contract proposal compiler
- User confirmation flow and SHA-256 contract hash
- Deterministic ALLOW / DENY / PAUSE policy engine
- Three synthetic local hotel websites representing valid, misleading and adversarial cases
- Playwright browser runner restricted to the localhost demo
- FastAPI backend and SQLite contract storage
- React + TypeScript judge dashboard with contract review, execution results, evidence ledger and session activity log

**Prototype boundary:** The compiler is rule-based, not LLM-powered. Evidence is extracted from the controlled synthetic websites, not arbitrary real websites. The dashboard activity log is session-side, not a tamper-resistant audit service. The system is not a production browser or a guarantee against all agent threats.

## Run locally (Windows)

You need Python 3.11+, Node.js 20+, and npm.

### Terminal 1 — backend

```powershell
cd INTENTLOCK\backend
conda create -n intentlock python=3.11 -y
conda activate intentlock
pip install -r requirements.txt
python -m playwright install chromium
uvicorn app.main:app --reload
```

The backend API is at http://localhost:8000. Open http://localhost:8000/docs for API documentation or http://localhost:8000/demo to inspect the three mock hotel pages.

### Terminal 2 — frontend dashboard

```powershell
cd INTENTLOCK\frontend
npm install
npm run dev
```

Open **http://localhost:5173**.

## Dashboard flow

1. Enter the task in natural language. The example task is already filled in.
2. Compile the proposal and review the extracted constraints.
3. Confirm the contract. It cannot be confirmed if clarification is still required.
4. Run the protected browser demonstration.
5. Inspect each hotel's ALLOW / DENY result, evidence sources, policy conflict and simulated blocked booking.
6. Open Evidence Ledger and Activity Log to review the run.

The local demo domain should remain `localhost`. Do not add real websites, credentials or personal data.

## Three demo scenarios

| Site | Scenario | Expected policy result |
|---|---|---|
| Cedar Grove Hotel | Refundable, 3.2 km, ₹4,499 final total | ALLOW |
| Metro Crown Inn | Marketing badge says free cancellation; selected room is non-refundable | DENY |
| Lakeview Residency | Hidden untrusted page instruction; ₹5,299 final total | DENY |

No real booking or payment action exists in the demonstration. A simulated booking proposal on the adversarial scenario is evaluated by the policy engine and must be denied before any browser action is dispatched.

## Verification

Backend tests (including the Playwright end-to-end scenario):

```powershell
cd backend
pytest -q
```

Frontend production build:

```powershell
cd frontend
npm install
npm run build
```

GitHub Actions workflows run the backend tests and frontend build separately.

## Architecture

- **Intent Contract Compiler:** proposes structured constraints; it does not authorize actions.
- **Policy Engine:** deterministic gate for navigation and offer recommendations.
- **Evidence Collector:** reads selected-room policy, final checkout total and distance from controlled demo HTML.
- **Playwright runner:** browser execution for local demo pages, with a policy check before each navigation.
- **Dashboard:** user-facing review and result visualization.

## Track

**wHACKiest 2026 — Beyond the Browser**

*Build principle: LLMs interpret. Deterministic code validates and decides. The controlled browser executes. The verifier checks the outcome.*
