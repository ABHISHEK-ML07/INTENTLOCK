from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.compiler import compile_contract
from app.browser.runner import DemoExecutionError, run_hotel_demo
from app.demo_models import DemoRunRequest, DemoRunResponse
from app.demo_sites import router as demo_sites_router
from app.models import (
    CompileRequest, ConfirmContractRequest, ContractStatus, HealthResponse,
    IntentContract, PolicyDecision, PolicyEvaluationRequest
)
from app.policy import evaluate_action
from app.storage import ContractNotFoundError, ContractStore, canonical_contract_payload


DB_PATH = os.getenv("INTENTLOCK_DB_PATH", "intentlock.db")
store = ContractStore(DB_PATH)

app = FastAPI(
    title="INTENTLOCK API",
    version="0.2.0",
    description="Prototype API for user-confirmed intent contracts and deterministic browser-action policy decisions.",
)

# Allow only the local Vite development server used by the dashboard.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()


@app.post("/contracts/propose", response_model=IntentContract, status_code=201)
def propose_contract(request: CompileRequest) -> IntentContract:
    requested_domains = {
        domain.strip().lower().rstrip(".")
        for domain in request.allowed_domains
        if domain.strip()
    }
    if requested_domains != {"localhost"}:
        raise HTTPException(
            status_code=400,
            detail="This local prototype only permits the localhost demo domain.",
        )
    contract = compile_contract(request.task, ["localhost"])
    store.save(contract)
    return contract


@app.get("/contracts/{contract_id}", response_model=IntentContract)
def get_contract(contract_id: str) -> IntentContract:
    try:
        return store.get(contract_id)
    except ContractNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Contract not found") from exc


@app.post("/contracts/{contract_id}/confirm", response_model=IntentContract)
def confirm_contract(contract_id: str, request: ConfirmContractRequest) -> IntentContract:
    try:
        contract = store.get(contract_id)
    except ContractNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Contract not found") from exc

    if contract.status != ContractStatus.PROPOSED:
        raise HTTPException(status_code=409, detail="Only proposed contracts can be confirmed")
    if contract.clarification_required:
        raise HTTPException(
            status_code=409,
            detail={"message": "Resolve clarification items before confirmation", "items": contract.clarification_required},
        )
    if contract.constraints.max_total_price and contract.constraints.max_total_price.basis != "total":
        raise HTTPException(
            status_code=409,
            detail="The MVP requires a confirmed total-price limit including fees and taxes",
        )

    confirmed_at = datetime.now(timezone.utc)
    candidate = contract.model_copy(update={
        "status": ContractStatus.CONFIRMED,
        "confirmed_at": confirmed_at,
        "confirmed_by": request.confirmed_by,
        "contract_hash": None,
    })
    digest = hashlib.sha256(canonical_contract_payload(candidate)).hexdigest()
    confirmed = candidate.model_copy(update={"contract_hash": digest})
    # model_copy does not validate updates; reconstruct to run model validators.
    confirmed = IntentContract.model_validate(confirmed.model_dump())
    store.save(confirmed)
    return confirmed


@app.post("/policy/evaluate", response_model=PolicyDecision)
def evaluate_policy(request: PolicyEvaluationRequest) -> PolicyDecision:
    try:
        contract = store.get(request.contract_id)
    except ContractNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Contract not found") from exc
    return evaluate_action(contract, request.action)


app.include_router(demo_sites_router)


@app.post("/browser/run-demo", response_model=DemoRunResponse)
async def run_browser_demo(request: DemoRunRequest) -> DemoRunResponse:
    """Run the controlled, localhost-only three-hotel Playwright demonstration."""
    try:
        contract = store.get(request.contract_id)
    except ContractNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Contract not found") from exc
    try:
        return await run_hotel_demo(contract)
    except DemoExecutionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
