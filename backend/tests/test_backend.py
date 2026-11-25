from datetime import datetime, timezone
from decimal import Decimal

from fastapi.testclient import TestClient

from app.compiler import compile_contract
from app.main import app
from app.models import (
    ActionProposal, ActionType, ClaimType, ContractConstraints, ContractStatus,
    Decision, EvidenceRecord, EvidenceStatus, IntentContract, PriceBasis, PriceConstraint,
)
from app.policy import evaluate_action


client = TestClient(app)


def make_contract() -> IntentContract:
    return IntentContract(
        goal="Find and compare a refundable hotel",
        constraints=ContractConstraints(
            max_total_price=PriceConstraint(amount=Decimal("5000"), currency="INR", basis=PriceBasis.TOTAL),
            max_distance_km=Decimal("5"),
            refundable_required=True,
            allowed_domains=["hotels.demo.local"],
        ),
        status=ContractStatus.CONFIRMED,
        confirmed_at=datetime.now(timezone.utc),
        confirmed_by="test-user",
        contract_hash="test-hash",
    )


def make_evidence(claim, value, *, fees=None, status=EvidenceStatus.VERIFIED, origin="hotels.demo.local"):
    return EvidenceRecord(
        claim_type=claim, value=value, status=status,
        source_url="https://hotels.demo.local/offer/room-1",
        source_origin=origin, offer_id="room-1", includes_fees_and_taxes=fees,
    )


def test_compiler_extracts_constraints_and_keeps_dangerous_actions_prohibited():
    contract = compile_contract(
        "Find a refundable hotel within 5 km for under ₹5,000 total. Do not book or pay.",
        ["hotels.demo.local"],
    )
    assert contract.status == ContractStatus.PROPOSED
    assert contract.constraints.max_total_price.amount == Decimal("5000")
    assert contract.constraints.max_total_price.basis == PriceBasis.TOTAL
    assert contract.constraints.max_distance_km == Decimal("5")
    assert contract.constraints.refundable_required is True
    assert {ActionType.BOOK, ActionType.PAY, ActionType.SHARE_PERSONAL_DATA}.issubset(
        contract.constraints.prohibited_actions
    )
    assert contract.clarification_required == []


def test_compiler_requires_clarification_for_ambiguous_price_and_missing_domains():
    contract = compile_contract("Find a refundable hotel under ₹5,000 within 5 km")
    assert contract.clarification_required
    assert any("total price" in item for item in contract.clarification_required)
    assert any("allowed to visit" in item for item in contract.clarification_required)


def test_unconfirmed_contract_denies_actions():
    contract = compile_contract(
        "Find a refundable hotel within 5 km for under ₹5,000 total.",
        ["hotels.demo.local"],
    )
    action = ActionProposal(action_type=ActionType.READ, label="Read hotel page", target_url="https://hotels.demo.local/search")
    assert evaluate_action(contract, action).decision == Decision.DENY


def test_non_recommendation_action_requires_target_url():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ActionProposal(action_type=ActionType.READ, label="Read page")


def test_compiler_does_not_misread_non_refundable_as_refundable():
    contract = compile_contract(
        "Find a non-refundable hotel within 5 km for under ₹5,000 total.",
        ["hotels.demo.local"],
    )
    assert contract.constraints.refundable_required is False
    assert any("whether the offer must be refundable" in item for item in contract.clarification_required)


def test_domain_allowlist_blocks_lookalike_domain():
    action = ActionProposal(
        action_type=ActionType.NAVIGATE,
        label="Open untrusted host",
        target_url="https://hotels.demo.local.evil.test",
    )
    result = evaluate_action(make_contract(), action)
    assert result.decision == Decision.DENY


def test_prohibited_booking_is_denied_even_if_approval_flag_is_true():
    action = ActionProposal(
        action_type=ActionType.BOOK, label="Book room",
        target_url="https://hotels.demo.local/checkout", user_approval_granted=True
    )
    assert evaluate_action(make_contract(), action).decision == Decision.DENY


def test_sensitive_form_submission_pauses_for_approval():
    action = ActionProposal(
        action_type=ActionType.SUBMIT_FORM, label="Submit form",
        target_url="https://hotels.demo.local/application"
    )
    assert evaluate_action(make_contract(), action).decision == Decision.PAUSE


