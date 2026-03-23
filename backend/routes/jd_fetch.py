"""
jd_fetch.py — Fetch and parse job descriptions from URLs.
Uses requests + BeautifulSoup to extract text content from job posting pages.
"""

import re
import requests
from flask import Blueprint, request, jsonify
from bs4 import BeautifulSoup

bp = Blueprint("jd_fetch", __name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# Elements that typically contain the JD on common job boards
JD_SELECTORS = [
    # LinkedIn
    ".description__text",
    ".show-more-less-html__markup",
    # Indeed
    "#jobDescriptionText",
    ".jobsearch-jobDescriptionText",
    # Greenhouse
    "#content .content-intro",
    "#content",
    # Lever
    ".posting-page .content",
    ".section-wrapper",
    # Workday
    '[data-automation-id="jobPostingDescription"]',
    # Generic patterns
    '[class*="job-description"]',
    '[class*="jobDescription"]',
    '[class*="job_description"]',
    '[id*="job-description"]',
    '[id*="jobDescription"]',
    "article",
    '[role="main"]',
    "main",
]


def extract_jd_text(html: str) -> str:
    """Extract job description text from HTML, trying board-specific selectors first."""
    soup = BeautifulSoup(html, "html.parser")

    # Remove script, style, nav, header, footer
    for tag in soup.find_all(["script", "style", "nav", "header", "footer", "noscript"]):
        tag.decompose()

    # Try each selector
    for selector in JD_SELECTORS:
        el = soup.select_one(selector)
        if el:
            text = el.get_text(separator="\n", strip=True)
            # Only use if it has meaningful content (at least 100 chars)
            if len(text) >= 100:
                return clean_text(text)

    # Fallback: get body text
    body = soup.find("body")
    if body:
        text = body.get_text(separator="\n", strip=True)
        return clean_text(text)

    return clean_text(soup.get_text(separator="\n", strip=True))


def clean_text(text: str) -> str:
    """Clean extracted text: collapse whitespace, remove empty lines."""
    lines = text.split("\n")
    cleaned = []
    for line in lines:
        line = line.strip()
        if line:
            cleaned.append(line)
    text = "\n".join(cleaned)
    # Collapse runs of 3+ newlines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


@bp.route("/api/jd/fetch-url", methods=["POST"])
def fetch_jd_from_url():
    """Fetch a job posting URL and extract the JD text."""
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()

    if not url:
        return jsonify({"error": "url is required"}), 400

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
        resp.raise_for_status()
    except requests.exceptions.Timeout:
        return jsonify({"error": "Request timed out. The site may be blocking automated requests."}), 504
    except requests.exceptions.HTTPError as e:
        return jsonify({"error": f"HTTP {e.response.status_code}: Could not fetch the page."}), 502
    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Failed to fetch URL: {str(e)[:200]}"}), 502

    text = extract_jd_text(resp.text)

    if len(text) < 50:
        return jsonify({
            "error": "Could not extract meaningful content. The page may require login or use JavaScript rendering.",
            "raw_length": len(resp.text),
            "extracted_length": len(text),
        }), 422

    return jsonify({
        "url": url,
        "text": text,
        "length": len(text),
    }), 200
