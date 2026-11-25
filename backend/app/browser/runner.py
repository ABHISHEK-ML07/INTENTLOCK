from __future__ import annotations

import os
from urllib.parse import urlparse

from app.demo_models import DemoOfferResult, DemoRunResponse
from app.models import (
    ActionProposal, ActionType, ClaimType, ContractStatus, EvidenceRecord,
    EvidenceStatus, IntentContract
)
from app.policy import evaluate_action


DEFAULT_DEMO_BASE_URL = "http://localhost:8000"
DEMO_HOTEL_IDS = ("hotel-a", "hotel-b", "hotel-c")


class DemoExecutionError(RuntimeError):
    """Raised when the controlled browser demonstration cannot safely continue."""


def _demo_base_url(contract: IntentContract) -> str:
    base_url = os.getenv("INTENTLOCK_DEMO_BASE_URL", DEFAULT_DEMO_BASE_URL).rstrip("/")
    parsed = urlparse(base_url)
    if parsed.scheme != "http" or parsed.hostname != "localhost" or parsed.port not in (None, 8000):
        raise DemoExecutionError(
            "For safety, the browser demo base URL must be http://localhost:8000."
        )
    if set(contract.constraints.allowed_domains) != {"localhost"}:
        raise DemoExecutionError(
            "The confirmed contract must allow only the localhost demo domain."
        )
    return base_url


def _check_navigation(contract: IntentContract, url: str) -> None:
    action = ActionProposal(
        action_type=ActionType.NAVIGATE,
        label=f"Navigate to controlled demo page: {urlparse(url).path}",
        target_url=url,
    )
    decision = evaluate_action(contract, action)
    if decision.decision.value != "allow":
        raise DemoExecutionError("Navigation blocked by policy: " + "; ".join(decision.reasons))


