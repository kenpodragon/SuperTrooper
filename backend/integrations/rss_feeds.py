"""RSS/Atom feed poller using stdlib xml.etree.ElementTree only."""

import sys
import os
import xml.etree.ElementTree as ET
from urllib.request import urlopen, Request
from urllib.error import URLError

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db

FEEDS = [
    {"url": "https://weworkremotely.com/remote-jobs.rss", "source": "weworkremotely"},
    {"url": "https://www.workingnomads.com/jobs.rss", "source": "workingnomads"},
]

NS_ATOM = "{http://www.w3.org/2005/Atom}"


def _get_text(el, tag: str, ns: str = "") -> str:
    """Safely extract text from an XML element."""
    child = el.find(f"{ns}{tag}")
    return (child.text or "").strip() if child is not None else ""


def fetch_rss_jobs(feed_url: str, source: str) -> list:
    """Fetch and parse an RSS or Atom feed, return normalized job list."""
    try:
        req = Request(feed_url, headers={"User-Agent": "SuperTroopers/1.0"})
        with urlopen(req, timeout=15) as response:
            raw = response.read()
        root = ET.fromstring(raw)
    except Exception as e:
        return [{"error": str(e), "source": source}]

    results = []

    # RSS 2.0
    items = root.findall(".//item")
    for item in items:
        title = _get_text(item, "title")
        url = _get_text(item, "link")
        description = _get_text(item, "description")[:2000]
        company = _get_text(item, "author") or source
        results.append({
            "title": title,
            "company": company,
            "location": "Remote",
            "url": url,
            "source": source,
            "salary_range": "",
            "description": description,
            "raw_data": {"feed": feed_url, "title": title},
        })

    # Atom feeds
    if not items:
        entries = root.findall(f"{NS_ATOM}entry")
        for entry in entries:
            title = _get_text(entry, "title", NS_ATOM)
            link_el = entry.find(f"{NS_ATOM}link")
            url = link_el.get("href", "") if link_el is not None else ""
            description = _get_text(entry, "summary", NS_ATOM) or _get_text(entry, "content", NS_ATOM)
            company = _get_text(entry, "author", NS_ATOM) or source
            results.append({
                "title": title,
                "company": company,
                "location": "Remote",
                "url": url,
                "source": source,
                "salary_range": "",
                "description": description[:2000],
                "raw_data": {"feed": feed_url, "title": title},
            })

    return results


def _insert_jobs(jobs: list) -> dict:
    """Insert a list of normalized jobs into fresh_jobs, skip duplicates."""
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
        except Exception:
            errors += 1
    return {"added": added, "duplicates": duplicates, "errors": errors}


def sync_all_rss_feeds() -> dict:
    """Poll all configured RSS feeds and sync to fresh_jobs."""
    results = {}
    for feed in FEEDS:
        jobs = fetch_rss_jobs(feed["url"], feed["source"])
        stats = _insert_jobs(jobs)
        stats["source"] = feed["source"]
        results[feed["source"]] = stats
    return results
