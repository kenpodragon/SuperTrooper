"""Test summary_variants headline CRUD."""
import requests

BASE_URL = "http://localhost:8055"


def test_create_summary_variant_with_headline():
    """POST /api/summary-variants accepts headline field."""
    resp = requests.post(f"{BASE_URL}/api/summary-variants", json={
        "role_type": "test_headline_role",
        "text": "Test summary text",
        "headline": "Test Headline | AI Architect"
    })
    assert resp.status_code in (200, 201)
    data = resp.json()
    assert data["headline"] == "Test Headline | AI Architect"
    # Cleanup
    requests.delete(f"{BASE_URL}/api/summary-variants/{data['id']}")


def test_update_summary_variant_headline():
    """PATCH /api/summary-variants/<id> updates headline."""
    # Create
    resp = requests.post(f"{BASE_URL}/api/summary-variants", json={
        "role_type": "test_headline_update",
        "text": "Summary text",
        "headline": "Original Headline"
    })
    assert resp.status_code in (200, 201)
    sv_id = resp.json()["id"]
    # Update
    resp = requests.patch(f"{BASE_URL}/api/summary-variants/{sv_id}", json={
        "headline": "Updated Headline | Engineering Leader"
    })
    assert resp.status_code == 200
    assert resp.json()["headline"] == "Updated Headline | Engineering Leader"
    # Cleanup
    requests.delete(f"{BASE_URL}/api/summary-variants/{sv_id}")


def test_list_summary_variants_includes_headline():
    """GET /api/summary-variants returns headline field."""
    resp = requests.get(f"{BASE_URL}/api/summary-variants")
    assert resp.status_code == 200
    data = resp.json()
    variants = data.get("summary_variants", data) if isinstance(data, dict) else data
    # headline key should exist on each variant (may be null)
    for v in variants:
        assert "headline" in v
