"""Routes for content_sections, voice_rules, salary_benchmarks, cola_markets.

Supports both individual section queries AND full document reconstruction.
"""

import os
import glob as globmod
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


# ---------------------------------------------------------------------------
# POST /api/knowledge/reindex — Scan output directories for generated documents
# ---------------------------------------------------------------------------

@bp.route("/api/knowledge/reindex", methods=["POST"])
def reindex_documents():
    """Scan output directories for generated documents.

    Finds .docx and .pdf files in Output/ directories, checks if they're tracked
    in the DB, updates paths if files moved, and reports counts.

    Body (JSON, optional):
        scan_paths: list of directories to scan (default: common output dirs)
    """
    data = request.get_json(force=True) if request.data else {}

    # Default scan paths relative to project root
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    project_root = os.path.dirname(base_dir)
    default_paths = [
        os.path.join(project_root, "Output"),
        os.path.join(project_root, "Originals"),
        os.path.join(base_dir, "output"),
    ]
    scan_paths = data.get("scan_paths", default_paths)

    found_files = []
    for scan_dir in scan_paths:
        if not os.path.isdir(scan_dir):
            continue
        for ext in ("*.docx", "*.pdf", "*.DOCX", "*.PDF"):
            pattern = os.path.join(scan_dir, "**", ext)
            found_files.extend(globmod.glob(pattern, recursive=True))

    # Normalize paths
    found_files = [os.path.normpath(f) for f in found_files]

    # Check existing document records in generated_documents table (if it exists)
    updated = 0
    missing = 0
    new_found = 0
    tracked_paths = set()

    try:
        existing = db.query("SELECT id, file_path FROM generated_documents") or []
        for doc in existing:
            old_path = doc.get("file_path", "")
            if old_path:
                tracked_paths.add(os.path.normpath(old_path))
                if not os.path.exists(old_path):
                    # Check if file exists under a different path
                    basename = os.path.basename(old_path)
                    matches = [f for f in found_files if os.path.basename(f) == basename]
                    if matches:
                        new_path = matches[0]
                        db.execute(
                            "UPDATE generated_documents SET file_path = %s, updated_at = NOW() WHERE id = %s",
                            (new_path, doc["id"]),
                        )
                        updated += 1
                    else:
                        missing += 1

        # Count newly discovered files not in DB
        for f in found_files:
            if f not in tracked_paths:
                new_found += 1
    except Exception:
        # Table might not exist; just report file counts
        new_found = len(found_files)

    return jsonify({
        "scanned_directories": [p for p in scan_paths if os.path.isdir(p)],
        "total_files_found": len(found_files),
        "paths_updated": updated,
        "files_missing": missing,
        "new_untracked": new_found,
        "files": [{"path": f, "size_kb": round(os.path.getsize(f) / 1024, 1)} for f in found_files[:100]],
    }), 200


# ---------------------------------------------------------------------------
# GET /api/knowledge/stats — KB statistics
# ---------------------------------------------------------------------------

@bp.route("/api/knowledge/stats", methods=["GET"])
def knowledge_stats():
    """Return knowledge base statistics: bullet count, skill count, career entries, voice rules, templates."""
    stats = {}
    table_map = {
        "bullets": "bullets",
        "skills": "skills",
        "career_entries": "career_history",
        "voice_rules": "voice_rules",
        "templates": "resume_templates",
        "recipes": "resume_recipes",
        "content_sections": "content_sections",
        "salary_benchmarks": "salary_benchmarks",
        "summary_variants": "summary_variants",
    }

    for label, table in table_map.items():
        try:
            r = db.query_one(f"SELECT COUNT(*) AS cnt FROM {table}")
            stats[label] = r["cnt"] if r else 0
        except Exception:
            stats[label] = 0

    # Bullet breakdown by type
    try:
        bullet_types = db.query(
            "SELECT type, COUNT(*) AS count FROM bullets GROUP BY type ORDER BY count DESC"
        )
        stats["bullet_types"] = {r["type"]: r["count"] for r in bullet_types} if bullet_types else {}
    except Exception:
        stats["bullet_types"] = {}

    # Skills by category
    try:
        skill_cats = db.query(
            "SELECT category, COUNT(*) AS count FROM skills GROUP BY category ORDER BY count DESC"
        )
        stats["skill_categories"] = {r["category"]: r["count"] for r in skill_cats} if skill_cats else {}
    except Exception:
        stats["skill_categories"] = {}

    return jsonify(stats), 200


# ---------------------------------------------------------------------------
# POST /api/knowledge/validate — Validate bullet against voice rules + metrics
# ---------------------------------------------------------------------------

