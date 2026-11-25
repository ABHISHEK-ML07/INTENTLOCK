# INTENTLOCK

**The Constraint Integrity Engine for the Autonomous Web**

INTENTLOCK is a proposed browser-automation safety layer for keeping autonomous web tasks faithful to a user's confirmed instructions. It focuses on three related risks:

1. **Instruction integrity** — a webpage may contain malicious or irrelevant instructions that try to redirect an agent.
2. **Information integrity** — marketing claims may conflict with the actual terms, selected offer, or final checkout state.
3. **Action integrity** — an agent may attempt an action the user did not authorise.

> **Project status:** Hackathon prototype in development. The capabilities described below are the intended design and MVP scope; they should not be interpreted as already implemented or independently validated.

## The idea

A user might ask:

> Find a refundable hotel within 5 km for less than ₹5,000 total. Compare options, but do not book or pay.

INTENTLOCK is designed to turn that request into a user-confirmed contract, gather evidence for important claims, check browser actions against the contract, and verify the final result.

## Three core components

### 1. Intent Contract Compiler

Converts a natural-language request into structured constraints, such as:

- Maximum total price: ₹5,000
- Maximum distance: 5 km
- Cancellation: refundable
- Booking: not authorised
- Payment: not authorised

The user reviews and confirms the contract before execution. The system should not silently change the confirmed constraints in response to webpage content.

### 2. Evidence Provenance Engine

Collects and records the evidence behind decision-critical claims. For the hotel example, this may include:

- The selected room's cancellation conditions
- The selected offer's price
- The final checkout total, including fees and taxes
- The source URL and time at which the evidence was captured

Conflicting or insufficient evidence should be marked accordingly rather than presented as verified fact. A marketing badge alone is not sufficient proof of a room's cancellation terms.

### 3. Policy-Enforced Execution Gateway

Checks agent-controlled browser actions against the confirmed contract. The intended decision model is:

- **Allow** actions within the confirmed scope
- **Block** actions that violate the contract
- **Pause** when user approval or additional evidence is required

The final state is checked against the original constraints, and decisions are recorded in an audit trail.

## Planned workflow

1. User describes a task in natural language.
2. Intent compiler proposes a structured contract.
3. User reviews and confirms the contract.
4. Browser automation visits the permitted websites.
5. Evidence engine extracts and checks decision-critical claims.
6. Policy gateway evaluates actions before they execute.
7. Final-state verification checks the result against the contract.
8. An audit record explains the outcome and supporting evidence.

## Proposed technology stack

| Layer | Planned technology |
|---|---|
| Frontend | Next.js, TypeScript, Tailwind CSS |
| Backend | Python, FastAPI |
| Browser automation | Playwright |
| Intent extraction | LLM with structured outputs |
| Contract validation and policy | Pydantic and deterministic Python rules |
| Evidence collection | DOM and accessibility-tree extraction, source and state checks |
| Cloud policy service | AWS Lambda |
| Audit storage | Amazon DynamoDB |
| Local development/fallback | SQLite |
| Spoken explanations (optional) | ElevenLabs |

The LLM is intended to interpret language and help extract candidate information. Deterministic application code is intended to validate the contract and make policy decisions.

## Hackathon MVP scope

The initial demonstration is deliberately narrow: a controlled hotel-comparison workflow across mock websites.

Planned scenarios:

- A legitimate refundable offer within the user's constraints
- A misleading “free cancellation” banner contradicted by the selected room's policy
- A final checkout total that exceeds the user's price ceiling
- A webpage containing instructions that attempt to redirect the agent
- An attempt to book, pay, or disclose information without authorisation

The prototype should demonstrate both safe rejection and successful completion of legitimate tasks. It is not intended to process real payments or use real personal credentials.

## Evaluation plan

We plan to compare a baseline browser agent with the same agent operating through INTENTLOCK, using the same model, tools, websites, prompts, and test scenarios.

Initial measures:

- **Constraint preservation:** proportion of completed results satisfying every hard constraint
- **Unauthorised action rate:** prohibited actions that actually execute
- **Evidence completeness:** decision-critical claims with traceable supporting evidence
- **Benign task completion:** legitimate tasks completed successfully
- **False rejection rate:** legitimate actions incorrectly blocked

The initial test set is planned to include clean and adversarial scenarios with repeated runs. Results will be reported as measured; no performance claims are made in advance.

## Security boundaries and limitations

INTENTLOCK is designed to enforce decisions at the browser-execution boundary it controls. It must not be described as a guarantee against every browser vulnerability, malicious script, model failure, or data leak through an external agent service.

The prototype should use isolated browser sessions, mock websites, synthetic data, and restricted network access. If policy authorisation cannot be verified, sensitive actions should fail closed.

## Repository status

This repository is the starting point for the INTENTLOCK hackathon prototype. Implementation, test cases, architecture details, and measured results will be added as they are built and verified.

## Track

**wHACKiest 2026 — Beyond the Browser**

---

*Build principle: LLMs interpret. Deterministic code validates and decides. The controlled browser executes. The system verifies the outcome.*
