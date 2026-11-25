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


def test_playwright_runs_three_local_scenarios_end_to_end(tmp_path, monkeypatch):
    """Launch the local API and exercise all three synthetic pages with Chromium."""
    import os
    import subprocess
    import sys
    import time
    from pathlib import Path

    import httpx

    backend_dir = Path(__file__).resolve().parents[1]
    db_path = tmp_path / "intentlock-e2e.sqlite3"
    env = os.environ.copy()
    env["INTENTLOCK_DB_PATH"] = str(db_path)
    env["PYTHONPATH"] = str(backend_dir)

    process = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn", "app.main:app",
            "--host", "0.0.0.0", "--port", "8000",
        ],
        cwd=str(backend_dir),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        ready = False
        for _ in range(80):
            if process.poll() is not None:
                raise RuntimeError("Uvicorn exited before the test server became ready.")
            try:
                response = httpx.get("http://127.0.0.1:8000/health", timeout=0.5)
                if response.status_code == 200:
                    ready = True
                    break
            except httpx.HTTPError:
                time.sleep(0.25)
        assert ready, "Local INTENTLOCK API did not start within 20 seconds."

        task = (
            "Find a refundable hotel within 5 km for under ₹5,000 total. "
            "Do not book or pay."
        )
        proposed_response = httpx.post(
            "http://127.0.0.1:8000/contracts/propose",
            json={"task": task, "allowed_domains": ["localhost"]},
            timeout=5,
        )
        assert proposed_response.status_code == 201, proposed_response.text
        contract_id = proposed_response.json()["contract_id"]

        confirm_response = httpx.post(
            f"http://127.0.0.1:8000/contracts/{contract_id}/confirm",
            json={"confirmed_by": "playwright-e2e-test"},
            timeout=5,
        )
        assert confirm_response.status_code == 200, confirm_response.text

        demo_response = httpx.post(
            "http://127.0.0.1:8000/browser/run-demo",
            json={"contract_id": contract_id},
            timeout=60,
        )
        assert demo_response.status_code == 200, demo_response.text
        report = demo_response.json()
        by_hotel = {offer["hotel_id"]: offer for offer in report["offers"]}

        assert report["eligible_count"] == 1
        assert by_hotel["hotel-a"]["decision"] == "allow"
        assert by_hotel["hotel-b"]["decision"] == "deny"
        assert by_hotel["hotel-b"]["marketing_policy_conflict"] is True
        assert by_hotel["hotel-c"]["decision"] == "deny"
        assert by_hotel["hotel-c"]["final_total_inr"] == "5299"
        assert by_hotel["hotel-c"]["suspicious_page_instruction_detected"] is True
        assert by_hotel["hotel-c"]["simulated_booking_blocked"] is True
        assert all(offer["navigation_checks_passed"] == 3 for offer in report["offers"])
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
