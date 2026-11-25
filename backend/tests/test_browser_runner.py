from decimal import Decimal

import pytest

from app.browser.runner import DemoExecutionError, _demo_base_url, run_hotel_demo
from app.compiler import compile_contract
from app.models import ContractStatus


def confirmed_demo_contract(domains=("localhost",)):
    proposed = compile_contract(
        "Find a refundable hotel within 5 km for under ₹5,000 total. Do not book or pay.",
        domains,
    )
    assert not proposed.clarification_required
    return proposed.model_copy(update={
        "status": ContractStatus.CONFIRMED,
        "confirmed_at": "2026-11-25T00:00:00Z",
        "confirmed_by": "test-user",
        "contract_hash": "test-hash",
    })


def test_browser_demo_requires_localhost_allowlisted():
    contract = confirmed_demo_contract()
    assert _demo_base_url(contract) == "http://localhost:8000"


def test_browser_demo_rejects_contract_without_localhost_allowlist():
    contract = confirmed_demo_contract(("example.com",))
    with pytest.raises(DemoExecutionError, match="localhost"):
        _demo_base_url(contract)


def test_browser_demo_rejects_unconfirmed_contract():
    proposed = compile_contract(
        "Find a refundable hotel within 5 km for under ₹5,000 total.",
        ["localhost"],
    )
    with pytest.raises(DemoExecutionError, match="Confirm"):
        import asyncio
        asyncio.run(run_hotel_demo(proposed))


def test_browser_demo_rejects_non_local_override(monkeypatch):
    contract = confirmed_demo_contract()
    monkeypatch.setenv("INTENTLOCK_DEMO_BASE_URL", "https://example.com")
    with pytest.raises(DemoExecutionError, match="localhost"):
        _demo_base_url(contract)