@bp.route("/api/knowledge/validate", methods=["POST"])
def validate_bullet():
    """Validate a bullet against voice rules and metric requirements.

    Body (JSON):
        text (required): The bullet text to validate
    Returns: violations list, has_metric flag, score
    """
    data = request.get_json(force=True)
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"error": "text is required"}), 400

    issues = []

    # Check for metrics (numbers, percentages, dollar amounts)
    import re
    has_metric = bool(re.search(r'\d+[\%\$KMBkmb]|\$[\d,]+|\d+\s*(?:percent|%|x|X)', text))
    if not has_metric:
        issues.append({
            "type": "missing_metric",
            "message": "Bullet lacks a concrete metric or measurable outcome",
        })

    # Check voice rules — banned words
    banned = db.query(
        "SELECT rule_text, subcategory, explanation FROM voice_rules WHERE category = 'banned_word'"
    ) or []
    lower_text = text.lower()
    for bw in banned:
        if bw["rule_text"].lower() in lower_text:
            issues.append({
                "type": "banned_word",
                "match": bw["rule_text"],
                "subcategory": bw.get("subcategory"),
                "explanation": bw.get("explanation"),
            })

    # Check voice rules — banned constructions
    constructions = db.query(
        "SELECT rule_text, subcategory, explanation FROM voice_rules WHERE category = 'banned_construction'"
    ) or []
    for bc in constructions:
        if bc["rule_text"].lower() in lower_text:
            issues.append({
                "type": "banned_construction",
                "match": bc["rule_text"],
                "subcategory": bc.get("subcategory"),
                "explanation": bc.get("explanation"),
            })

    # Length check
    word_count = len(text.split())
    if word_count < 5:
        issues.append({"type": "too_short", "message": "Bullet is fewer than 5 words"})
    if word_count > 40:
        issues.append({"type": "too_long", "message": "Bullet exceeds 40 words"})

    # Starts with action verb check
    first_word = text.split()[0].lower().rstrip(".,;:")
    weak_starts = {"responsible", "helped", "assisted", "worked", "involved", "participated"}
    if first_word in weak_starts:
        issues.append({
            "type": "weak_start",
            "message": f"Starts with weak verb '{first_word}'. Use a strong action verb.",
        })

    score = max(0, 100 - len(issues) * 20)

    return jsonify({
        "text": text,
        "has_metric": has_metric,
        "word_count": word_count,
        "issues": issues,
        "issue_count": len(issues),
        "score": score,
        "valid": len(issues) == 0,
    }), 200


# ---------------------------------------------------------------------------
# GET /api/knowledge/search-semantic — Semantic search across bullets
# ---------------------------------------------------------------------------

@bp.route("/api/knowledge/search-semantic", methods=["GET"])
def search_semantic():
    """Semantic search across bullets using pgvector (if embeddings exist, else keyword fallback).

    Query params:
        q (required): search query
        limit: max results (default 20)
        type: filter by bullet type
    """
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"error": "q parameter is required"}), 400

    limit = int(request.args.get("limit", 20))
    bullet_type = request.args.get("type")

    # Try pgvector semantic search first
    has_embeddings = False
    try:
        check = db.query_one(
            "SELECT COUNT(*) AS cnt FROM bullets WHERE embedding IS NOT NULL"
        )
        has_embeddings = check and check["cnt"] > 0
    except Exception:
        pass

    if has_embeddings:
        # Use pgvector cosine similarity
        try:
            type_clause = "AND b.type = %s" if bullet_type else ""
            params = [query, limit] if not bullet_type else [query, bullet_type, limit]

            # Generate embedding for the query using the same approach as insert
            # For now, fall back to keyword if we can't generate query embedding
            has_embeddings = False  # Degrade to keyword — generating embeddings needs AI provider
        except Exception:
            has_embeddings = False

    # Keyword fallback with ts_rank
    type_clause = ""
    params = [f"%{query}%", f"%{query}%"]
    if bullet_type:
        type_clause = "AND b.type = %s"
        params.append(bullet_type)
    params.append(limit)

    rows = db.query(
        f"""
        SELECT b.id, b.text, b.type, b.tags, b.career_history_id,
               ch.employer, ch.title,
               ts_rank(to_tsvector('english', b.text), plainto_tsquery('english', %s)) AS rank
        FROM bullets b
        LEFT JOIN career_history ch ON ch.id = b.career_history_id
        WHERE (b.text ILIKE %s OR b.tags::text ILIKE %s)
        {type_clause}
        ORDER BY rank DESC, b.id DESC
        LIMIT %s
        """,
        [query] + params,
    )

    return jsonify({
        "results": rows or [],
        "count": len(rows) if rows else 0,
        "query": query,
        "method": "semantic" if has_embeddings else "keyword",
    }), 200
