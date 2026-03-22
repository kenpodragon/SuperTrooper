import requests

BASE = "http://localhost:8055"

def test_applications_list():
    r = requests.get(f"{BASE}/api/applications")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, (list, dict))

def test_pipeline_summary():
    r = requests.get(f"{BASE}/api/reporting/pipeline")
    assert r.status_code == 200

def test_stale_applications():
    r = requests.get(f"{BASE}/api/aging/stale-applications")
    assert r.status_code == 200
