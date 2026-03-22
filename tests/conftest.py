import pytest
import requests

BASE_URL = "http://localhost:8055"

@pytest.fixture
def api():
    session = requests.Session()
    session.base_url = BASE_URL
    return session

@pytest.fixture
def base_url():
    return BASE_URL
