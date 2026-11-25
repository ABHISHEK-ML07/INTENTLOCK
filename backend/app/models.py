from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
import re
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ContractStatus(StrEnum):
    PROPOSED = "proposed"
    CONFIRMED = "confirmed"


class PriceBasis(StrEnum):
    TOTAL = "total"
    PER_NIGHT = "per_night"
    UNSPECIFIED = "unspecified"


class ActionType(StrEnum):
    NAVIGATE = "navigate"
    READ = "read"
    SELECT_OFFER = "select_offer"
    RECOMMEND_OFFER = "recommend_offer"
    FILL_FORM = "fill_form"
    SUBMIT_FORM = "submit_form"
    BOOK = "book"
    PAY = "pay"
    SHARE_PERSONAL_DATA = "share_personal_data"
    CHANGE_ACCOUNT = "change_account"
    EXTERNAL_REQUEST = "external_request"


class Decision(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    PAUSE = "pause"


class EvidenceStatus(StrEnum):
    VERIFIED = "verified"
    CONFLICTING = "conflicting"
    INSUFFICIENT = "insufficient"
    INVALID = "invalid"


class ClaimType(StrEnum):
    TOTAL_PRICE = "total_price"
    REFUNDABILITY = "refundability"
    DISTANCE_KM = "distance_km"
    AVAILABILITY = "availability"


class PriceConstraint(StrictModel):
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    currency: str = Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    basis: PriceBasis = PriceBasis.UNSPECIFIED


class ContractConstraints(StrictModel):
    max_total_price: PriceConstraint | None = None
    max_distance_km: Decimal | None = Field(default=None, gt=0, le=10000)
    refundable_required: bool = False
    allowed_domains: list[str] = Field(default_factory=list, max_length=20)
    # Real bookings, payments and personal-data disclosure are prohibited in this MVP.
    prohibited_actions: set[ActionType] = Field(default_factory=lambda: {
        ActionType.BOOK, ActionType.PAY, ActionType.SHARE_PERSONAL_DATA
    })

    @field_validator("allowed_domains")
    @classmethod
    def normalise_domains(cls, values: list[str]) -> list[str]:
        result: list[str] = []
        for value in values:
            domain = value.lower().strip().rstrip(".")
            if not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)*", domain):
                raise ValueError(f"Invalid domain: {value}")
            if domain not in result:
                result.append(domain)
        return result


class IntentContract(StrictModel):
    contract_id: str = Field(default_factory=lambda: str(uuid4()))
    task_id: str = Field(default_factory=lambda: str(uuid4()))
    version: int = Field(default=1, ge=1)
    goal: str = Field(min_length=8, max_length=1000)
    constraints: ContractConstraints
    status: ContractStatus = ContractStatus.PROPOSED
    assumptions: list[str] = Field(default_factory=list)
    clarification_required: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    confirmed_at: datetime | None = None
    confirmed_by: str | None = None
    contract_hash: str | None = None

    @model_validator(mode="after")
    def confirmation_consistency(self) -> "IntentContract":
        if self.status == ContractStatus.CONFIRMED:
            if not self.confirmed_at or not self.confirmed_by or not self.contract_hash:
                raise ValueError("Confirmed contracts require confirmed_at, confirmed_by and contract_hash")
            if self.clarification_required:
                raise ValueError("A contract requiring clarification cannot be confirmed")
        return self


class ConfirmContractRequest(StrictModel):
    confirmed_by: str = Field(min_length=1, max_length=120)


class EvidenceRecord(StrictModel):
    claim_type: ClaimType
    value: Any
    status: EvidenceStatus
    source_url: HttpUrl
    source_origin: str = Field(min_length=1, max_length=255)
    captured_at: datetime = Field(default_factory=utc_now)
    offer_id: str = Field(min_length=1, max_length=120)
    includes_fees_and_taxes: bool | None = None
    extractor: str = Field(default="dom", max_length=80)
    evidence_ref: str | None = Field(default=None, max_length=200)


class ActionProposal(StrictModel):
    action_id: str = Field(default_factory=lambda: str(uuid4()))
    action_type: ActionType
    label: str = Field(min_length=1, max_length=300)
    target_url: HttpUrl | None = None
    resource_id: str | None = Field(default=None, max_length=120)
    evidence: list[EvidenceRecord] = Field(default_factory=list)
    user_approval_granted: bool = False

    @model_validator(mode="after")
    def require_action_context(self) -> "ActionProposal":
        # Every browser operation needs an explicit page context. Offer
        # recommendations can instead be bound to offer-specific evidence.
        if self.action_type != ActionType.RECOMMEND_OFFER and self.target_url is None:
            raise ValueError("Browser actions require a target_url so the policy gateway can enforce the domain allow-list")
        if self.action_type == ActionType.RECOMMEND_OFFER and not self.resource_id:
            raise ValueError("Offer recommendations require a resource_id")
        return self


class PolicyEvaluationRequest(StrictModel):
    contract_id: str
    action: ActionProposal


class PolicyDecision(StrictModel):
    decision: Decision
    action_id: str
    contract_id: str
    contract_version: int
    reasons: list[str]
    checked_at: datetime = Field(default_factory=utc_now)
    required_evidence: list[ClaimType] = Field(default_factory=list)


class CompileRequest(StrictModel):
    task: str = Field(min_length=8, max_length=2000)
    allowed_domains: list[str] = Field(default_factory=list, max_length=20)


class HealthResponse(StrictModel):
    status: str = "ok"
    service: str = "intentlock-backend"
    compiler_mode: str = "deterministic_prototype"
