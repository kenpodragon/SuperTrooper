"""Routes for contacts / network."""

from flask import Blueprint, request, jsonify
import db

bp = Blueprint("contacts", __name__)


@bp.route("/api/contacts", methods=["GET"])
def list_contacts():
    """List/filter/search contacts."""
    company = request.args.get("company")
    relationship = request.args.get("relationship")
    strength = request.args.get("strength")
    q = request.args.get("q")
    limit = int(request.args.get("limit", 50))
    offset = int(request.args.get("offset", 0))

    clauses, params = [], []
    if company:
        clauses.append("company ILIKE %s")
        params.append(f"%{company}%")
    if relationship:
        clauses.append("relationship = %s")
        params.append(relationship)
    if strength:
        clauses.append("relationship_strength = %s")
        params.append(strength)
    if q:
        clauses.append("(name ILIKE %s OR title ILIKE %s)")
        params.extend([f"%{q}%", f"%{q}%"])

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = db.query(
        f"""
        SELECT id, name, company, title, relationship, email, phone,
               linkedin_url, relationship_strength, last_contact, source,
               notes, created_at, updated_at
        FROM contacts
        {where}
        ORDER BY last_contact DESC NULLS LAST, name
        LIMIT %s OFFSET %s
        """,
        params + [limit, offset],
    )
    return jsonify(rows), 200


@bp.route("/api/contacts", methods=["POST"])
def create_contact():
    """Add a new contact."""
    data = request.get_json(force=True)
    if not data.get("name"):
        return jsonify({"error": "name is required"}), 400

    row = db.execute_returning(
        """
        INSERT INTO contacts (name, company, title, relationship, email, phone,
            linkedin_url, relationship_strength, last_contact, source, notes)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        RETURNING *
        """,
        (
            data["name"], data.get("company"), data.get("title"),
            data.get("relationship"), data.get("email"), data.get("phone"),
            data.get("linkedin_url"), data.get("relationship_strength"),
            data.get("last_contact"), data.get("source", "manual"),
            data.get("notes"),
        ),
    )
    return jsonify(row), 201


@bp.route("/api/contacts/<int:contact_id>", methods=["PATCH"])
def update_contact(contact_id):
    """Update contact fields."""
    data = request.get_json(force=True)
    allowed = [
        "name", "company", "title", "relationship", "email", "phone",
        "linkedin_url", "relationship_strength", "last_contact", "source", "notes",
    ]
    sets, params = [], []
    for key in allowed:
        if key in data:
            sets.append(f"{key} = %s")
            params.append(data[key])
    if not sets:
        return jsonify({"error": "No valid fields to update"}), 400

    params.append(contact_id)
    row = db.execute_returning(
        f"UPDATE contacts SET {', '.join(sets)} WHERE id = %s RETURNING *",
        params,
    )
    if not row:
        return jsonify({"error": "Not found"}), 404
    return jsonify(row), 200
