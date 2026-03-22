"""Routes for network path finding — warm intros, company maps, connection rankings."""

from flask import Blueprint, request, jsonify
import db

bp = Blueprint("path_finding", __name__)


@bp.route("/api/network/find-paths", methods=["POST"])
def find_paths():
    """Find warm intro paths to a target company."""
    data = request.get_json(force=True)
    company_name = data.get("company_name")
    company_id = data.get("company_id")

    if not company_name and not company_id:
        return jsonify({"error": "company_name or company_id is required"}), 400

    # Resolve company info
    if company_id:
        company = db.query_one(
            "SELECT id, name, sector FROM companies WHERE id = %s", (company_id,)
        )
        if not company:
            return jsonify({"error": f"Company ID {company_id} not found"}), 404
        company_name = company["name"]
        sector = company.get("sector")
    else:
        company = db.query_one(
            "SELECT id, name, sector FROM companies WHERE name ILIKE %s",
            (f"%{company_name}%",),
        )
        sector = company.get("sector") if company else None

    # Direct contacts at that company
    direct = db.query(
        """
        SELECT id, name, company, title, relationship, relationship_strength,
               email, last_contact
        FROM contacts
        WHERE company ILIKE %s
        ORDER BY CASE relationship_strength
            WHEN 'strong' THEN 1 WHEN 'warm' THEN 2 WHEN 'cold' THEN 3 ELSE 4
        END, last_contact DESC NULLS LAST
        """,
        (f"%{company_name}%",),
    )

    # Same-sector contacts (if sector known)
    same_sector = []
    if sector:
        same_sector = db.query(
            """
            SELECT c.id, c.name, c.company, c.title, c.relationship,
                   c.relationship_strength, c.email, c.last_contact,
                   co.name AS their_company, co.sector
            FROM contacts c
            LEFT JOIN companies co ON c.company_id = co.id
            WHERE co.sector = %s
              AND c.company NOT ILIKE %s
            ORDER BY CASE c.relationship_strength
                WHEN 'strong' THEN 1 WHEN 'warm' THEN 2 WHEN 'cold' THEN 3 ELSE 4
            END, c.last_contact DESC NULLS LAST
            LIMIT 20
            """,
            (sector, f"%{company_name}%"),
        )

    # Warm path score: direct strong=3, direct warm=2, direct cold=1, sector contacts=0.5
    score = 0
    for c in direct:
        s = c.get("relationship_strength", "")
        score += 3 if s == "strong" else 2 if s == "warm" else 1
    for c in same_sector:
        s = c.get("relationship_strength", "")
        score += 1.5 if s == "strong" else 1 if s == "warm" else 0.5

    return jsonify({
        "company": company_name,
        "sector": sector,
        "direct": direct,
        "same_sector": same_sector,
        "warm_path_score": score,
    }), 200


@bp.route("/api/network/company-map/<company_name>", methods=["GET"])
def company_map(company_name):
    """List all contacts at a company with relationship details."""
    contacts = db.query(
        """
        SELECT name, title, relationship, relationship_strength,
               email, last_contact
        FROM contacts
        WHERE company ILIKE %s
        ORDER BY CASE relationship_strength
            WHEN 'strong' THEN 1 WHEN 'warm' THEN 2 WHEN 'cold' THEN 3 ELSE 4
        END, name
        """,
        (f"%{company_name}%",),
    )
    return jsonify({"company": company_name, "contacts": contacts}), 200


@bp.route("/api/network/warm-companies", methods=["GET"])
def warm_companies():
    """Companies ranked by connection strength."""
    rows = db.query(
        """
        SELECT company,
               COUNT(*) AS contact_count,
               ROUND(AVG(CASE relationship_strength
                   WHEN 'strong' THEN 3 WHEN 'warm' THEN 2 WHEN 'cold' THEN 1 ELSE 0
               END), 2) AS avg_strength,
               (SELECT name FROM contacts c2
                WHERE c2.company = contacts.company
                ORDER BY CASE c2.relationship_strength
                    WHEN 'strong' THEN 1 WHEN 'warm' THEN 2 WHEN 'cold' THEN 3 ELSE 4
                END LIMIT 1) AS strongest_contact
        FROM contacts
        WHERE company IS NOT NULL AND company != ''
        GROUP BY company
        ORDER BY avg_strength DESC, contact_count DESC
        """
    )
    return jsonify({"companies": rows}), 200
