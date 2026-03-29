import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import pytest

BASE_URL = "http://localhost:8055"

@pytest.fixture
def api():
    import requests  # guard: only imported when fixture is used
    session = requests.Session()
    session.base_url = BASE_URL
    return session

@pytest.fixture
def base_url():
    return BASE_URL
