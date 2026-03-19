"""Routes for content_sections, voice_rules, salary_benchmarks, cola_markets.

Supports both individual section queries AND full document reconstruction.
"""

from flask import Blueprint, request, jsonify
import db

bp = Blueprint("knowledge", __name__)


# ---------------------------------------------------------------------------
# Content Sections (Candidate Profile, Rejection Analysis, etc.)
# ---------------------------------------------------------------------------

@bp.route("/api/content/<document>", methods=["GET"])
def get_document(document):
    """Get a full document reconstructed from content_sections.

    Query params:
        section: filter by section name (ILIKE)
        subsection: filter by subsection name (ILIKE)
        format: 'sections' returns structured JSON, 'text' returns reconstructed markdown (default: sections)
    """
    section = request.args.get("section")
    subsection = request.args.get("subsection")
    fmt = request.args.get("format", "sections")

    clauses = ["source_document = %s"]
    params = [document]

    if section:
        clauses.append("section ILIKE %s")
        params.append(f"%{section}%")
    if subsection:
        clauses.append("subsection ILIKE %s")
        params.append(f"%{subsection}%")

    where = f"WHERE {' AND '.join(clauses)}"
    rows = db.query(
        f"""
        SELECT id, section, subsection, sort_order, content, content_format, tags, metadata
        FROM content_sections
        {where}
        ORDER BY sort_order
        """,
        params,
    )

    if not rows:
        return jsonify({"error": f"Document '{document}' not found or no matching sections"}), 404

    if fmt == "text":
        # Reconstruct as markdown
        parts = []
        for row in rows:
            if row["subsection"]:
                parts.append(f"### {row['subsection']}\n\n{row['content']}")
            else:
                parts.append(f"## {row['section']}\n\n{row['content']}")
        return jsonify({
            "document": document,
            "text": "\n\n---\n\n".join(parts),
            "section_count": len(rows),
        })

    return jsonify({
        "document": document,
        "sections": rows,
        "count": len(rows),
    })


@bp.route("/api/content", methods=["GET"])
def list_documents():
    """List all available documents and their section counts."""
    rows = db.query(
        """
        SELECT source_document, COUNT(*) as section_count,
               MIN(created_at) as created_at, MAX(updated_at) as updated_at
        FROM content_sections
        GROUP BY source_document
        ORDER BY source_document
        """
    )
    return jsonify({"documents": rows})


# ---------------------------------------------------------------------------
# Voice Rules
# ---------------------------------------------------------------------------

@bp.route("/api/voice-rules", methods=["GET"])
def get_voice_rules():
    """Get voice rules with optional filters.

    Query params:
        category: filter by category (banned_word, banned_construction, etc.)
        part: filter by part number (1-8)
        subcategory: filter by subcategory
        format: 'rules' returns structured JSON, 'text' returns reconstructed guide (default: rules)
    """
    category = request.args.get("category")
    part = request.args.get("part")
    subcategory = request.args.get("subcategory")
    fmt = request.args.get("format", "rules")

    clauses, params = [], []
    if category:
        clauses.append("category = %s")
        params.append(category)
    if part:
        clauses.append("part = %s")
        params.append(int(part))
    if subcategory:
        clauses.append("subcategory = %s")
        params.append(subcategory)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = db.query(
        f"""
        SELECT id, part, part_title, category, subcategory, rule_text,
               explanation, examples_bad, examples_good, sort_order
        FROM voice_rules
        {where}
        ORDER BY sort_order
        """,
        params,
    )

    if fmt == "text":
        # Reconstruct as readable guide
        parts = {}
        for row in rows:
            key = f"Part {row['part']}: {row['part_title']}"
            if key not in parts:
                parts[key] = []
            parts[key].append(row)

        text_parts = []
        for key, rules in parts.items():
            text_parts.append(f"## {key}\n")
            for r in rules:
                if r["category"] == "banned_word":
                    text_parts.append(f"- {r['rule_text']}")
                else:
                    text_parts.append(f"### {r['rule_text']}")
                    if r["explanation"]:
                        text_parts.append(r["explanation"])
                    if r["examples_bad"]:
                        text_parts.append(f"Bad: {'; '.join(r['examples_bad'])}")
                    if r["examples_good"]:
                        text_parts.append(f"Good: {'; '.join(r['examples_good'])}")
                text_parts.append("")

        return jsonify({
            "text": "\n".join(text_parts),
            "rule_count": len(rows),
        })

    return jsonify({
        "rules": rows,
        "count": len(rows),
    })


