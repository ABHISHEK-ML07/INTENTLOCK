# INTENTLOCK Dashboard

A React + TypeScript + Vite dashboard for the local FastAPI demonstration.

## Start the backend first

In Anaconda Prompt / PowerShell:

```powershell
cd INTENTLOCK\backend
conda activate intentlock
uvicorn app.main:app --reload
```

The backend must be available at http://localhost:8000.

## Start the frontend

Open a second terminal:

```powershell
cd INTENTLOCK\frontend
npm install
npm run dev
```

Open http://localhost:5173.

## Dashboard workflow

1. Enter a natural-language task and allowed hostnames.
2. Compile the intent proposal.
3. Review the extracted constraints and any clarification warnings.
4. Confirm the proposal.
5. Run the protected local browser demonstration.
6. Inspect offer decisions, evidence sources, conflicts, detected injected text and blocked simulated booking.

The dashboard uses VITE_API_BASE_URL if supplied; otherwise it calls http://localhost:8000.

## Safety and prototype limitations

- The demo's allowed site should remain localhost.
- The frontend does not grant permissions. FastAPI and the deterministic policy engine remain responsible for contract confirmation and action decisions.
- The evidence ledger displays data extracted from the three synthetic sites only.
- Activity log entries are client-side session logs, not a tamper-resistant server audit trail.
- There is no authentication or production deployment hardening. Keep the backend on localhost.
