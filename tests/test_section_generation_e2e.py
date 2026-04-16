"""End-to-end test: section-based recipe -> .docx generation."""
import requests
import pytest

BASE_URL = "http://localhost:8055"


def test_generate_resume_from_recipe():
    """Generate a resume from an existing recipe — should not 500."""
    resp = requests.get(f"{BASE_URL}/api/resume/recipes")
    assert resp.status_code == 200
    recipes = resp.json()
    if isinstance(recipes, dict):
        recipes = recipes.get("recipes", [])
    if not recipes:
        pytest.skip("No recipes in DB")

    recipe_id = recipes[0]["id"]
    resp = requests.post(f"{BASE_URL}/api/resume/recipes/{recipe_id}/generate")
    # Accept 200 (success with file) or other non-500
    assert resp.status_code != 500, f"Server error: {resp.text}"


def test_is_section_recipe_detection():
    """is_section_recipe correctly detects format."""
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "utils"))
    from generate_resume import is_section_recipe

    v1 = {"CERT_1": {"table": "certifications", "id": 1}, "JOB_1_BULLET_1": {"table": "bullets", "id": 2}}
    assert is_section_recipe(v1) is False

    section = {"HEADER": {"table": "resume_header", "id": 1}, "CERTIFICATIONS": {"table": "certifications", "ids": [1, 2]}}
    assert is_section_recipe(section) is True
