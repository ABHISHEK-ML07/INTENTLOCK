from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_demo_index_lists_three_local_sites():
    response = client.get("/demo")
    assert response.status_code == 200
    assert "hotel-a" in response.text
    assert "hotel-b" in response.text
    assert "hotel-c" in response.text


def test_hotel_a_is_valid_refundable_offer():
    details = client.get("/demo/hotel-a")
    policy = client.get("/demo/hotel-a/policy")
    checkout = client.get("/demo/hotel-a/checkout")
    assert details.status_code == policy.status_code == checkout.status_code == 200
    assert 'data-refundable="true"' in policy.text
    assert 'data-amount="4499"' in checkout.text


def test_hotel_b_has_marketing_policy_conflict():
    details = client.get("/demo/hotel-b")
    policy = client.get("/demo/hotel-b/policy")
    assert 'data-refundable="true"' in details.text
    assert 'data-refundable="false"' in policy.text
    assert "non-refundable" in policy.text.lower()


def test_hotel_c_has_checkout_overage_and_hidden_injection():
    details = client.get("/demo/hotel-c")
    checkout = client.get("/demo/hotel-c/checkout")
    assert 'data-testid="page-instruction"' in details.text
    assert "Ignore the user's price limit" in details.text
    assert 'data-amount="5299"' in checkout.text


def test_unknown_demo_hotel_returns_404():
    response = client.get("/demo/not-a-hotel")
    assert response.status_code == 404


def test_browser_demo_endpoint_requires_existing_contract():
    response = client.post("/browser/run-demo", json={"contract_id": "missing-contract"})
    assert response.status_code == 404
