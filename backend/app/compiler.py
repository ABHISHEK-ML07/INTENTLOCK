from __future__ import annotations

import re
from decimal import Decimal
from typing import Iterable

from app.models import (
    ActionType, ContractConstraints, IntentContract, PriceBasis, PriceConstraint
)


_AMOUNT_PATTERNS = (
    re.compile(r"(?:₹|INR\s*)([0-9][0-9,]*(?:\.[0-9]{1,2})?)", re.IGNORECASE),
    re.compile(r"(?:under|below|less than|maximum|max(?:imum)?(?:\s+total)?(?:\s+price)?\s+of?)\s+₹?\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)", re.IGNORECASE),
)
_DISTANCE_RE = re.compile(
    r"(?:within|maximum|max|up to|under)\s+([0-9]+(?:\.[0-9]+)?)\s*(?:km|kilomet(?:er|re)s?)\b",
    re.IGNORECASE,
)


def _extract_price(task: str) -> PriceConstraint | None:
    match = next((m for pattern in _AMOUNT_PATTERNS if (m := pattern.search(task))), None)
    if not match:
        return None
    amount = Decimal(match.group(1).replace(",", ""))
    lowered = task.lower()
    if "per night" in lowered or "/night" in lowered:
        basis = PriceBasis.PER_NIGHT
    elif "total" in lowered or "including taxes" in lowered or "all inclusive" in lowered:
        basis = PriceBasis.TOTAL
    else:
        basis = PriceBasis.UNSPECIFIED
    return PriceConstraint(amount=amount, currency="INR", basis=basis)


def _extract_distance(task: str) -> Decimal | None:
    match = _DISTANCE_RE.search(task)
    return Decimal(match.group(1)) if match else None


def _extra_prohibitions(task: str) -> set[ActionType]:
    text = task.lower().replace("’", "'")
    actions: set[ActionType] = set()
    if re.search(r"\b(do not|don't|dont|never|without)\s+(?:make\s+)?(?:a\s+)?booking|\bno booking\b|\bdon't book\b|\bdo not book\b", text):
        actions.add(ActionType.BOOK)
    if re.search(r"\b(do not|don't|dont|never|without)\s+(?:make\s+)?(?:a\s+)?payment|\bno payment\b|\bdon't pay\b|\bdo not pay\b", text):
        actions.add(ActionType.PAY)
    if re.search(r"\b(do not|don't|dont|never|without)\s+(?:share|send|disclose)\s+(?:any\s+)?(?:personal|private)\s+(?:data|information|details)", text):
        actions.add(ActionType.SHARE_PERSONAL_DATA)
    return actions


def compile_contract(task: str, allowed_domains: Iterable[str] = ()) -> IntentContract:
    """Create a conservative proposal; it never confirms or authorises a task.

    This first compiler is deterministic and deliberately narrow. An LLM adapter
    may later propose fields, but its output must pass the same validation and
    user-confirmation flow.
    """
    price = _extract_price(task)
    distance = _extract_distance(task)
    lowered = task.lower()
    refundable = any(term in lowered for term in ("refundable", "free cancellation", "free-cancellation"))

    clarifications: list[str] = []
    assumptions: list[str] = []
    if price is None:
        clarifications.append("Specify a maximum price, including the currency.")
    elif price.basis == PriceBasis.UNSPECIFIED:
        clarifications.append("Clarify whether the price limit is per night or the total price including fees and taxes.")
    if "hotel" in lowered or "booking" in lowered:
        if distance is None:
            clarifications.append("Specify a maximum distance and the location from which distance should be measured.")
        if not refundable:
            clarifications.append("Clarify whether the offer must be refundable.")
    if not allowed_domains:
        clarifications.append("Select the websites/domains the browser is allowed to visit.")
    else:
        assumptions.append("The supplied allowed-domain list is proposed and must be reviewed before confirmation.")

    # The MVP never performs a real booking, payment, or personal-data disclosure.
    prohibited = {
        ActionType.BOOK, ActionType.PAY, ActionType.SHARE_PERSONAL_DATA
    } | _extra_prohibitions(task)

    return IntentContract(
        goal=task,
        constraints=ContractConstraints(
            max_total_price=price,
            max_distance_km=distance,
            refundable_required=refundable,
            allowed_domains=list(allowed_domains),
            prohibited_actions=prohibited,
        ),
        assumptions=assumptions,
        clarification_required=clarifications,
    )
