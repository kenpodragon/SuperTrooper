"""KB dedup routes — scan, apply, employer-rename, summary utilities."""

import db
import kb_dedup_engine
from flask import Blueprint, jsonify, request

bp = Blueprint("kb_dedup", __name__)

# ---------------------------------------------------------------------------
# Entity configuration
# ---------------------------------------------------------------------------

ENTITY_TABLES = {
    "career_history": "career_history",
    "bullets": "bullets",
    "skills": "skills",
    "education": "education",
    "certifications": "certifications",
    "summaries": "summary_variants",
    "languages": "languages",
    "references": '"references"',
}

ENTITY_COLUMNS = {
    "career_history": "id, employer, title, start_date, end_date, location, industry, intro_text, notes",
    "bullets": "id, career_history_id, text, type, tags, source_file",
    "skills": "id, name, category, proficiency, last_used_year",
    "education": "id, degree, field, institution, location, type, sort_order",
    "certifications": "id, name, issuer, is_active, sort_order",
    "summaries": "id, role_type, text",
    "languages": "id, name, proficiency",
    "references": "id, name, title, company, relationship, email, phone, linkedin_url, notes, career_history_id",
}

GROUP_FUNCTIONS = {
    "career_history": kb_dedup_engine.group_career_history,
    "bullets": kb_dedup_engine.group_bullets,
    "skills": kb_dedup_engine.group_skills,
    "education": kb_dedup_engine.group_education,
    "certifications": kb_dedup_engine.group_certifications,
    "summaries": kb_dedup_engine.group_summaries,
    "languages": kb_dedup_engine.group_languages,
    "references": kb_dedup_engine.group_references,
}


def _fetch_all(entity_type: str) -> list:
    """SELECT all records for the given entity type, return as list of dicts."""
    table = ENTITY_TABLES[entity_type]
    cols = ENTITY_COLUMNS[entity_type]
    return db.query(f"SELECT {cols} FROM {table}")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@bp.route("/api/kb/dedup/scan", methods=["POST"])
def scan():
    """Scan an entity type for duplicates."""
    data = request.get_json(force=True) or {}
    entity_type = data.get("entity_type")
    use_ai = bool(data.get("use_ai", False))

    if not entity_type or entity_type not in ENTITY_TABLES:
        return jsonify({"error": f"Invalid entity_type. Must be one of: {', '.join(ENTITY_TABLES)}"}), 400

    records = _fetch_all(entity_type)

    if use_ai:
        result = kb_dedup_engine.ai_enhanced_group(entity_type, records)
    else:
        fn = GROUP_FUNCTIONS[entity_type]
        result = fn(records)

    return jsonify(result), 200


@bp.route("/api/kb/dedup/apply", methods=["POST"])
def apply():
    """Apply confirmed merges, deletes, and reclassifications."""
    data = request.get_json(force=True) or {}
    entity_type = data.get("entity_type")

    if not entity_type or entity_type not in ENTITY_TABLES:
        return jsonify({"error": f"Invalid entity_type. Must be one of: {', '.join(ENTITY_TABLES)}"}), 400

    # For summaries, the execution functions use the DB table name "summary_variants"
    exec_entity = "summary_variants" if entity_type == "summaries" else entity_type

    merges = data.get("merges", [])
    deletes = data.get("deletes", [])
    reclassifications = data.get("reclassifications", [])

    merged = 0
    deleted = 0
    reclassified = 0
    errors = []

    for merge in merges:
        winner_id = merge.get("winner_id")
        loser_ids = merge.get("loser_ids", [])
        if winner_id is None or not loser_ids:
            errors.append(f"Invalid merge entry: {merge}")
            continue
        try:
            result = kb_dedup_engine.execute_merge(exec_entity, winner_id, loser_ids)
            merged += result.get("merged", 0)
        except Exception as e:
            errors.append(f"Merge winner={winner_id}: {e}")

    if deletes:
        try:
            result = kb_dedup_engine.execute_delete(exec_entity, deletes)
            deleted += result.get("deleted", 0)
            errors.extend(result.get("errors", []))
        except Exception as e:
            errors.append(f"Delete: {e}")

    if reclassifications:
        for item in reclassifications:
            target_table = item.get("target_table")
            if not target_table:
                errors.append(f"Reclassification missing target_table: {item}")
                continue
            try:
                result = kb_dedup_engine.execute_reclassify(exec_entity, target_table, [item])
                reclassified += result.get("reclassified", 0)
                errors.extend(result.get("errors", []))
            except Exception as e:
                errors.append(f"Reclassify id={item.get('id')}: {e}")

    return jsonify({"merged": merged, "deleted": deleted, "reclassified": reclassified, "errors": errors}), 200


@bp.route("/api/kb/dedup/employer-rename", methods=["POST"])
def employer_rename():
    """Rename employer across career_history records."""
    data = request.get_json(force=True) or {}
    career_history_ids = data.get("career_history_ids", [])
    canonical_name = data.get("canonical_name")

    if not career_history_ids or not canonical_name:
        return jsonify({"error": "career_history_ids and canonical_name are required"}), 400

    result = kb_dedup_engine.execute_employer_rename(career_history_ids, canonical_name)
    return jsonify({"updated": result.get("updated", 0)}), 200


@bp.route("/api/kb/dedup/summaries/role-types", methods=["POST"])
def rename_role_types():
    """Rename role_types across summary_variants."""
    data = request.get_json(force=True) or {}
    reassignments = data.get("reassignments", {})

    if not reassignments:
        return jsonify({"error": "reassignments dict is required"}), 400

    result = kb_dedup_engine.execute_summary_role_type_rename(reassignments)
    return jsonify({"updated": result.get("updated", 0)}), 200


@bp.route("/api/kb/dedup/summaries/suggest-role-types", methods=["POST"])
def suggest_role_types():
    """AI-suggest role types for all summaries."""
    summaries = db.query("SELECT id, role_type, text FROM summary_variants")
    result = kb_dedup_engine.ai_suggest_role_types(summaries)
    return jsonify({"suggestions": result.get("suggestions", [])}), 200


@bp.route("/api/kb/dedup/summaries/split", methods=["POST"])
def split_summaries():
    """Apply summary splits — extract bullets from mixed-content summaries."""
    data = request.get_json(force=True) or {}
    splits = data.get("splits", [])

    if not splits:
        return jsonify({"error": "splits list is required"}), 400

    splits_applied = 0
    bullets_created = 0
    errors = []

    for split in splits:
        summary_id = split.get("id")
        keep_summary_text = split.get("keep_summary_text")
        extract_bullets = split.get("extract_bullets", [])
        career_history_id = split.get("career_history_id")

        if summary_id is None:
            errors.append(f"Split missing id: {split}")
            continue

        try:
            result = kb_dedup_engine.execute_summary_split(
                split_id=summary_id,
                keep_summary_text=keep_summary_text,
                extract_bullets=extract_bullets,
                career_history_id=career_history_id,
            )
            splits_applied += 1
            bullets_created += result.get("bullets_created", 0)
            errors.extend(result.get("errors", []))
        except Exception as e:
            errors.append(f"Split id={summary_id}: {e}")

    return jsonify({"splits_applied": splits_applied, "bullets_created": bullets_created, "errors": errors}), 200
