"""Routes for LinkedIn data import — connections, messages, applications, profile, ZIP upload, scraped data."""

import csv
import io
import json
import os
import tempfile
import zipfile
from datetime import datetime

from flask import Blueprint, request, jsonify
import db

bp = Blueprint("linkedin_import", __name__)

# ---------------------------------------------------------------------------
# Helpers for ZIP import
# ---------------------------------------------------------------------------

ORIGINALS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "Originals"))


def _extract_zip(zip_bytes: bytes, dest: str) -> str:
    """Extract ZIP bytes, handling double-zip if present."""
    os.makedirs(dest, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as z:
        inner_zips = [n for n in z.namelist() if n.endswith(".zip")]
        if inner_zips and not any(n.endswith(".csv") for n in z.namelist()):
            with z.open(inner_zips[0]) as inner_f:
                with zipfile.ZipFile(io.BytesIO(inner_f.read()), "r") as z2:
                    z2.extractall(dest)
        else:
            z.extractall(dest)
    return dest


def _find_csv(extract_dir: str, filename: str):
    """Find a CSV file in the extracted directory (case-insensitive)."""
    for root, _dirs, files in os.walk(extract_dir):
        for f in files:
            if f.lower() == filename.lower():
                return os.path.join(root, f)
    return None


def _read_linkedin_csv(filepath: str) -> list:
    """Read a LinkedIn CSV, skipping disclaimer rows before the real header."""
    with open(filepath, "r", encoding="utf-8-sig", errors="replace") as f:
        raw_lines = f.readlines()

    header_idx = 0
    for i, line in enumerate(raw_lines):
        stripped = line.strip()
        if not stripped:
            continue
        lower = stripped.lower().lstrip('"')
        if lower.startswith(("notes:", "when exporting", "when you")):
            continue
        if "," in stripped:
            tokens = [t.strip().strip('"') for t in stripped.split(",")]
            if len(tokens) >= 2 and all(len(t) < 60 for t in tokens):
                header_idx = i
                break

    csv_text = "".join(raw_lines[header_idx:])
    reader = csv.DictReader(io.StringIO(csv_text))
    rows = []
    for row in reader:
        if all(not v or (isinstance(v, str) and not v.strip()) for v in row.values()):
            continue
        clean = {}
        for k, v in row.items():
            clean[k] = " ".join(str(x) for x in v if x) if isinstance(v, list) else v
        rows.append(clean)
    return rows


def _parse_linkedin_date(date_str: str):
    """Parse LinkedIn date formats into ISO date string."""
    if not date_str or not date_str.strip():
        return None
    date_str = date_str.strip()
    for fmt in ["%d %b %Y", "%b %Y", "%Y-%m-%d", "%Y-%m", "%m/%d/%Y", "%m/%Y", "%Y"]:
        try:
            return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


@bp.route("/api/import/linkedin-connections", methods=["POST"])
def import_connections():
    """Import LinkedIn connections as contacts."""
    data = request.get_json(force=True)
    connections = data.get("connections", [])
    if not connections:
        return jsonify({"error": "connections array is required"}), 400

    imported = 0
    skipped = 0
    companies_linked = 0

    for conn in connections:
        name = conn.get("name", "").strip()
        company = conn.get("company", "").strip()
        title = conn.get("title", "").strip()
        connected_on = conn.get("connected_on")

        if not name:
            continue

        # Check for duplicate by name + company
        existing = db.query_one(
            "SELECT id FROM contacts WHERE name ILIKE %s AND company ILIKE %s",
            (name, company if company else ""),
        )
        if existing:
            skipped += 1
            continue

        # Try to link to existing company
        company_id = None
        if company:
            co = db.query_one(
                "SELECT id FROM companies WHERE name ILIKE %s", (company,)
            )
            if co:
                company_id = co["id"]
                companies_linked += 1

        db.execute_returning(
            """
            INSERT INTO contacts (name, company, company_id, title, source, last_contact)
            VALUES (%s, %s, %s, %s, 'linkedin', %s)
            RETURNING id
            """,
            (name, company, company_id, title, connected_on),
        )
        imported += 1

    return jsonify({
        "imported": imported,
        "skipped_duplicates": skipped,
        "companies_linked": companies_linked,
    }), 200


@bp.route("/api/import/linkedin-messages", methods=["POST"])
def import_messages():
    """Import LinkedIn messages as outreach records."""
    data = request.get_json(force=True)
    messages = data.get("messages", [])
    candidate_name = data.get("candidate_name", "Stephen Salaka")
    if not messages:
        return jsonify({"error": "messages array is required"}), 400

    imported = 0
    linked = 0

    for msg in messages:
        from_name = msg.get("from_name", "").strip()
        to_name = msg.get("to_name", "").strip()
        date_val = msg.get("date")
        content = msg.get("content", "")

        # Determine direction
        direction = "sent" if from_name.lower() == candidate_name.lower() else "received"

        # Try to link to a contact
        other_name = to_name if direction == "sent" else from_name
        contact = db.query_one(
            "SELECT id FROM contacts WHERE name ILIKE %s", (other_name,)
        ) if other_name else None

        contact_id = contact["id"] if contact else None
        if contact_id:
            linked += 1

        db.execute_returning(
            """
            INSERT INTO outreach_messages (contact_id, channel, direction, subject, body, status, created_at)
            VALUES (%s, 'linkedin', %s, %s, %s, 'delivered', COALESCE(%s::timestamp, NOW()))
            RETURNING id
            """,
            (contact_id, direction, f"LinkedIn message with {other_name}", content, date_val),
        )
        imported += 1

    return jsonify({
        "imported": imported,
        "linked_to_contacts": linked,
    }), 200


@bp.route("/api/import/linkedin-applications", methods=["POST"])
def import_applications():
    """Import LinkedIn Easy Apply history."""
    data = request.get_json(force=True)
    applications = data.get("applications", [])
    if not applications:
        return jsonify({"error": "applications array is required"}), 400

    imported = 0
    skipped = 0

    for app in applications:
        company = app.get("company", "").strip()
        role = app.get("role", "").strip()
        date_applied = app.get("date_applied")
        status = app.get("status", "applied")

        if not company or not role:
            continue

        # Deduplicate by company + role
        existing = db.query_one(
            "SELECT id FROM applications WHERE company_name ILIKE %s AND role ILIKE %s",
            (company, role),
        )
        if existing:
            skipped += 1
            continue

        db.execute_returning(
            """
            INSERT INTO applications (company_name, role, source, status, date_applied)
            VALUES (%s, %s, 'linkedin', %s, %s)
            RETURNING id
            """,
            (company, role, status, date_applied),
        )
        imported += 1

    return jsonify({
        "imported": imported,
        "skipped_duplicates": skipped,
    }), 200


@bp.route("/api/import/linkedin-profile", methods=["POST"])
def import_profile():
    """Extract career history and skills from LinkedIn profile data."""
    data = request.get_json(force=True)
    positions = data.get("positions", [])
    skills_list = data.get("skills", [])

    positions_added = 0
    bullets_extracted = 0
    skills_added = 0

    # Import positions
    for pos in positions:
        title = pos.get("title", "").strip()
        company = pos.get("company", "").strip()
        start_date = pos.get("start_date")
        end_date = pos.get("end_date")
        # Normalize partial dates: "2010-01" -> "2010-01-01"
        if start_date and len(start_date) == 7:
            start_date = start_date + "-01"
        if end_date and len(end_date) == 7:
            end_date = end_date + "-01"
        description = pos.get("description", "")

        if not title or not company:
            continue

        # Check for existing career_history entry
        existing = db.query_one(
            "SELECT id FROM career_history WHERE employer ILIKE %s AND title ILIKE %s",
            (company, title),
        )
        if existing:
            continue

        ch = db.execute_returning(
            """
            INSERT INTO career_history (employer, title, start_date, end_date)
            VALUES (%s, %s, %s, %s)
            RETURNING id
            """,
            (company, title, start_date, end_date),
        )
        positions_added += 1

        # Extract bullets from description
        if description and ch:
            lines = [
                line.strip().lstrip("-").lstrip("*").lstrip("•").strip()
                for line in description.split("\n")
                if line.strip() and len(line.strip()) > 10
            ]
            for line in lines:
                db.execute_returning(
                    """
                    INSERT INTO bullets (career_history_id, text, type)
                    VALUES (%s, %s, 'achievement')
                    RETURNING id
                    """,
                    (ch["id"], line),
                )
                bullets_extracted += 1

    # Import skills
    for skill_name in skills_list:
        skill_name = skill_name.strip()
        if not skill_name:
            continue
        existing = db.query_one(
            "SELECT id FROM skills WHERE name ILIKE %s", (skill_name,)
        )
        if existing:
            continue
        db.execute_returning(
            """
            INSERT INTO skills (name, category, proficiency)
            VALUES (%s, 'linkedin_import', 'intermediate')
            RETURNING id
            """,
            (skill_name,),
        )
        skills_added += 1

    return jsonify({
        "positions_added": positions_added,
        "bullets_extracted": bullets_extracted,
        "skills_added": skills_added,
    }), 200


# ---------------------------------------------------------------------------
# POST /api/import/linkedin-zip — Upload & import a LinkedIn data export ZIP
# ---------------------------------------------------------------------------

@bp.route("/api/import/linkedin-zip", methods=["POST"])
def import_linkedin_zip():
    """Accept a LinkedIn data export ZIP, extract, and import all data."""
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded. Use multipart form with 'file' field."}), 400

    f = request.files["file"]
    fname = f.filename or "linkedin_export.zip"
    if not fname.lower().endswith(".zip"):
        return jsonify({"error": "File must be a .zip file."}), 400

    zip_bytes = f.read()

    # Save the original ZIP to Originals/
    os.makedirs(ORIGINALS_DIR, exist_ok=True)
    save_path = os.path.join(ORIGINALS_DIR, "linkedin_export.zip")
    with open(save_path, "wb") as out:
        out.write(zip_bytes)

    # Extract to a temp directory
    extract_dir = os.path.join(ORIGINALS_DIR, "linkedin_export")
    try:
        _extract_zip(zip_bytes, extract_dir)
    except Exception as e:
        return jsonify({"error": f"Failed to extract ZIP: {str(e)}"}), 400

    summary = {
        "zip_saved": save_path,
        "connections": {"imported": 0, "skipped": 0, "companies_linked": 0},
        "profile": {"positions_added": 0, "bullets_extracted": 0, "skills_added": 0},
        "messages": {"imported": 0, "linked_to_contacts": 0},
        "applications": {"imported": 0, "skipped": 0},
    }

    # --- Connections ---
    csv_path = _find_csv(extract_dir, "Connections.csv")
    if csv_path:
        rows = _read_linkedin_csv(csv_path)
        connections = []
        for row in rows:
            first = row.get("First Name", "").strip()
            last = row.get("Last Name", "").strip()
            name = f"{first} {last}".strip()
            if not name:
                continue
            connections.append({
                "name": name,
                "company": row.get("Company", "").strip(),
                "title": row.get("Position", "").strip(),
                "connected_on": _parse_linkedin_date(row.get("Connected On", "")),
            })
        # Import via the existing logic inline
        for conn in connections:
            name = conn["name"]
            company = conn.get("company", "")
            title = conn.get("title", "")
            connected_on = conn.get("connected_on")
            existing = db.query_one(
                "SELECT id FROM contacts WHERE name ILIKE %s AND company ILIKE %s",
                (name, company if company else ""),
            )
            if existing:
                summary["connections"]["skipped"] += 1
                continue
            company_id = None
            if company:
                co = db.query_one("SELECT id FROM companies WHERE name ILIKE %s", (company,))
                if co:
                    company_id = co["id"]
                    summary["connections"]["companies_linked"] += 1
            db.execute_returning(
                """INSERT INTO contacts (name, company, company_id, title, source, last_contact)
                   VALUES (%s, %s, %s, %s, 'linkedin', %s) RETURNING id""",
                (name, company, company_id, title, connected_on),
            )
            summary["connections"]["imported"] += 1

    # --- Profile (Positions + Skills) ---
    positions_path = _find_csv(extract_dir, "Positions.csv")
    if positions_path:
        rows = _read_linkedin_csv(positions_path)
        for row in rows:
            title = row.get("Title", "").strip()
            company = row.get("Company Name", "").strip()
            description = row.get("Description", "").strip()
            start_date = _parse_linkedin_date(row.get("Started On", ""))
            end_date = _parse_linkedin_date(row.get("Finished On", ""))
            if start_date and len(start_date) == 7:
                start_date += "-01"
            if end_date and len(end_date) == 7:
                end_date += "-01"
            if not title or not company:
                continue
            existing = db.query_one(
                "SELECT id FROM career_history WHERE employer ILIKE %s AND title ILIKE %s",
                (company, title),
            )
            if existing:
                continue
            ch = db.execute_returning(
                """INSERT INTO career_history (employer, title, start_date, end_date)
                   VALUES (%s, %s, %s, %s) RETURNING id""",
                (company, title, start_date, end_date),
            )
            summary["profile"]["positions_added"] += 1
            if description and ch:
                lines = [
                    line.strip().lstrip("-").lstrip("*").lstrip("\u2022").strip()
                    for line in description.split("\n")
                    if line.strip() and len(line.strip()) > 10
                ]
                for line in lines:
                    db.execute_returning(
                        """INSERT INTO bullets (career_history_id, text, type)
                           VALUES (%s, %s, 'achievement') RETURNING id""",
                        (ch["id"], line),
                    )
                    summary["profile"]["bullets_extracted"] += 1

    skills_path = _find_csv(extract_dir, "Skills.csv")
    if skills_path:
        rows = _read_linkedin_csv(skills_path)
        for row in rows:
            skill_name = row.get("Name", "").strip()
            if not skill_name:
                continue
            existing = db.query_one("SELECT id FROM skills WHERE name ILIKE %s", (skill_name,))
            if existing:
                continue
            db.execute_returning(
                """INSERT INTO skills (name, category, proficiency)
                   VALUES (%s, 'linkedin_import', 'intermediate') RETURNING id""",
                (skill_name,),
            )
            summary["profile"]["skills_added"] += 1

    # --- Messages ---
    msg_path = _find_csv(extract_dir, "messages.csv")
    if msg_path:
        rows = _read_linkedin_csv(msg_path)
        candidate_name = "Stephen Salaka"
        for row in rows:
            content = row.get("CONTENT", "").strip()
            from_name = row.get("FROM", "").strip()
            to_name = row.get("TO", "").strip()
            date_val = row.get("DATE", "").strip() or None
            if row.get("IS MESSAGE DRAFT", "").strip().lower() == "yes":
                continue
            if not content and not from_name:
                continue
            direction = "sent" if from_name.lower() == candidate_name.lower() else "received"
            other_name = to_name if direction == "sent" else from_name
            contact = db.query_one(
                "SELECT id FROM contacts WHERE name ILIKE %s", (other_name,)
            ) if other_name else None
            contact_id = contact["id"] if contact else None
            if contact_id:
                summary["messages"]["linked_to_contacts"] += 1
            db.execute_returning(
                """INSERT INTO outreach_messages (contact_id, channel, direction, subject, body, status, created_at)
                   VALUES (%s, 'linkedin', %s, %s, %s, 'delivered', COALESCE(%s::timestamp, NOW()))
                   RETURNING id""",
                (contact_id, direction, f"LinkedIn message with {other_name}", content, date_val),
            )
            summary["messages"]["imported"] += 1

    # --- Applications ---
    apps_path = _find_csv(extract_dir, "Saved Jobs.csv")
    if apps_path:
        rows = _read_linkedin_csv(apps_path)
        for row in rows:
            company = row.get("Company", row.get("Company Name", "")).strip()
            role = row.get("Title", row.get("Job Title", "")).strip()
            date_applied = _parse_linkedin_date(row.get("Saved At", row.get("Create Date", "")))
            if not company or not role:
                continue
            existing = db.query_one(
                "SELECT id FROM applications WHERE company_name ILIKE %s AND role ILIKE %s",
                (company, role),
            )
            if existing:
                summary["applications"]["skipped"] += 1
                continue
            db.execute_returning(
                """INSERT INTO applications (company_name, role, source, status, date_applied)
                   VALUES (%s, %s, 'linkedin', 'saved', %s) RETURNING id""",
                (company, role, date_applied),
            )
            summary["applications"]["imported"] += 1

    return jsonify(summary), 200


# ---------------------------------------------------------------------------
# POST /api/import/linkedin-scraped — Import scraped JSONL data
# ---------------------------------------------------------------------------

LINKEDIN_SCRAPE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "Originals", "LinkedIn"))