@bp.route("/api/voice-rules/check", methods=["POST"])
def check_text_against_rules():
    """Check a piece of text against banned words and constructions.

    Body: {"text": "the text to check"}
    Returns: list of violations found
    """
    data = request.get_json()
    if not data or "text" not in data:
        return jsonify({"error": "Provide 'text' in request body"}), 400

    text = data["text"].lower()
    violations = []

    # Check banned words
    banned_words = db.query(
        "SELECT rule_text, subcategory FROM voice_rules WHERE category = 'banned_word'"
    )
    for bw in banned_words:
        word = bw["rule_text"].lower()
        if word in text:
            violations.append({
                "type": "banned_word",
                "match": bw["rule_text"],
                "subcategory": bw["subcategory"],
            })

    # Check banned constructions
    banned_constructions = db.query(
        "SELECT rule_text, subcategory, explanation FROM voice_rules WHERE category = 'banned_construction'"
    )
    for bc in banned_constructions:
        pattern = bc["rule_text"].lower()
        if pattern in text:
            violations.append({
                "type": "banned_construction",
                "match": bc["rule_text"],
                "subcategory": bc["subcategory"],
                "explanation": bc["explanation"],
            })

    return jsonify({
        "text_length": len(data["text"]),
        "violations": violations,
        "violation_count": len(violations),
        "clean": len(violations) == 0,
    })


# ---------------------------------------------------------------------------
# Salary Benchmarks
# ---------------------------------------------------------------------------

@bp.route("/api/salary-benchmarks", methods=["GET"])
def get_salary_benchmarks():
    """Get salary benchmarks with optional filters.

    Query params:
        tier: filter by tier number (1-5)
        role: search by role title (ILIKE)
        format: 'rows' returns structured JSON, 'text' returns reconstructed doc (default: rows)
    """
    tier = request.args.get("tier")
    role = request.args.get("role")
    fmt = request.args.get("format", "rows")

    clauses, params = [], []
    if tier:
        clauses.append("tier = %s")
        params.append(int(tier))
    if role:
        clauses.append("role_title ILIKE %s")
        params.append(f"%{role}%")

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = db.query(
        f"""
        SELECT id, role_title, tier, tier_name, national_median_range,
               melbourne_range, remote_range, hcol_range, target_realistic
        FROM salary_benchmarks
        {where}
        ORDER BY sort_order
        """,
        params,
    )

    if fmt == "text":
        text_parts = ["# Salary Benchmarks\n"]
        current_tier = None
        for r in rows:
            if r["tier_name"] != current_tier:
                current_tier = r["tier_name"]
                text_parts.append(f"\n## Tier {r['tier']}: {current_tier}\n")
            text_parts.append(f"### {r['role_title']}")
            text_parts.append(f"- National: {r['national_median_range']}")
            text_parts.append(f"- Melbourne FL: {r['melbourne_range']}")
            text_parts.append(f"- Remote: {r['remote_range']}")
            text_parts.append(f"- HCOL: {r['hcol_range']}")
            text_parts.append(f"- $200-250K realistic? {r['target_realistic']}")
            text_parts.append("")

        return jsonify({"text": "\n".join(text_parts), "count": len(rows)})

    return jsonify({"benchmarks": rows, "count": len(rows)})


@bp.route("/api/cola-markets", methods=["GET"])
def get_cola_markets():
    """Get COLA market reference data."""
    rows = db.query("SELECT * FROM cola_markets ORDER BY cola_factor")
    return jsonify({"markets": rows, "count": len(rows)})
