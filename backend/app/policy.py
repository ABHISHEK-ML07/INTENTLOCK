from __future__ import annotations

from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse

from app.models import (
    ActionProposal, ActionType, ClaimType, ContractStatus, Decision,
    EvidenceRecord, EvidenceStatus, IntentContract, PolicyDecision
)


SENSITIVE_ACTIONS = {
    ActionType.BOOK, ActionType.PAY, ActionType.SHARE_PERSONAL_DATA,
    ActionType.CHANGE_ACCOUNT, ActionType.SUBMIT_FORM, ActionType.EXTERNAL_REQUEST,
}


def _host_matches(host: str, allowed_domain: str) -> bool:
    host = host.lower().rstrip(".")
    allowed_domain = allowed_domain.lower().rstrip(".")
    return host == allowed_domain or host.endswith("." + allowed_domain)


def _number(value: object) -> Decimal | None:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _evidence_for(action: ActionProposal, claim: ClaimType) -> EvidenceRecord | None:
    candidates = [e for e in action.evidence if e.claim_type == claim]
    if action.resource_id:
        candidates = [e for e in candidates if e.offer_id == action.resource_id]
    return candidates[-1] if candidates else None


def evaluate_action(contract: IntentContract, action: ActionProposal) -> PolicyDecision:
    reasons: list[str] = []
    required: list[ClaimType] = []
    decision = Decision.ALLOW

    def deny(reason: str) -> None:
        nonlocal decision
        decision = Decision.DENY
        reasons.append(reason)

    def pause(reason: str) -> None:
        nonlocal decision
        if decision != Decision.DENY:
            decision = Decision.PAUSE
        reasons.append(reason)

    if contract.status != ContractStatus.CONFIRMED:
        deny("The intent contract has not been confirmed by the user.")
        return PolicyDecision(
            decision=decision, action_id=action.action_id, contract_id=contract.contract_id,
            contract_version=contract.version, reasons=reasons,
        )

    if action.action_type in contract.constraints.prohibited_actions:
        deny(f"Action '{action.action_type.value}' is prohibited by the confirmed contract.")

    if action.action_type in SENSITIVE_ACTIONS and not action.user_approval_granted:
        pause(f"Action '{action.action_type.value}' requires explicit user approval.")

    # When an action identifies a target URL, enforce the same allow-list.
    if action.target_url:
        host = urlparse(str(action.target_url)).hostname or ""
        if not any(_host_matches(host, domain) for domain in contract.constraints.allowed_domains):
            deny(f"Target domain '{host}' is outside the confirmed allow-list.")
    elif action.action_type == ActionType.NAVIGATE:
        deny("Navigation requires a target URL.")

    if action.action_type == ActionType.RECOMMEND_OFFER:
        c = contract.constraints
        if c.max_total_price:
            required.append(ClaimType.TOTAL_PRICE)
        if c.refundable_required:
            required.append(ClaimType.REFUNDABILITY)
        if c.max_distance_km is not None:
            required.append(ClaimType.DISTANCE_KM)

        accepted: dict[ClaimType, EvidenceRecord] = {}
        for claim in required:
            record = _evidence_for(action, claim)
            if record is None:
                pause(f"Missing evidence for required claim '{claim.value}'.")
                continue
            if record.status != EvidenceStatus.VERIFIED:
                pause(f"Evidence for '{claim.value}' is {record.status.value}; it cannot support a verified recommendation.")
                continue
            if action.resource_id and record.offer_id != action.resource_id:
                deny(f"Evidence for '{claim.value}' does not belong to the selected offer.")
                continue

            source_host = urlparse(str(record.source_url)).hostname or ""
            if source_host.lower().rstrip(".") != record.source_origin.lower().rstrip("."):
                pause(f"Evidence source-origin metadata does not match its source URL for '{claim.value}'.")
                continue
            if not any(_host_matches(source_host, domain) for domain in c.allowed_domains):
                pause(f"Evidence for '{claim.value}' comes from a domain outside the confirmed allow-list.")
                continue
            accepted[claim] = record

        price = accepted.get(ClaimType.TOTAL_PRICE)
        if price and c.max_total_price:
            if c.max_total_price.basis != "total":
                pause("The confirmed price constraint is not defined as a total-price limit.")
            if price.includes_fees_and_taxes is not True:
                pause("Total-price evidence must explicitly include fees and taxes.")
            amount = _number(price.value)
            if amount is None:
                pause("Total-price evidence is not a valid numeric amount.")
            elif amount > c.max_total_price.amount:
                deny(f"Verified total price {amount} exceeds the user's maximum {c.max_total_price.amount}.")

        refund = accepted.get(ClaimType.REFUNDABILITY)
        if refund and c.refundable_required and refund.value is not True:
            deny("The selected offer is not verified as refundable.")

        distance = accepted.get(ClaimType.DISTANCE_KM)
        if distance and c.max_distance_km is not None:
            amount = _number(distance.value)
            if amount is None:
                pause("Distance evidence is not a valid numeric value.")
            elif amount > c.max_distance_km:
                deny(f"Verified distance {amount} km exceeds the user's maximum {c.max_distance_km} km.")

    if not reasons:
        reasons.append("Action is within the confirmed contract and its required preconditions passed.")

    return PolicyDecision(
        decision=decision, action_id=action.action_id, contract_id=contract.contract_id,
        contract_version=contract.version, reasons=reasons, required_evidence=required,
    )
