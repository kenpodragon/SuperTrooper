"""BLS JOLTS data fetcher.

Calls the Bureau of Labor Statistics public API v2 to fetch JOLTS
(Job Openings and Labor Turnover Survey) data and ingests it into
the market_signals table.

Public API (no key): 25 requests/day limit.
"""

import json
import logging
import urllib.request
import urllib.error
from datetime import datetime

import db

logger = logging.getLogger(__name__)

BLS_API_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"

# JOLTS series IDs and their human-readable names + sentiment direction
JOLTS_SERIES = {
    "JTS000000000000000JOR": {
        "name": "Job Openings Rate",
        "direction": "positive",  # rising = positive for job seekers
    },
    "JTS000000000000000HIR": {
        "name": "Hires Rate",
        "direction": "positive",
    },
    "JTS000000000000000TSR": {
        "name": "Total Separations Rate",
        "direction": "negative",
    },
    "JTS000000000000000QUR": {
        "name": "Quits Rate",
        "direction": "positive",  # rising quits = workers confident
    },
    "JTS000000000000000LDR": {
        "name": "Layoffs/Discharges Rate",
        "direction": "negative",  # rising layoffs = bad for seekers
    },
}

MONTH_NAMES = {
    "M01": "Jan", "M02": "Feb", "M03": "Mar", "M04": "Apr",
    "M05": "May", "M06": "Jun", "M07": "Jul", "M08": "Aug",
    "M09": "Sep", "M10": "Oct", "M11": "Nov", "M12": "Dec",
}


def _period_to_date(year: str, period: str) -> datetime:
    """Convert BLS year + period (e.g. '2025', 'M06') to a datetime."""
    month = int(period.replace("M", ""))
    return datetime(int(year), month, 1)


def _compute_severity(series_id: str, current_value: float, previous_value: float | None) -> str:
    """Compute severity based on trend direction and series sentiment."""
    if previous_value is None:
        return "neutral"

    direction = JOLTS_SERIES[series_id]["direction"]
    change = current_value - previous_value

    if abs(change) < 0.1:
        return "neutral"

    if direction == "positive":
        return "positive" if change > 0 else "negative"
    else:
        # For negative-direction series (layoffs, separations),
        # a rise is bad, a drop is good
        return "negative" if change > 0 else "positive"


def _build_trend_body(name: str, current_value: float, previous_value: float | None) -> str:
    """Build a descriptive body string with trend context."""
    if previous_value is None:
        return f"{name} stands at {current_value}%."

    change = current_value - previous_value
    direction = "up" if change > 0 else "down"
    return (
        f"{name} is {direction} {abs(change):.1f} percentage points "
        f"from previous period ({previous_value}% to {current_value}%)."
    )


def _signal_exists(source: str, captured_at: datetime, title: str) -> bool:
    """Check if a signal with the same source, captured_at, and title already exists."""
    row = db.query_one(
        """
        SELECT id FROM market_signals
        WHERE source = %s AND captured_at = %s AND title = %s
        """,
        (source, captured_at, title),
    )
    return row is not None


def fetch_jolts(start_year: int | None = None, end_year: int | None = None) -> dict:
    """Fetch JOLTS data from BLS API and ingest into market_signals.

    Args:
        start_year: First year to fetch (default: current year - 1).
        end_year: Last year to fetch (default: current year).

    Returns:
        Dict with 'inserted' count and 'skipped' count.
    """
    now = datetime.now()
    if start_year is None:
        start_year = now.year - 1
    if end_year is None:
        end_year = now.year

    series_ids = list(JOLTS_SERIES.keys())

    payload = {
        "seriesid": series_ids,
        "startyear": str(start_year),
        "endyear": str(end_year),
    }

    logger.info("Fetching JOLTS data from BLS: years %s-%s", start_year, end_year)

    try:
        req = urllib.request.Request(
            BLS_API_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:
        logger.error("BLS API request failed: %s", exc)
        return {"inserted": 0, "skipped": 0, "error": str(exc)}

    result = json.loads(raw)

    if result.get("status") != "REQUEST_SUCCEEDED":
        error_msg = "; ".join(result.get("message", ["Unknown error"]))
        logger.error("BLS API error: %s", error_msg)
        return {"inserted": 0, "skipped": 0, "error": error_msg}

    inserted = 0
    skipped = 0

    for series in result.get("Results", {}).get("series", []):
        series_id = series.get("seriesID", "")
        if series_id not in JOLTS_SERIES:
            continue

        meta = JOLTS_SERIES[series_id]
        data_points = series.get("data", [])

        # Sort by year+period ascending so we can compute trends
        data_points.sort(key=lambda d: (d["year"], d["period"]))

        previous_value = None

        for dp in data_points:
            year = dp["year"]
            period = dp["period"]

            # Skip annual averages
            if period == "M13":
                continue

            try:
                value = float(dp["value"])
            except (ValueError, KeyError):
                continue

            captured_at = _period_to_date(year, period)
            month_name = MONTH_NAMES.get(period, period)
            title = f"JOLTS {meta['name']}: {value}% ({month_name} {year})"

            # Deduplication check
            if _signal_exists("bls_jolts", captured_at, title):
                skipped += 1
                previous_value = value
                continue

            severity = _compute_severity(series_id, value, previous_value)
            body = _build_trend_body(meta["name"], value, previous_value)

            data_json = json.dumps({
                "series_id": series_id,
                "series_name": meta["name"],
                "year": year,
                "period": period,
                "value": value,
                "previous_value": previous_value,
                "footnotes": dp.get("footnotes", []),
            })

            db.execute_returning(
                """
                INSERT INTO market_signals
                    (source, signal_type, title, body, data_json, region, industry,
                     severity, source_url, captured_at)
                VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    "bls_jolts",
                    "labor_market",
                    title,
                    body,
                    data_json,
                    "United States",
                    "All Industries",
                    severity,
                    "https://www.bls.gov/jlt/",
                    captured_at,
                ),
            )
            inserted += 1
            previous_value = value

    logger.info("JOLTS fetch complete: %d inserted, %d skipped", inserted, skipped)
    return {"inserted": inserted, "skipped": skipped}