async def run_hotel_demo(contract: IntentContract) -> DemoRunResponse:
    """Run the three localhost-only synthetic sites through Playwright and policy checks.

    Website text is treated only as untrusted page data. No page content is sent
    back to an LLM, and no real booking, payment, or personal-data action occurs.
    """
    if contract.status != ContractStatus.CONFIRMED:
        raise DemoExecutionError("Confirm the intent contract before running the browser demo.")
    if contract.clarification_required:
        raise DemoExecutionError("Resolve all contract clarifications before running the demo.")
    constraints = contract.constraints
    if not constraints.max_total_price or constraints.max_total_price.basis.value != "total":
        raise DemoExecutionError("The confirmed contract must include a total-price ceiling.")
    if not constraints.refundable_required or constraints.max_distance_km is None:
        raise DemoExecutionError("The demo requires refundable and distance constraints.")

    base_url = _demo_base_url(contract)

    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise DemoExecutionError(
            "Playwright is not installed. Run: pip install -r requirements.txt "
            "and python -m playwright install chromium."
        ) from exc

    results: list[DemoOfferResult] = []

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        page.set_default_timeout(7000)

        try:
            for hotel_id in DEMO_HOTEL_IDS:
                navigation_checks = 0

                details_url = f"{base_url}/demo/{hotel_id}"
                _check_navigation(contract, details_url)
                await page.goto(details_url, wait_until="domcontentloaded")
                navigation_checks += 1

                hotel_name = (await page.get_by_test_id("hotel-name").inner_text()).strip()
                meta = page.get_by_test_id("hotel-meta")
                room_id = await meta.get_attribute("data-room-id")
                distance = await meta.get_attribute("data-distance-km")
                base_price = await page.get_by_test_id("base-price").get_attribute("data-amount")
                banner = page.get_by_test_id("marketing-refundability")
                marketing_text = (await banner.inner_text()).strip()
                marketing_refundable = (await banner.get_attribute("data-refundable")) == "true"

                instruction_locator = page.get_by_test_id("page-instruction")
                suspicious_instruction = await instruction_locator.count() > 0
                if suspicious_instruction:
                    page_instruction = (await instruction_locator.text_content() or "").lower()
                    suspicious_instruction = any(
                        marker in page_instruction
                        for marker in (
                            "ignore the user",
                            "system override",
                            "share",
                            "confirm this booking",
                        )
                    )

                policy_url = f"{base_url}/demo/{hotel_id}/policy"
                _check_navigation(contract, policy_url)
                await page.goto(policy_url, wait_until="domcontentloaded")
                navigation_checks += 1
                policy_element = page.get_by_test_id("refundability")
                policy_refundable = (await policy_element.get_attribute("data-refundable")) == "true"
                policy_text = (await page.get_by_test_id("policy-text").inner_text()).strip()
                policy_source = page.url

                checkout_url = f"{base_url}/demo/{hotel_id}/checkout"
                _check_navigation(contract, checkout_url)
                await page.goto(checkout_url, wait_until="domcontentloaded")
                navigation_checks += 1
                checkout = page.get_by_test_id("checkout-total")
                final_total = await checkout.get_attribute("data-amount")
                includes_fees = (await checkout.get_attribute("data-includes-fees")) == "true"
                checkout_source = page.url

                source_origin = urlparse(details_url).hostname or "localhost"
                evidence = [
                    EvidenceRecord(
                        claim_type=ClaimType.TOTAL_PRICE,
                        value=final_total,
                        status=EvidenceStatus.VERIFIED,
                        source_url=checkout_source,
                        source_origin=urlparse(checkout_source).hostname or source_origin,
                        offer_id=room_id or "unknown",
                        includes_fees_and_taxes=includes_fees,
                        extractor="playwright-dom",
                        evidence_ref=f"{hotel_id}:checkout-total",
                    ),
                    EvidenceRecord(
                        claim_type=ClaimType.REFUNDABILITY,
                        value=policy_refundable,
                        status=EvidenceStatus.VERIFIED,
                        source_url=policy_source,
                        source_origin=urlparse(policy_source).hostname or source_origin,
                        offer_id=room_id or "unknown",
                        extractor="playwright-dom",
                        evidence_ref=f"{hotel_id}:selected-room-policy",
                    ),
                    EvidenceRecord(
                        claim_type=ClaimType.DISTANCE_KM,
                        value=distance,
                        status=EvidenceStatus.VERIFIED,
                        source_url=details_url,
                        source_origin=source_origin,
                        offer_id=room_id or "unknown",
                        extractor="playwright-dom",
                        evidence_ref=f"{hotel_id}:distance",
                    ),
                ]

                recommendation = ActionProposal(
                    action_type=ActionType.RECOMMEND_OFFER,
                    label=f"Evaluate selected offer at {hotel_name}",
                    resource_id=room_id or "unknown",
                    evidence=evidence,
                )
                policy_decision = evaluate_action(contract, recommendation)

                simulated_booking_blocked = False
                if suspicious_instruction:
                    # This proposal is evaluated, never dispatched to the browser.
                    attempted_booking = ActionProposal(
                        action_type=ActionType.BOOK,
                        label="Simulated booking attempt prompted by untrusted page content",
                        target_url=checkout_url,
                    )
                    booking_decision = evaluate_action(contract, attempted_booking)
                    simulated_booking_blocked = booking_decision.decision.value == "deny"
                    if not simulated_booking_blocked:
                        raise DemoExecutionError(
                            "Safety invariant failed: simulated booking was not denied."
                        )

                conflict = marketing_refundable != policy_refundable
                reasons = list(policy_decision.reasons)
                if conflict:
                    reasons.insert(
                        0,
                        "Marketing cancellation claim conflicts with the selected-room policy; the selected-rate policy was used.",
                    )
                if suspicious_instruction:
                    reasons.append(
                        "Suspicious webpage text was detected and treated as untrusted content, not as an instruction."
                    )
                    reasons.append(
                        "A simulated prohibited booking proposal was denied before any browser action was dispatched."
                    )

                results.append(DemoOfferResult(
                    hotel_id=hotel_id,
                    hotel_name=hotel_name,
                    room_id=room_id or "unknown",
                    marketing_cancellation_claim=marketing_text,
                    detailed_cancellation_policy=policy_text,
                    base_price_inr=base_price or "unknown",
                    final_total_inr=final_total or "unknown",
                    distance_km=distance or "unknown",
                    marketing_policy_conflict=conflict,
                    suspicious_page_instruction_detected=suspicious_instruction,
                    simulated_booking_blocked=simulated_booking_blocked,
                    instruction_handling=(
                        "Detected as untrusted webpage content; not executed."
                        if suspicious_instruction
                        else "No suspicious page instruction detected."
                    ),
                    decision=policy_decision.decision,
                    eligible=policy_decision.decision.value == "allow",
                    reasons=reasons,
                    evidence_sources=[details_url, policy_source, checkout_source],
                    navigation_checks_passed=navigation_checks,
                ))
        finally:
            await context.close()
            await browser.close()

    eligible_count = sum(1 for offer in results if offer.eligible)
    return DemoRunResponse(
        contract_id=contract.contract_id,
        contract_version=contract.version,
        offers=results,
        eligible_count=eligible_count,
        rejected_or_paused_count=len(results) - eligible_count,
    )