def test_valid_offer_evidence_is_allowed():
    action = ActionProposal(
        action_type=ActionType.RECOMMEND_OFFER, label="Recommend room", resource_id="room-1",
        evidence=[
            make_evidence(ClaimType.TOTAL_PRICE, "4499", fees=True),
            make_evidence(ClaimType.REFUNDABILITY, True),
            make_evidence(ClaimType.DISTANCE_KM, "3.2"),
        ],
    )
    assert evaluate_action(make_contract(), action).decision == Decision.ALLOW


def test_offer_over_price_limit_is_denied():
    action = ActionProposal(
        action_type=ActionType.RECOMMEND_OFFER, label="Recommend room", resource_id="room-1",
        evidence=[
            make_evidence(ClaimType.TOTAL_PRICE, "5299", fees=True),
            make_evidence(ClaimType.REFUNDABILITY, True),
            make_evidence(ClaimType.DISTANCE_KM, "3.2"),
        ],
    )
    assert evaluate_action(make_contract(), action).decision == Decision.DENY


def test_missing_tax_inclusion_pauses_recommendation():
    action = ActionProposal(
        action_type=ActionType.RECOMMEND_OFFER, label="Recommend room", resource_id="room-1",
        evidence=[
            make_evidence(ClaimType.TOTAL_PRICE, "4499"),
            make_evidence(ClaimType.REFUNDABILITY, True),
            make_evidence(ClaimType.DISTANCE_KM, "3.2"),
        ],
    )
    assert evaluate_action(make_contract(), action).decision == Decision.PAUSE


def test_non_refundable_offer_is_denied():
    action = ActionProposal(
        action_type=ActionType.RECOMMEND_OFFER, label="Recommend room", resource_id="room-1",
        evidence=[
            make_evidence(ClaimType.TOTAL_PRICE, "4499", fees=True),
            make_evidence(ClaimType.REFUNDABILITY, False),
            make_evidence(ClaimType.DISTANCE_KM, "3.2"),
        ],
    )
    assert evaluate_action(make_contract(), action).decision == Decision.DENY


def test_conflicting_evidence_pauses_recommendation():
    action = ActionProposal(
        action_type=ActionType.RECOMMEND_OFFER, label="Recommend room", resource_id="room-1",
        evidence=[
            make_evidence(ClaimType.TOTAL_PRICE, "4499", fees=True),
            make_evidence(ClaimType.REFUNDABILITY, False, status=EvidenceStatus.CONFLICTING),
            make_evidence(ClaimType.DISTANCE_KM, "3.2"),
        ],
    )
    assert evaluate_action(make_contract(), action).decision == Decision.PAUSE


def test_evidence_source_origin_must_match_url():
    action = ActionProposal(
        action_type=ActionType.RECOMMEND_OFFER, label="Recommend room", resource_id="room-1",
        evidence=[
            make_evidence(ClaimType.TOTAL_PRICE, "4499", fees=True, origin="trusted-looking.example"),
            make_evidence(ClaimType.REFUNDABILITY, True),
            make_evidence(ClaimType.DISTANCE_KM, "3.2"),
        ],
    )
    assert evaluate_action(make_contract(), action).decision == Decision.PAUSE


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_proposal_cannot_be_confirmed_when_clarification_is_pending():
    response = client.post("/contracts/propose", json={
        "task": "Find a refundable hotel under ₹5,000 within 5 km.",
        "allowed_domains": ["hotels.demo.local"],
    })
    assert response.status_code == 201
    proposed = response.json()
    assert proposed["status"] == "proposed"
    assert proposed["clarification_required"]
    confirmed = client.post(
        f"/contracts/{proposed['contract_id']}/confirm",
        json={"confirmed_by": "test-user"},
    )
    assert confirmed.status_code == 409


def test_valid_proposal_can_be_confirmed_and_hashed():
    response = client.post("/contracts/propose", json={
        "task": "Find a refundable hotel within 5 km for under ₹5,000 total. Do not book or pay.",
        "allowed_domains": ["hotels.demo.local"],
    })
    assert response.status_code == 201
    proposed = response.json()
    assert proposed["clarification_required"] == []
    confirmed = client.post(
        f"/contracts/{proposed['contract_id']}/confirm",
        json={"confirmed_by": "test-user"},
    )
    assert confirmed.status_code == 200
    body = confirmed.json()
    assert body["status"] == "confirmed"
    assert len(body["contract_hash"]) == 64
