from __future__ import annotations

from datetime import datetime, timezone
from pydantic import BaseModel, ConfigDict, Field

from app.models import Decision


class DemoRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    contract_id: str = Field(min_length=1)


class DemoOfferResult(BaseModel):
    hotel_id: str
    hotel_name: str
    room_id: str
    marketing_cancellation_claim: str
    detailed_cancellation_policy: str
    base_price_inr: str
    final_total_inr: str
    distance_km: str
    marketing_policy_conflict: bool
    suspicious_page_instruction_detected: bool
    simulated_booking_blocked: bool
    instruction_handling: str
    decision: Decision
    eligible: bool
    reasons: list[str]
    evidence_sources: list[str]
    navigation_checks_passed: int


class DemoRunResponse(BaseModel):
    contract_id: str
    contract_version: int
    demo_mode: str = "synthetic_local_websites"
    offers: list[DemoOfferResult]
    eligible_count: int
    rejected_or_paused_count: int
    completed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    disclaimer: str = "Synthetic demonstration only. No real booking, payment, or personal data is used."
