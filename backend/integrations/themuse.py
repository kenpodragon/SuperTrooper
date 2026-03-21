"""The Muse API integration — no auth required."""

import requests
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db

MUSE_URL = "https://www.themuse.com/api/public/jobs"


def fetch_muse_jobs(category: str = None, level: str = None, location: str = None, page: int = 0) -> list:
    """Fetch jobs from The Muse API and return normalized list."""
    params = {"page": page, "descending": "true"}
    if category:
        params["category"] = category
    if level:
        params["level"] = level
    if location:
        params["location"] = location

    try:
        resp = requests.get(MUSE_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        jobs = data.get("results", [])
    except Exception as e:
        return [{"error": str(e), "source": "themuse"}]

    results = []
    for j in jobs:
        company = j.get("company", {}).get("name", "") if isinstance(j.get("company"), dict) else ""
        locations = j.get("locations", [])
        loc_str = ", ".join(l.get("name", "") for l in locations) if locations else "Remote"
        levels = j.get("levels", [])
        level_str = ", ".join(lv.get("name", "") for lv in levels) if levels else ""
        results.append({
            "title": j.get("name", ""),
            "company": company,
            "location": loc_str,
            "url": j.get("refs", {}).get("landing_page", ""),
            "source": "themuse",
            "salary_range": "",
            "description": j.get("contents", "")[:2000],
            "raw_data": j,
        })
    return results


def sync_muse_to_inbox(category: str = None, level: str = None, location: str = None, page: int = 0) -> dict:
    """Fetch from The Muse and insert new jobs into fresh_jobs, skipping duplicates."""
    jobs = fetch_muse_jobs(category=category, level=level, location=location, page=page)

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

    return {"source": "themuse", "added": added, "duplicates": duplicates, "errors": errors}
