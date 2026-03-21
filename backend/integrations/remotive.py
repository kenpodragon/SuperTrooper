"""Remotive API integration — no auth required."""

import requests
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db

REMOTIVE_URL = "https://remotive.com/api/remote-jobs"


def fetch_remotive_jobs(search: str = None, category: str = None, limit: int = 20) -> list:
    """Fetch jobs from Remotive API and return normalized list."""
    params = {"limit": limit}
    if search:
        params["search"] = search
    if category:
        params["category"] = category

    try:
        resp = requests.get(REMOTIVE_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        jobs = data.get("jobs", [])
    except Exception as e:
        return [{"error": str(e), "source": "remotive"}]

    results = []
    for j in jobs:
        salary = j.get("salary", "") or ""
        results.append({
            "title": j.get("title", ""),
            "company": j.get("company_name", ""),
            "location": j.get("candidate_required_location", "Remote"),
            "url": j.get("url", ""),
            "source": "remotive",
            "salary_range": salary,
            "description": j.get("description", "")[:2000],
            "raw_data": j,
        })
    return results


def sync_remotive_to_inbox(search: str = None, category: str = None, limit: int = 20) -> dict:
    """Fetch from Remotive and insert new jobs into fresh_jobs, skipping duplicates."""
    jobs = fetch_remotive_jobs(search=search, category=category, limit=limit)

    added = 0
    duplicates = 0
    errors = 0

    for j in jobs:
        if "error" in j:
            errors += 1
            continue
        if not j.get("url"):
            errors += 1
            continue
        try:
            existing = db.query_one("SELECT id FROM fresh_jobs WHERE url = %s", (j["url"],))
            if existing:
                duplicates += 1
                continue
            db.query(
                """INSERT INTO fresh_jobs (url, title, company, location, source, salary_range, description, raw_data)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    j["url"], j["title"], j["company"], j["location"],
                    j["source"], j["salary_range"], j["description"],
                    str(j["raw_data"]),
                ),
            )
            added += 1
        except Exception as e:
            errors += 1

    return {"source": "remotive", "added": added, "duplicates": duplicates, "errors": errors}
