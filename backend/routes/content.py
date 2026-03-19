"""Routes for emails, documents, resume_versions."""

from flask import Blueprint, request, jsonify
import db

bp = Blueprint("content", __name__)


# ---------------------------------------------------------------------------
# Emails
# ---------------------------------------------------------------------------

@bp.route("/api/emails", methods=["GET"])
def list_emails():
    """Search/filter emails."""
    q = request.args.get("q")
    category = request.args.get("category")
    from_addr = request.args.get("from")
    after = request.args.get("after")
    before = request.args.get("before")
    application_id = request.args.get("application_id")
    limit = int(request.args.get("limit", 50))
    offset = int(request.args.get("offset", 0))

    clauses, params = [], []
    if q:
        clauses.append("(subject ILIKE %s OR snippet ILIKE %s OR body ILIKE %s)")
        params.extend([f"%{q}%", f"%{q}%", f"%{q}%"])
    if category:
        clauses.append("category = %s")
        params.append(category)
    if from_addr:
        clauses.append("(from_address ILIKE %s OR from_name ILIKE %s)")
        params.extend([f"%{from_addr}%", f"%{from_addr}%"])
    if after:
        clauses.append("date >= %s")
        params.append(after)
    if before:
        clauses.append("date <= %s")
        params.append(before)
    if application_id:
        clauses.append("application_id = %s")
        params.append(int(application_id))

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = db.query(
        f"""
        SELECT id, gmail_id, thread_id, date, from_address, from_name,
               to_address, subject, snippet, category, application_id,
               labels, created_at
        FROM emails
        {where}
        ORDER BY date DESC NULLS LAST
        LIMIT %s OFFSET %s
        """,
        params + [limit, offset],
    )
    return jsonify(rows), 200


@bp.route("/api/emails/<int:email_id>", methods=["GET"])
def get_email(email_id):
    """Single email with full body."""
    row = db.query_one("SELECT * FROM emails WHERE id = %s", (email_id,))
    if not row:
        return jsonify({"error": "Not found"}), 404
    return jsonify(row), 200


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------

@bp.route("/api/documents", methods=["GET"])
def list_documents():
    """List/filter documents by type."""
    doc_type = request.args.get("type")
    variant = request.args.get("variant")
    limit = int(request.args.get("limit", 50))
    offset = int(request.args.get("offset", 0))

    clauses, params = [], []
    if doc_type:
        clauses.append("type = %s")
        params.append(doc_type)
    if variant:
        clauses.append("variant = %s")
        params.append(variant)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = db.query(
        f"""
        SELECT id, path, filename, type, content_hash, version, variant,
               extracted_date, metadata_json, created_at
        FROM documents
        {where}
        ORDER BY created_at DESC
        LIMIT %s OFFSET %s
        """,
        params + [limit, offset],
    )
    return jsonify(rows), 200


@bp.route("/api/documents/<int:doc_id>", methods=["GET"])
def get_document(doc_id):
    """Single document with content."""
    row = db.query_one("SELECT * FROM documents WHERE id = %s", (doc_id,))
    if not row:
        return jsonify({"error": "Not found"}), 404
    return jsonify(row), 200


# ---------------------------------------------------------------------------
# Resume Versions
# ---------------------------------------------------------------------------

@bp.route("/api/resume-versions", methods=["GET"])
def list_resume_versions():
    """List all resume versions."""
    rows = db.query(
        """
        SELECT id, version, variant, docx_path, pdf_path, summary,
               target_role_type, document_id, is_current, created_at
        FROM resume_versions
        ORDER BY created_at DESC
        """
    )
    return jsonify(rows), 200
