import requests

BASE = "http://localhost:8055"

def test_recipes_list():
    r = requests.get(f"{BASE}/api/resume/recipes")
    assert r.status_code == 200

def test_bullets_list():
    r = requests.get(f"{BASE}/api/bullets")
    assert r.status_code == 200

def test_career_history():
    r = requests.get(f"{BASE}/api/career-history")
    assert r.status_code == 200

def test_skills_list():
    r = requests.get(f"{BASE}/api/skills")
    assert r.status_code == 200
