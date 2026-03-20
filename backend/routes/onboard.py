"""Onboarding upload endpoint — accepts .docx/.pdf resumes and runs the full
extract → parse → insert → templatize → recipe → reconstruct → compare pipeline.
"""

import io
import json
import os
import sys
import tempfile
import traceback
from difflib import SequenceMatcher
from pathlib import Path

from flask import Blueprint, request, jsonify
import psycopg2.extras

import db

# Add code/utils to import path so we can use the shared scripts.
# Inside Docker the utils volume is mounted at /app/utils.
# Outside Docker, traverse from routes/ -> backend/ -> code/ -> utils/.
_UTILS_DOCKER = "/app/utils"
_UTILS_LOCAL = str(Path(__file__).resolve().parent.parent.parent / "utils")
for _p in (_UTILS_DOCKER, _UTILS_LOCAL):
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

from read_docx import read_full_text
from read_pdf import read_pdf_text
from templatize_resume import templatize
from generate_resume import generate_resume, resolve_recipe
from compare_docs import extract_paragraphs, compare_text

from parsers import parse_resume
from ai_providers import get_provider

bp = Blueprint("onboard", __name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_settings(cur):
    """Read settings row."""
    cur.execute(
        "SELECT duplicate_threshold, ai_provider, ai_enabled FROM settings WHERE id = 1"
    )
    row = cur.fetchone()
    if row:
        return dict(row)
    return {"duplicate_threshold": 0.92, "ai_provider": "none", "ai_enabled": False}


def _dedup_bullet(cur, text, career_history_id, threshold):
    """Check for exact or near-duplicate bullets.

    Returns:
        (skip: bool, near_dup_id: int|None)
    """
    cur.execute(
        "SELECT id, text FROM bullets WHERE career_history_id = %s",
        (career_history_id,),
    )
    for row in cur.fetchall():
        existing = row["text"]
        if existing == text:
            return True, None  # exact dup — skip
        ratio = SequenceMatcher(None, existing, text).ratio()
        if ratio >= threshold:
            return False, row["id"]  # near dup — insert but flag
    return False, None


def _dedup_skill(cur, name):
    """Return existing skill id if name already exists, else None."""
    cur.execute("SELECT id FROM skills WHERE LOWER(name) = LOWER(%s)", (name,))
    row = cur.fetchone()
    return row["id"] if row else None


def _insert_career_history(cur, entry):
    """Insert a career_history row, or return existing id if employer+title already exists."""
    employer = entry.get("employer") or "Unknown"
    title = entry.get("title") or "Unknown"

    # Check for existing (unique constraint on employer+title)
    cur.execute(
        "SELECT id FROM career_history WHERE employer = %s AND title = %s",
        (employer, title),
    )
    existing = cur.fetchone()
    if existing:
        return existing["id"]

    cur.execute(
        """INSERT INTO career_history
               (employer, title, start_date, end_date, location, industry,
                team_size, budget_usd, revenue_impact, is_current, intro_text, notes)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
           RETURNING id""",
        (
            employer,
            title,
            entry.get("start_date"),
            entry.get("end_date"),
            entry.get("location"),
            entry.get("industry"),
            entry.get("team_size"),
            entry.get("budget_usd"),
            entry.get("revenue_impact"),
            entry.get("is_current", False),
            entry.get("intro_text"),
            entry.get("notes"),
        ),
    )
    return cur.fetchone()["id"]


def _insert_bullet(cur, career_history_id, bullet_text, source_file):
    """Insert a bullet row. Returns the new id."""
    cur.execute(
        """INSERT INTO bullets (career_history_id, text, type, source_file)
           VALUES (%s, %s, %s, %s) RETURNING id""",
        (career_history_id, bullet_text, "achievement", source_file),
    )
    return cur.fetchone()["id"]


def _insert_skill(cur, name, category=None, proficiency=None):
    """Insert a skill row. Returns the new id."""
    cur.execute(
        "INSERT INTO skills (name, category, proficiency) VALUES (%s,%s,%s) RETURNING id",
        (name, category, proficiency),
    )
    return cur.fetchone()["id"]


def _store_original_template(cur, filename, docx_bytes):
    """Store the uploaded resume in resume_templates as uploaded_original.
    Returns template id.
    """
    cur.execute(
        """INSERT INTO resume_templates
               (name, filename, template_blob, template_type, is_active)
           VALUES (%s, %s, %s, 'uploaded_original', false)
           RETURNING id""",
        (f"Upload: {filename}", filename, psycopg2.Binary(docx_bytes)),
    )
    return cur.fetchone()["id"]


def _build_recipe_slots(template_map, career_ids, bullet_ids, skill_ids, parsed):
    """Map template_map slots to inserted DB rows for recipe creation.

    Uses original_text matching where possible to map slots to the correct
    career_history, bullets, or skills rows.
    """
    slots = {}
    if not template_map:
        return slots

    # Build quick lookup from parsed data
    # career_history entries keyed by employer+title
    ch_lookup = {}
    for i, ch in enumerate(parsed.get("career_history", [])):
        key = (ch.get("employer", ""), ch.get("title", ""))
        if i < len(career_ids):
            ch_lookup[key] = career_ids[i]

    job_idx = 0
    bullet_offset = 0
    for slot in template_map.get("slots", []):
        slot_name = slot.get("name", "")
        slot_type = slot.get("type", "")

        if slot_type == "header":
            slots[slot_name] = {"literal": slot.get("original_text", "")}
        elif slot_type == "headline":
            slots[slot_name] = {"literal": slot.get("original_text", "")}
        elif slot_type == "summary":
            slots[slot_name] = {"literal": slot.get("original_text", "")}
        elif slot_type == "highlight":
            slots[slot_name] = {"literal": slot.get("original_text", "")}
        elif slot_type == "keywords":
            slots[slot_name] = {"literal": slot.get("original_text", "")}
        elif slot_type in ("job_header", "job_intro"):
            if job_idx < len(career_ids):
                slots[slot_name] = {
                    "table": "career_history",
                    "id": career_ids[job_idx],
                    "column": "employer" if slot_type == "job_header" else "intro_text",
                }
            else:
                slots[slot_name] = {"literal": slot.get("original_text", "")}
        elif slot_type == "bullet":
            if bullet_offset < len(bullet_ids):
                slots[slot_name] = {
                    "table": "bullets",
                    "id": bullet_ids[bullet_offset],
                    "column": "text",
                }
                bullet_offset += 1
            else:
                slots[slot_name] = {"literal": slot.get("original_text", "")}
        elif slot_type == "education":
            slots[slot_name] = {"literal": slot.get("original_text", "")}
        elif slot_type == "certification":
            slots[slot_name] = {"literal": slot.get("original_text", "")}
        else:
            slots[slot_name] = {"literal": slot.get("original_text", "")}

        # Advance job_idx when we hit a new job_header
        if slot_type == "job_header":
            job_idx += 1

    return slots


def _process_file(filename, file_bytes, file_ext):
    """Process a single uploaded file through the full pipeline.

    Returns a report dict.
    """
    report = {
        "filename": filename,
        "status": "success",
        "steps": {},
        "errors": [],
    }

    tmp_dir = tempfile.mkdtemp(prefix="onboard_")
    original_path = os.path.join(tmp_dir, filename)

    try:
        # ----- Step 0: Save file to temp -----
        with open(original_path, "wb") as f:
            f.write(file_bytes)

        docx_path = original_path

        # ----- Step 1: PDF → DOCX conversion if needed -----
        if file_ext == ".pdf":
            try:
                from pdf2docx import Converter
                docx_path = os.path.join(tmp_dir, Path(filename).stem + ".docx")
                cv = Converter(original_path)
                cv.convert(docx_path)
                cv.close()
                report["steps"]["pdf_conversion"] = "ok"
            except Exception as e:
                report["steps"]["pdf_conversion"] = f"failed: {e}"
                report["errors"].append(f"PDF conversion failed: {e}")
                report["status"] = "partial"
                # Try reading PDF text directly
                try:
                    raw_text = read_pdf_text(original_path)
                    report["steps"]["text_extraction"] = f"ok (pdf direct, {len(raw_text)} chars)"
                    # Can't templatize without docx, so we'll skip those steps
                    docx_path = None
                except Exception as e2:
                    report["errors"].append(f"PDF text extraction also failed: {e2}")
                    report["status"] = "failed"
                    return report

        # ----- Step 2: Extract text -----
        if "text_extraction" not in report["steps"]:
            try:
                raw_text = read_full_text(docx_path)
                report["steps"]["text_extraction"] = f"ok ({len(raw_text)} chars)"
            except Exception as e:
                report["errors"].append(f"Text extraction failed: {e}")
                report["status"] = "failed"
                return report

        # ----- Step 3: Parse -----
        try:
            provider = get_provider()
            parsed = parse_resume(raw_text, provider)
            parsing_method = "ai_enhanced" if provider else "rule_based"
            confidence = parsed.get("confidence", 0.0)
            report["steps"]["parsing"] = {
                "method": parsing_method,
                "confidence": confidence,
                "career_history_count": len(parsed.get("career_history", [])),
                "bullet_count": sum(
                    len(ch.get("bullets", []))
                    for ch in parsed.get("career_history", [])
                ),
                "skill_count": len(parsed.get("skills", [])),
            }
        except Exception as e:
            report["errors"].append(f"Parsing failed: {e}")
            report["status"] = "failed"
            return report

        # ----- Step 4: Insert into DB -----
        career_ids = []
        bullet_ids = []
        skill_ids = []
        near_dups = []

        with db.get_conn() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            try:
                settings = _get_settings(cur)
                dup_threshold = float(settings.get("duplicate_threshold") or 0.92)

                # Career history + bullets
                for entry in parsed.get("career_history", []):
                    ch_id = _insert_career_history(cur, entry)
                    career_ids.append(ch_id)

                    for bullet_text in entry.get("bullets", []):
                        if not bullet_text or not bullet_text.strip():
                            continue
                        skip, near_id = _dedup_bullet(
                            cur, bullet_text, ch_id, dup_threshold
                        )
                        if skip:
                            continue
                        bid = _insert_bullet(cur, ch_id, bullet_text, filename)
                        bullet_ids.append(bid)
                        if near_id:
                            near_dups.append({
                                "new_id": bid,
                                "similar_to": near_id,
                                "text_preview": bullet_text[:80],
                            })

                # Skills
                for skill in parsed.get("skills", []):
                    name = skill if isinstance(skill, str) else skill.get("name", "")
                    cat = None if isinstance(skill, str) else skill.get("category")
                    prof = None if isinstance(skill, str) else skill.get("proficiency")
                    if not name:
                        continue
                    existing_id = _dedup_skill(cur, name)
                    if existing_id:
                        skill_ids.append(existing_id)
                    else:
                        sid = _insert_skill(cur, name, cat, prof)
                        skill_ids.append(sid)

                report["steps"]["db_insert"] = {
                    "career_history_ids": career_ids,
                    "bullet_ids": bullet_ids,
                    "skill_ids": skill_ids,
                    "near_duplicates": near_dups,
                    "skipped_exact_dups": sum(
                        len(ch.get("bullets", []))
                        for ch in parsed.get("career_history", [])
                    ) - len(bullet_ids) - len([b for b in parsed.get("career_history", []) for bt in b.get("bullets", []) if not bt or not bt.strip()]),
                }

                # ----- Step 5: Store original as template -----
                if docx_path:
                    with open(docx_path, "rb") as f:
                        docx_bytes = f.read()
                    template_id = _store_original_template(cur, filename, docx_bytes)
                    report["steps"]["template_stored"] = {"template_id": template_id}
                else:
                    template_id = None
                    report["steps"]["template_stored"] = "skipped (no docx)"

                # ----- Step 6: Templatize -----
                recipe_id = None
                match_score = None

                if docx_path:
                    try:
                        tmpl_docx = os.path.join(tmp_dir, "template_placeholder.docx")
                        tmpl_map_path = os.path.join(tmp_dir, "template_map.json")
                        templ_result = templatize(docx_path, tmpl_docx, tmpl_map_path)
                        report["steps"]["templatize"] = {
                            "slots": templ_result.get("slot_count", 0),
                            "template_docx": tmpl_docx,
                        }

                        # Read the template map
                        with open(tmpl_map_path, "r") as f:
                            template_map = json.load(f)

                        # Read template blob
                        with open(tmpl_docx, "rb") as f:
                            tmpl_blob = f.read()

                        # Update template row with map and blob
                        if template_id:
                            cur.execute(
                                """UPDATE resume_templates
                                   SET template_map = %s,
                                       template_blob = %s
                                   WHERE id = %s""",
                                (json.dumps(template_map), psycopg2.Binary(tmpl_blob), template_id),
                            )

                        # ----- Step 7: Create recipe -----
                        try:
                            cur.execute("SAVEPOINT recipe_sp")
                            slots = _build_recipe_slots(
                                template_map, career_ids, bullet_ids, skill_ids, parsed
                            )
                            cur.execute(
                                """INSERT INTO resume_recipes
                                       (name, template_id, recipe, is_active)
                                   VALUES (%s, %s, %s, true)
                                   RETURNING id""",
                                (
                                    f"Onboard: {filename}",
                                    template_id,
                                    json.dumps(slots),
                                ),
                            )
                            recipe_id = cur.fetchone()["id"]
                            cur.execute("RELEASE SAVEPOINT recipe_sp")
                            report["steps"]["recipe"] = {"recipe_id": recipe_id, "slot_count": len(slots)}
                        except Exception as e:
                            cur.execute("ROLLBACK TO SAVEPOINT recipe_sp")
                            report["steps"]["recipe"] = f"failed: {e}"
                            report["errors"].append(f"Recipe creation failed: {e}")

                        # ----- Step 8: Reconstruct -----
                        try:
                            cur.execute("SAVEPOINT reconstruct_sp")
                            if recipe_id and template_id:
                                content_map = resolve_recipe(conn, slots)
                                doc = generate_resume(tmpl_blob, content_map, template_map)
                                reconstructed_path = os.path.join(tmp_dir, "reconstructed.docx")
                                doc.save(reconstructed_path)
                                cur.execute("RELEASE SAVEPOINT reconstruct_sp")
                                report["steps"]["reconstruct"] = "ok"

                                # ----- Step 9: Compare -----
                                try:
                                    paras_orig = extract_paragraphs(docx_path)
                                    paras_recon = extract_paragraphs(reconstructed_path)
                                    diff_text = compare_text(paras_orig, paras_recon)

                                    # Calculate match percentage
                                    total = max(len(paras_orig), len(paras_recon), 1)
                                    matching = sum(
                                        1 for a, b in zip(paras_orig, paras_recon)
                                        if a.strip() == b.strip()
                                    )
                                    match_score = round(matching / total * 100, 1)

                                    report["steps"]["compare"] = {
                                        "match_score": match_score,
                                        "total_paragraphs": total,
                                        "matching_paragraphs": matching,
                                        "diff_preview": diff_text[:500] if diff_text else "(identical)",
                                    }
                                except Exception as e:
                                    report["steps"]["compare"] = f"failed: {e}"
                                    report["errors"].append(f"Compare failed: {e}")
                            else:
                                cur.execute("RELEASE SAVEPOINT reconstruct_sp")
                                report["steps"]["reconstruct"] = "skipped (no recipe or template)"
                        except Exception as e:
                            cur.execute("ROLLBACK TO SAVEPOINT reconstruct_sp")
                            report["steps"]["reconstruct"] = f"failed: {e}"
                            report["errors"].append(f"Reconstruction failed: {e}")

                    except Exception as e:
                        report["steps"]["templatize"] = f"failed: {e}"
                        report["errors"].append(f"Templatize failed: {e}")
                else:
                    report["steps"]["templatize"] = "skipped (no docx)"

                # ----- Step 10: Record in onboard_uploads -----
                cur.execute(
                    """INSERT INTO onboard_uploads
                           (filename, file_type, file_size, status, parsing_method,
                            parsing_confidence, career_history_ids, bullet_ids,
                            skill_ids, template_id, recipe_id, match_score, report)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                       RETURNING id""",
                    (
                        filename,
                        file_ext.lstrip("."),
                        len(file_bytes),
                        report["status"],
                        parsing_method,
                        confidence,
                        career_ids or None,
                        bullet_ids or None,
                        skill_ids or None,
                        template_id,
                        recipe_id,
                        match_score,
                        json.dumps(report),
                    ),
                )
                upload_id = cur.fetchone()["id"]
                report["upload_id"] = upload_id

            finally:
                cur.close()

        # Summary fields at top level
        report["template_id"] = template_id
        report["recipe_id"] = recipe_id
        report["match_score"] = match_score
        report["parsing_method"] = parsing_method
        report["parsing_confidence"] = confidence

    except Exception as e:
        report["status"] = "failed"
        report["errors"].append(f"Unexpected error: {e}\n{traceback.format_exc()}")

    return report


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------

@bp.route("/api/onboard/upload", methods=["POST"])
def upload():
    """Accept one or more .docx/.pdf files and run the full onboarding pipeline."""
    if "files" not in request.files:
        return jsonify({"error": "No files provided. Use field name 'files'."}), 400

    files = request.files.getlist("files")
    if not files:
        return jsonify({"error": "No files provided."}), 400

    results = []
    for f in files:
        fname = f.filename or "unknown"
        ext = Path(fname).suffix.lower()
        if ext not in (".docx", ".pdf"):
            results.append({
                "filename": fname,
                "status": "failed",
                "errors": [f"Unsupported file type: {ext}. Only .docx and .pdf accepted."],
            })
            continue

        file_bytes = f.read()
        report = _process_file(fname, file_bytes, ext)
        results.append(report)

    return jsonify({"results": results, "total": len(results)})
