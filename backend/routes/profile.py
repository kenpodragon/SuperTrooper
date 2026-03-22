"""Routes for candidate profile (stored in settings.preferences JSONB)."""

import json
from flask import Blueprint, request, jsonify
import db

bp = Blueprint("profile", __name__)

PROFILE_FIELDS = {
    "candidate_name",
    "candidate_email",
    "candidate_phone",
    "candidate_location",
    "target_roles",
    "avoid_roles",
    "target_locations",
    "work_mode",
    "desired_salary_min",
    "desired_salary_max",
    "industry_preferences",
    "industry_avoids",
    "years_experience",
    "visa_status",
    "credentials",
    "linkedin_url",
    "github_url",
    "portfolio_url",
    "bio",
    "job_search_status",
}


def _get_preferences():
    """Read settings.preferences JSONB, return as dict."""
    row = db.query_one("SELECT preferences FROM settings WHERE id = 1")
    prefs = (row.get("preferences") or {}) if row else {}
    if isinstance(prefs, str):
        try:
            prefs = json.loads(prefs)
        except (json.JSONDecodeError, TypeError):
            prefs = {}
    return prefs


def _get_profile(prefs):
    """Extract profile fields from preferences dict."""
    profile = {}
    for field in PROFILE_FIELDS:
        profile[field] = prefs.get(field)
    return profile


@bp.route("/api/profile", methods=["GET"])
def get_profile():
    """Return the candidate profile from settings.preferences."""
    prefs = _get_preferences()
    return jsonify(_get_profile(prefs)), 200


@bp.route("/api/profile", methods=["PUT"])
def update_profile():
    """Merge submitted profile fields into settings.preferences JSONB."""
    data = request.get_json(force=True)
    if not data:
        return jsonify({"error": "No data provided"}), 400

    # Only accept known profile fields
    updates = {k: v for k, v in data.items() if k in PROFILE_FIELDS}
    if not updates:
        return jsonify({"error": "No valid profile fields provided"}), 400

    # Read current preferences
    prefs = _get_preferences()

    # Merge profile fields into preferences
    prefs.update(updates)

    db.execute(
        "UPDATE settings SET preferences = %s::jsonb, updated_at = NOW() WHERE id = 1",
        (json.dumps(prefs),),
    )

    return jsonify({
        "profile": _get_profile(prefs),
        "updated_fields": list(updates.keys()),
    }), 200


@bp.route("/api/profile/from-kb", methods=["GET"])
def profile_from_kb():
    """Build a best-guess profile from knowledge base data.

    Queries career_history, skills, and settings to auto-populate profile fields.
    """
    result = {}

    # --- Pull existing preferences as baseline ---
    prefs = _get_preferences()
    for field in ("candidate_name", "candidate_email", "candidate_phone",
                  "candidate_location", "linkedin_url", "github_url",
                  "portfolio_url", "bio", "job_search_status"):
        val = prefs.get(field)
        if val:
            result[field] = val

    # --- Career history: derive target roles + location ---
    try:
        rows = db.query(
            "SELECT title, location, employer, start_date, end_date, is_current "
            "FROM career_history ORDER BY start_date DESC NULLS LAST LIMIT 20"
        )
    except Exception:
        rows = []

    if rows:
        # Unique recent titles as target roles
        titles = []
        seen = set()
        for r in rows:
            t = (r.get("title") or "").strip()
            if t and t.lower() not in seen:
                seen.add(t.lower())
                titles.append(t)
        if titles:
            result["target_roles"] = titles[:10]

        # Location from most recent / current role
        for r in rows:
            loc = (r.get("location") or "").strip()
            if loc:
                result["candidate_location"] = loc
                break

        # Build target_locations from unique career locations
        loc_names = []
        loc_seen = set()
        for r in rows:
            loc = (r.get("location") or "").strip()
            if loc and loc.lower() not in loc_seen:
                loc_seen.add(loc.lower())
                loc_names.append({
                    "name": loc,
                    "work_mode": "Hybrid",
                    "range_miles": 50,
                })
        if loc_names:
            result["target_locations"] = loc_names[:5]

    # --- Skills: derive industry preferences ---
    try:
        skill_rows = db.query(
            "SELECT DISTINCT category FROM skills WHERE category IS NOT NULL LIMIT 20"
        )
    except Exception:
        skill_rows = []

    if skill_rows:
        categories = [r["category"] for r in skill_rows if r.get("category")]
        if categories:
            result["industry_preferences"] = categories

    # --- Salary from existing prefs ---
    for field in ("desired_salary_min", "desired_salary_max"):
        val = prefs.get(field)
        if val is not None:
            result[field] = val

    # --- Years of experience from career history span ---
    if rows:
        try:
            earliest = db.query_one(
                "SELECT MIN(start_date) AS earliest FROM career_history WHERE start_date IS NOT NULL"
            )
            if earliest and earliest.get("earliest"):
                from datetime import date
                start = earliest["earliest"]
                if isinstance(start, str):
                    start = date.fromisoformat(start[:10])
                years = (date.today() - start).days // 365
                result["years_experience"] = years
        except Exception:
            pass

    # --- Credentials ---
    if prefs.get("credentials"):
        result["credentials"] = prefs["credentials"]

    # --- Visa status ---
    if prefs.get("visa_status"):
        result["visa_status"] = prefs["visa_status"]

    return jsonify(result), 200