@bp.route("/api/import/linkedin-scraped", methods=["POST"])
def import_linkedin_scraped():
    """Import scraped LinkedIn posts and comments from JSONL files in Originals/LinkedIn/."""
    summary = {
        "posts": {"found": False, "total_lines": 0, "imported": 0, "updated": 0},
        "comments": {"found": False, "total_lines": 0, "imported": 0, "updated": 0},
        "bridged_to_hub": 0,
    }

    # --- Posts ---
    posts_path = os.path.join(LINKEDIN_SCRAPE_DIR, "posts.jsonl")
    if os.path.exists(posts_path):
        summary["posts"]["found"] = True
        with open(posts_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                summary["posts"]["total_lines"] += 1
                try:
                    post = json.loads(line)
                except json.JSONDecodeError:
                    continue

                urn = post.get("urn", "")
                text = post.get("text", "")
                post_type = post.get("post_type", "text")
                likes = post.get("likes", 0) or 0
                comments_count = post.get("comments", 0) or 0
                reposts = post.get("reposts", 0) or 0
                media_files = json.dumps(post.get("media_files", []))
                url = post.get("url", "")
                original_author = post.get("original_author", "")
                posted_at = post.get("posted_at")

                if urn:
                    existing = db.query_one(
                        "SELECT id FROM linkedin_scraped_posts WHERE urn = %s", (urn,)
                    )
                else:
                    existing = None

                if existing:
                    db.execute(
                        """UPDATE linkedin_scraped_posts
                           SET text=%s, post_type=%s, likes=%s, comments=%s, reposts=%s,
                               media_files=%s, url=%s, original_author=%s, posted_at=%s
                           WHERE id=%s""",
                        (text, post_type, likes, comments_count, reposts,
                         media_files, url, original_author, posted_at, existing["id"]),
                    )
                    summary["posts"]["updated"] += 1
                else:
                    db.execute_returning(
                        """INSERT INTO linkedin_scraped_posts
                           (urn, text, post_type, likes, comments, reposts, media_files, url, original_author, posted_at)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                           RETURNING id""",
                        (urn, text, post_type, likes, comments_count, reposts,
                         media_files, url, original_author, posted_at),
                    )
                    summary["posts"]["imported"] += 1

                    # Bridge to linkedin_posts for Hub visibility
                    hook = (text[:200] + "...") if len(text) > 200 else text
                    db.execute_returning(
                        """INSERT INTO linkedin_posts (hook_text, body, status, post_type, created_at)
                           VALUES (%s, %s, 'published', %s, COALESCE(%s::timestamptz, NOW()))
                           RETURNING id""",
                        (hook, text, post_type, posted_at),
                    )
                    summary["bridged_to_hub"] += 1

    # --- Comments ---
    comments_path = os.path.join(LINKEDIN_SCRAPE_DIR, "comments.jsonl")
    if os.path.exists(comments_path):
        summary["comments"]["found"] = True
        with open(comments_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                summary["comments"]["total_lines"] += 1
                try:
                    comment = json.loads(line)
                except json.JSONDecodeError:
                    continue

                urn = comment.get("urn", "")
                original_author = comment.get("original_author", "")
                original_snippet = comment.get("original_snippet", "")
                original_post_url = comment.get("original_post_url", "")
                comment_text = comment.get("comment_text", "")
                comment_url = comment.get("comment_url", "")
                commented_at = comment.get("commented_at")

                if urn:
                    existing = db.query_one(
                        "SELECT id FROM linkedin_scraped_comments WHERE urn = %s", (urn,)
                    )
                else:
                    existing = None

                if existing:
                    db.execute(
                        """UPDATE linkedin_scraped_comments
                           SET original_author=%s, original_snippet=%s, original_post_url=%s,
                               comment_text=%s, comment_url=%s, commented_at=%s
                           WHERE id=%s""",
                        (original_author, original_snippet, original_post_url,
                         comment_text, comment_url, commented_at, existing["id"]),
                    )
                    summary["comments"]["updated"] += 1
                else:
                    db.execute_returning(
                        """INSERT INTO linkedin_scraped_comments
                           (urn, original_author, original_snippet, original_post_url,
                            comment_text, comment_url, commented_at)
                           VALUES (%s, %s, %s, %s, %s, %s, %s)
                           RETURNING id""",
                        (urn, original_author, original_snippet, original_post_url,
                         comment_text, comment_url, commented_at),
                    )
                    summary["comments"]["imported"] += 1

    return jsonify(summary), 200


# ---------------------------------------------------------------------------
# GET /api/import/linkedin-scraped/status — Check what scraper data is available
# ---------------------------------------------------------------------------

@bp.route("/api/import/linkedin-scraped/status", methods=["GET"])
def linkedin_scraped_status():
    """Check what scraped data files are available and their line counts."""
    status = {
        "posts": {"exists": False, "lines": 0},
        "comments": {"exists": False, "lines": 0},
        "messages": {"exists": False, "conversations": 0},
    }

    posts_path = os.path.join(LINKEDIN_SCRAPE_DIR, "posts.jsonl")
    if os.path.exists(posts_path):
        status["posts"]["exists"] = True
        with open(posts_path, "r", encoding="utf-8") as f:
            status["posts"]["lines"] = sum(1 for line in f if line.strip())

    comments_path = os.path.join(LINKEDIN_SCRAPE_DIR, "comments.jsonl")
    if os.path.exists(comments_path):
        status["comments"]["exists"] = True
        with open(comments_path, "r", encoding="utf-8") as f:
            status["comments"]["lines"] = sum(1 for line in f if line.strip())

    messages_dir = os.path.join(LINKEDIN_SCRAPE_DIR, "messages")
    if os.path.exists(messages_dir):
        jsonl_files = [f for f in os.listdir(messages_dir) if f.endswith(".jsonl")]
        if jsonl_files:
            status["messages"]["exists"] = True
            status["messages"]["conversations"] = len(jsonl_files)

    return jsonify(status), 200
