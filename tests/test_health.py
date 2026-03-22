import requests

BASE = "http://localhost:8055"

def test_api_health():
    r = requests.get(f"{BASE}/api/health")
    assert r.status_code == 200

def test_applications_endpoint():
    r = requests.get(f"{BASE}/api/applications")
    assert r.status_code == 200

def test_notifications_endpoint():
    r = requests.get(f"{BASE}/api/notifications")
    assert r.status_code == 200

def test_fresh_jobs_endpoint():
    r = requests.get(f"{BASE}/api/fresh-jobs")
    assert r.status_code == 200

def test_contacts_endpoint():
    r = requests.get(f"{BASE}/api/contacts")
    assert r.status_code == 200

def test_saved_jobs_endpoint():
    r = requests.get(f"{BASE}/api/saved-jobs")
    assert r.status_code == 200
