"""Routes for network path finding — warm intros, company maps, connection rankings, path strength."""

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


@bp.route("/api/paths/to-company/<company>", methods=["GET"])
def paths_to_company(company):
    """Find all paths to a target company.

    Returns:
    - Direct contacts currently at the company
    - Contacts who previously worked there (via notes/enrichment)
    - 2nd-degree connections (contacts connected to people at company)
    - Alumni connections (same school/background)
    """
    # Direct contacts at company
    direct = db.query(
        """
        SELECT id, name, company, title, relationship, relationship_strength,
               email, linkedin_url, last_contact, relationship_stage, health_score
        FROM contacts
        WHERE company ILIKE %s AND merged_into_id IS NULL
        ORDER BY CASE relationship_strength
            WHEN 'strong' THEN 1 WHEN 'warm' THEN 2 WHEN 'cold' THEN 3 ELSE 4
        END, last_contact DESC NULLS LAST
        """,
        (f"%{company}%",),
    )

    # Contacts who mention the company in notes (previously worked there)
    previous = db.query(
        """
        SELECT id, name, company, title, relationship, relationship_strength,
               email, linkedin_url, last_contact, notes
        FROM contacts
        WHERE company NOT ILIKE %s
          AND notes ILIKE %s
          AND merged_into_id IS NULL
        ORDER BY CASE relationship_strength
            WHEN 'strong' THEN 1 WHEN 'warm' THEN 2 WHEN 'cold' THEN 3 ELSE 4
        END
        LIMIT 20
        """,
        (f"%{company}%", f"%{company}%"),
    )

    # 2nd degree: contacts at companies that have referrals/outreach with target company
    second_degree = db.query(
        """
        SELECT DISTINCT c.id, c.name, c.company, c.title, c.relationship_strength,
               c.email, c.linkedin_url
        FROM contacts c
        JOIN referrals r ON r.contact_id = c.id
        JOIN applications a ON a.id = r.application_id
        WHERE a.company_name ILIKE %s
          AND c.company NOT ILIKE %s
          AND c.merged_into_id IS NULL
        LIMIT 20
        """,
        (f"%{company}%", f"%{company}%"),
    )

    # Alumni: same source='linkedin' contacts at target (already covered by direct)
    # Score the overall path strength
    score = 0.0
    for c in direct:
        s = c.get("relationship_strength", "")
        score += 3.0 if s == "strong" else 2.0 if s == "warm" else 1.0
    for c in previous:
        s = c.get("relationship_strength", "")
        score += 2.0 if s == "strong" else 1.0 if s == "warm" else 0.5
    for c in second_degree:
        score += 1.0

    return jsonify({
        "company": company,
        "direct_contacts": direct,
        "previous_employees": previous,
        "second_degree": second_degree,
        "path_score": score,
        "summary": {
            "direct": len(direct),
            "previous": len(previous),
            "second_degree": len(second_degree),
        },
    }), 200


@bp.route("/api/paths/strength", methods=["GET"])
def path_strength():
    """Score path strength for all companies with contacts.

    Based on recency, relationship stage, touchpoint frequency.
    """
    rows = db.query(
        """
        SELECT
            c.company,
            COUNT(DISTINCT c.id) AS contact_count,
            ROUND(AVG(CASE c.relationship_strength
                WHEN 'strong' THEN 3 WHEN 'warm' THEN 2 WHEN 'cold' THEN 1 ELSE 0
            END)::NUMERIC, 2) AS avg_strength,
            ROUND(AVG(c.health_score)::NUMERIC, 1) AS avg_health,
            MAX(c.last_contact) AS most_recent_contact,
            COUNT(t.id) FILTER (WHERE t.logged_at >= NOW() - INTERVAL '90 days') AS touchpoints_90d,
            ROUND(
                (AVG(CASE c.relationship_strength
                    WHEN 'strong' THEN 3 WHEN 'warm' THEN 2 WHEN 'cold' THEN 1 ELSE 0
                END) * 20
                + COALESCE(AVG(c.health_score), 0) * 0.5
                + LEAST(COUNT(t.id) FILTER (WHERE t.logged_at >= NOW() - INTERVAL '90 days'), 10) * 3
                )::NUMERIC, 1
            ) AS path_score
        FROM contacts c
        LEFT JOIN touchpoints t ON t.contact_id = c.id
        WHERE c.company IS NOT NULL AND c.company != ''
          AND c.merged_into_id IS NULL
        GROUP BY c.company
        ORDER BY path_score DESC NULLS LAST
        """
    )
    return jsonify({"companies": rows}), 200
