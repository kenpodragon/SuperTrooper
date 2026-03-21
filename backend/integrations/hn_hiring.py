"""Hacker News Who's Hiring integration via Algolia API."""

import re
import requests
import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db

ALGOLIA_URL = "https://hn.algolia.com/api/v1/search_by_date"

URL_RE = re.compile(r'https?://[^\s|<>"]+')
REMOTE_RE = re.compile(r'\bremote\b', re.IGNORECASE)


def _parse_comment(comment_text: str, object_id: str) -> dict:
    """Extract job info from a HN comment using simple regex."""
    text = comment_text or ""
    # Strip HTML tags
    text_clean = re.sub(r'<[^>]+>', ' ', text)
    lines = [l.strip() for l in text_clean.splitlines() if l.strip()]

    title = lines[0][:200] if lines else "Software Engineer"
    company = lines[1][:100] if len(lines) > 1 else "Unknown"

    urls = URL_RE.findall(text_clean)
    url = urls[0] if urls else f"https://news.ycombinator.com/item?id={object_id}"

    is_remote = bool(REMOTE_RE.search(text_clean))
    location = "Remote" if is_remote else "See posting"

    return {
        "title": title,
        "company": company,
        "location": location,
        "url": url,
        "source": "hn_hiring",
        "salary_range": "",
        "description": text_clean[:2000],
        "raw_data": {"object_id": object_id, "snippet": text_clean[:500]},
    }


def fetch_hn_jobs(months_back: int = 1) -> list:
    """Fetch HN Who's Hiring comments and parse into job listings."""
    cutoff = datetime.utcnow() - timedelta(days=30 * months_back)
    cutoff_ts = int(cutoff.timestamp())

    # Find the thread
    try:
        thread_resp = requests.get(
            ALGOLIA_URL,
            params={
                "query": "Ask HN: Who is hiring",
                "tags": "ask_hn",
                "numericFilters": f"created_at_i>{cutoff_ts}",
                "hitsPerPage": 3,
            },
            timeout=15,
        )
        thread_resp.raise_for_status()
        threads = thread_resp.json().get("hits", [])
    except Exception as e:
        return [{"error": str(e), "source": "hn_hiring"}]

    if not threads:
        return []

    thread_id = threads[0].get("objectID", "")
    if not thread_id:
        return []

    # Fetch top-level comments on that thread
    try:
        comments_resp = requests.get(
            ALGOLIA_URL,
            params={
                "tags": f"comment,story_{thread_id}",
                "hitsPerPage": 50,
            },
            timeout=15,
        )
        comments_resp.raise_for_status()
        hits = comments_resp.json().get("hits", [])
    except Exception as e:
        return [{"error": str(e), "source": "hn_hiring"}]

    results = []
    for hit in hits:
        text = hit.get("comment_text", "")
        if not text or len(text) < 30:
            continue
        parsed = _parse_comment(text, hit.get("objectID", ""))
        results.append(parsed)

    return results


def sync_hn_to_inbox(months_back: int = 1) -> dict:
    """Fetch HN jobs and insert new ones into fresh_jobs."""
    jobs = fetch_hn_jobs(months_back=months_back)

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

    return {"source": "hn_hiring", "added": added, "duplicates": duplicates, "errors": errors}
