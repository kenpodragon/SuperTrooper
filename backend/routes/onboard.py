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

def _build_onboard_next_steps(results: list) -> list:
    """Generate prioritised next-step guidance based on onboard results.

    Examines what was extracted (bullets, skills, career history, recipe)
    and returns an ordered list of suggested actions for the user.
    """
    steps = []
    any_success = any(r.get("status") in ("success", "partial") for r in results)
    if not any_success:
        return [{"priority": 1, "action": "Fix upload errors", "detail": "No files processed successfully. Check file format and retry."}]

    total_bullets = sum(
        (r.get("steps", {}).get("parsing") or {}).get("bullet_count", 0)
        for r in results
        if isinstance((r.get("steps", {}).get("parsing")), dict)
    )
    total_skills = sum(
        (r.get("steps", {}).get("parsing") or {}).get("skill_count", 0)
        for r in results
        if isinstance((r.get("steps", {}).get("parsing")), dict)
    )
    total_jobs = sum(
        (r.get("steps", {}).get("parsing") or {}).get("career_history_count", 0)
        for r in results
        if isinstance((r.get("steps", {}).get("parsing")), dict)
    )
    has_recipe = any(r.get("recipe_id") for r in results)
    has_near_dups = any(
        len((r.get("steps", {}).get("dedup") or {}).get("near_duplicates", [])) > 0
        for r in results
        if isinstance(r.get("steps", {}).get("dedup"), dict)
    )

    priority = 1

    if total_bullets < 10:
        steps.append({
            "priority": priority,
            "action": "Add more resume bullets",
            "detail": f"Only {total_bullets} bullets extracted. Add more achievements with metrics to strengthen your knowledge base.",
            "tool": "search_bullets",
        })
        priority += 1

    if total_skills < 5:
        steps.append({
            "priority": priority,
            "action": "Populate your skills",
            "detail": f"Only {total_skills} skills extracted. Add your full skill set via Settings > Skills.",
            "tool": "get_skills",
        })
        priority += 1

    steps.append({
        "priority": priority,
        "action": "Train voice rules",
        "detail": "Upload writing samples (emails, bios, past cover letters) so the AI learns your tone and style.",
        "endpoint": "POST /api/onboarding/voice-sample",
    })
    priority += 1

    if not has_recipe:
        steps.append({
            "priority": priority,
            "action": "Create your first recipe",
            "detail": "A recipe defines how your resume is structured. Create one via Settings > Recipes or use create_recipe().",
            "tool": "create_recipe",
            "endpoint": "POST /api/onboarding/initial-recipe",
        })
        priority += 1
    else:
        steps.append({
            "priority": priority,
            "action": "Generate your first resume",
            "detail": "A recipe was created from your upload. Use generate_resume() to produce a tailored .docx.",
            "tool": "generate_resume",
        })
        priority += 1

    if has_near_dups:
        steps.append({
            "priority": priority,
            "action": "Review near-duplicate bullets",
            "detail": "Some bullets were flagged as near-duplicates. Review and consolidate via the Bullets page.",
            "tool": "search_bullets",
        })
        priority += 1

    steps.append({
        "priority": priority,
        "action": "Run a gap analysis against a target role",
        "detail": "Paste a job description URL or text to see how well your profile matches.",
        "tool": "match_jd",
    })

    return steps


@bp.route("/api/onboard/status", methods=["GET"])
def onboard_status():
    """Check onboarding completion status across all data categories."""
    with db.get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            cur.execute("SELECT COUNT(*) AS cnt FROM bullets")
            bullets_count = cur.fetchone()["cnt"]

            cur.execute("SELECT COUNT(*) AS cnt FROM career_history")
            career_count = cur.fetchone()["cnt"]

            cur.execute("SELECT COUNT(*) AS cnt FROM contacts")
            contacts_count = cur.fetchone()["cnt"]

            cur.execute("SELECT COUNT(*) AS cnt FROM skills")
            skills_count = cur.fetchone()["cnt"]

            cur.execute("SELECT COUNT(*) AS cnt FROM resume_recipes")
            recipes_count = cur.fetchone()["cnt"]

            cur.execute("SELECT COUNT(*) AS cnt FROM resume_templates")
            templates_count = cur.fetchone()["cnt"]

            cur.execute("SELECT preferences FROM settings WHERE id = 1")
            row = cur.fetchone()
            prefs = (row or {}).get("preferences") or {}
            has_profile = bool(prefs.get("candidate_name") or prefs.get("candidate_email"))

        finally:
            cur.close()

    checks = {
        "has_bullets": bullets_count > 0,
        "has_career_history": career_count > 0,
        "has_contacts": contacts_count > 0,
        "has_skills": skills_count > 0,
        "has_recipes": recipes_count > 0,
        "has_templates": templates_count > 0,
        "has_profile": has_profile,
    }

    completed = sum(1 for v in checks.values() if v)
    total = len(checks)
    completion_percentage = round(completed / total * 100, 1)

    return jsonify({
        **checks,
        "counts": {
            "bullets": bullets_count,
            "career_history": career_count,
            "contacts": contacts_count,
            "skills": skills_count,
            "recipes": recipes_count,
            "templates": templates_count,
        },
        "completion_percentage": completion_percentage,
    })


@bp.route("/api/onboard/next-steps", methods=["GET"])
def onboard_next_steps():
    """Return ordered list of recommended onboarding actions based on current status."""
    # Reuse the status logic
    with db.get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            cur.execute("SELECT COUNT(*) AS cnt FROM bullets")
            has_bullets = cur.fetchone()["cnt"] > 0
            cur.execute("SELECT COUNT(*) AS cnt FROM career_history")
            has_career = cur.fetchone()["cnt"] > 0
            cur.execute("SELECT COUNT(*) AS cnt FROM contacts")
            has_contacts = cur.fetchone()["cnt"] > 0
            cur.execute("SELECT COUNT(*) AS cnt FROM skills")
            has_skills = cur.fetchone()["cnt"] > 0
            cur.execute("SELECT COUNT(*) AS cnt FROM resume_recipes")
            has_recipes = cur.fetchone()["cnt"] > 0
            cur.execute("SELECT preferences FROM settings WHERE id = 1")
            row = cur.fetchone()
            prefs = (row or {}).get("preferences") or {}
            has_profile = bool(prefs.get("candidate_name") or prefs.get("candidate_email"))
        finally:
            cur.close()

    steps = []
    priority = 1

    if not has_profile:
        steps.append({"priority": priority, "action": "Set up your profile",
                       "detail": "Add your name, email, target roles, and locations via POST /api/onboard/quick-setup."})
        priority += 1
    if not has_career:
        steps.append({"priority": priority, "action": "Upload your resume",
                       "detail": "Upload a .docx or .pdf to populate career history, bullets, and skills."})
        priority += 1
    if not has_bullets:
        steps.append({"priority": priority, "action": "Add resume bullets",
                       "detail": "No bullets found. Upload a resume or add achievements with concrete metrics."})
        priority += 1
    if not has_skills:
        steps.append({"priority": priority, "action": "Populate your skills",
                       "detail": "Add technical and leadership skills to enable gap analysis and tailoring."})
        priority += 1
    if not has_contacts:
        steps.append({"priority": priority, "action": "Add networking contacts",
                       "detail": "Import contacts for warm intros, referrals, and outreach."})
        priority += 1
    if not has_recipes:
        steps.append({"priority": priority, "action": "Create a resume recipe",
                       "detail": "A recipe defines resume structure. Upload a resume to auto-generate one."})
        priority += 1
    if has_career and has_bullets:
        steps.append({"priority": priority, "action": "Run a gap analysis",
                       "detail": "Paste a job description to see how your profile matches."})
        priority += 1

    if not steps:
        steps.append({"priority": 1, "action": "You're all set!",
                       "detail": "All onboarding steps complete. Start searching for jobs or generating resumes."})

    return jsonify({"next_steps": steps})


@bp.route("/api/onboard/quick-setup", methods=["POST"])
def onboard_quick_setup():
    """Accept name, email, target_roles, target_locations and upsert into settings.preferences."""
    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip()
    email = data.get("email", "").strip()
    target_roles = data.get("target_roles", [])
    target_locations = data.get("target_locations", [])

    if not name and not email:
        return jsonify({"error": "At least name or email is required."}), 400

    with db.get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            cur.execute("SELECT preferences FROM settings WHERE id = 1")
            row = cur.fetchone()
            prefs = (row or {}).get("preferences") or {}

            if name:
                prefs["candidate_name"] = name
            if email:
                prefs["candidate_email"] = email
            if target_roles:
                prefs["target_roles"] = target_roles
            if target_locations:
                prefs["target_locations"] = target_locations

            cur.execute(
                "UPDATE settings SET preferences = %s, updated_at = NOW() WHERE id = 1",
                (json.dumps(prefs),),
            )
        finally:
            cur.close()

    return jsonify({"success": True, "preferences": prefs})


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

    # Build next_steps guidance based on what was extracted
    next_steps = _build_onboard_next_steps(results)

    return jsonify({"results": results, "total": len(results), "next_steps": next_steps})


# ---------------------------------------------------------------------------
# POST /api/onboard/import-archive — Import career data from uploaded doc
# ---------------------------------------------------------------------------

@bp.route("/api/onboard/import-archive", methods=["POST"])
def import_archive():
    """Import career data from an uploaded resume/document.

    Accepts multipart file upload (.docx or .pdf). Extracts text, parses
    career entries, and inserts into career_history and bullets tables.
    Similar to the main onboard endpoint but focused on supplemental imports.

    Form data:
        file: the uploaded file (.docx or .pdf)
        merge_mode: 'append' (default) or 'replace'
    """
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded. Use multipart form with 'file' field."}), 400

    f = request.files["file"]
    fname = f.filename or "upload"
    merge_mode = request.form.get("merge_mode", "append")

    ext = os.path.splitext(fname)[1].lower()
    if ext not in (".docx", ".pdf"):
        return jsonify({"error": f"Unsupported file type: {ext}. Use .docx or .pdf"}), 400

    # Save to temp file and extract text
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        f.save(tmp.name)
        tmp_path = tmp.name

    try:
        if ext == ".docx":
            text = read_full_text(tmp_path)
        else:
            text = read_pdf_text(tmp_path)
    except Exception as e:
        return jsonify({"error": f"Failed to read file: {str(e)}"}), 500
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass

    if not text or len(text.strip()) < 50:
        return jsonify({"error": "File appears to be empty or too short to parse"}), 400

    # Parse the resume text
    try:
        parsed = parse_resume(text)
    except Exception as e:
        return jsonify({"error": f"Failed to parse resume: {str(e)}"}), 500

    # Extract career entries and bullets
    imported = {"career_entries": 0, "bullets": 0, "skipped_duplicates": 0}

    conn = db.get_connection()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        settings = _get_settings(cur)
        threshold = settings.get("duplicate_threshold", 0.92)

        for entry in parsed.get("experience", []):
            employer = entry.get("company", "Unknown")
            title = entry.get("title", "Unknown")
            start_date = entry.get("start_date")
            end_date = entry.get("end_date")

            # Check for existing career entry
            existing = None
            cur.execute(
                "SELECT id FROM career_history WHERE employer ILIKE %s AND title ILIKE %s LIMIT 1",
                (f"%{employer}%", f"%{title}%"),
            )
            existing = cur.fetchone()

            if existing and merge_mode == "append":
                ch_id = existing["id"]
            elif existing and merge_mode == "replace":
                ch_id = existing["id"]
            else:
                cur.execute(
                    """
                    INSERT INTO career_history (employer, title, start_date, end_date)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                    """,
                    (employer, title, start_date, end_date),
                )
                ch_id = cur.fetchone()["id"]
                imported["career_entries"] += 1

            # Import bullets
            for bullet_text in entry.get("bullets", []):
                bullet_text = bullet_text.strip()
                if not bullet_text:
                    continue

                skip, _ = _dedup_bullet(cur, bullet_text, ch_id, threshold)
                if skip:
                    imported["skipped_duplicates"] += 1
                    continue

                cur.execute(
                    """
                    INSERT INTO bullets (career_history_id, text, type)
                    VALUES (%s, %s, %s)
                    """,
                    (ch_id, bullet_text, "achievement"),
                )
                imported["bullets"] += 1

        conn.commit()
    except Exception as e:
        conn.rollback()
        return jsonify({"error": f"Import failed: {str(e)}"}), 500
    finally:
        conn.close()

    return jsonify({
        "imported": imported,
        "merge_mode": merge_mode,
        "source_file": fname,
        "text_length": len(text),
    }), 201


# ---------------------------------------------------------------------------
# GET /api/onboard/validation — Validate data completeness
# ---------------------------------------------------------------------------

@bp.route("/api/onboard/validation", methods=["GET"])
def validate_onboard_data():
    """Validate current data completeness.

    Checks:
    - Bullets have metrics
    - Skills are categorized
    - Career dates are consistent
    - Required profile fields are filled
    """
    issues = []
    scores = {}

    # 1. Bullets with metrics
    total_bullets = db.query_one("SELECT COUNT(*) AS cnt FROM bullets")
    bullets_count = total_bullets["cnt"] if total_bullets else 0

    import re
    if bullets_count > 0:
        all_bullets = db.query("SELECT id, text FROM bullets") or []
        with_metrics = sum(
            1 for b in all_bullets
            if re.search(r'\d+[\%\$KMBkmb]|\$[\d,]+|\d+\s*(?:percent|%|x|X)', b.get("text", ""))
        )
        metric_pct = round(with_metrics / len(all_bullets) * 100, 1) if all_bullets else 0
        scores["bullets_with_metrics"] = metric_pct
        if metric_pct < 80:
            issues.append({
                "area": "bullets",
                "severity": "warning" if metric_pct >= 50 else "error",
                "message": f"Only {metric_pct}% of bullets have quantifiable metrics ({with_metrics}/{len(all_bullets)})",
            })
    else:
        scores["bullets_with_metrics"] = 0
        issues.append({"area": "bullets", "severity": "error", "message": "No bullets loaded"})

    # 2. Skills categorized
    total_skills = db.query_one("SELECT COUNT(*) AS cnt FROM skills")
    skills_count = total_skills["cnt"] if total_skills else 0
    uncategorized = db.query_one(
        "SELECT COUNT(*) AS cnt FROM skills WHERE category IS NULL OR category = ''"
    )
    uncat_count = uncategorized["cnt"] if uncategorized else 0

    if skills_count > 0:
        cat_pct = round((skills_count - uncat_count) / skills_count * 100, 1)
        scores["skills_categorized"] = cat_pct
        if uncat_count > 0:
            issues.append({
                "area": "skills",
                "severity": "warning",
                "message": f"{uncat_count} skills are uncategorized",
            })
    else:
        scores["skills_categorized"] = 0
        issues.append({"area": "skills", "severity": "error", "message": "No skills loaded"})

    # 3. Career dates consistency
    career = db.query(
        "SELECT id, employer, title, start_date, end_date FROM career_history ORDER BY start_date DESC"
    ) or []
    scores["career_entries"] = len(career)

    for c in career:
        if not c.get("start_date"):
            issues.append({
                "area": "career_dates",
                "severity": "warning",
                "message": f"Missing start date: {c.get('employer')} - {c.get('title')}",
            })
        if c.get("start_date") and c.get("end_date") and c["start_date"] > c["end_date"]:
            issues.append({
                "area": "career_dates",
                "severity": "error",
                "message": f"Start date after end date: {c.get('employer')} - {c.get('title')}",
            })

    # 4. Resume header completeness
    header = db.query_one("SELECT * FROM resume_header ORDER BY id LIMIT 1")
    if header:
        required_fields = ["full_name", "email", "phone"]
        missing = [f for f in required_fields if not header.get(f)]
        scores["header_complete"] = round((len(required_fields) - len(missing)) / len(required_fields) * 100, 1)
        if missing:
            issues.append({
                "area": "header",
                "severity": "warning",
                "message": f"Missing header fields: {', '.join(missing)}",
            })
    else:
        scores["header_complete"] = 0
        issues.append({"area": "header", "severity": "error", "message": "No resume header found"})

    # 5. Summary variants
    summaries = db.query_one("SELECT COUNT(*) AS cnt FROM summary_variants")
    scores["summary_variants"] = summaries["cnt"] if summaries else 0
    if not summaries or summaries["cnt"] == 0:
        issues.append({"area": "summaries", "severity": "warning", "message": "No summary variants created"})

    # Overall completeness score
    weights = {
        "bullets_with_metrics": 30,
        "skills_categorized": 20,
        "header_complete": 20,
        "career_entries": 15,
        "summary_variants": 15,
    }
    overall = 0
    for key, weight in weights.items():
        val = scores.get(key, 0)
        if key in ("career_entries", "summary_variants"):
            val = min(100, val * 20)  # Normalize counts to percentage
        overall += (val / 100) * weight

    return jsonify({
        "overall_score": round(overall, 1),
        "scores": scores,
        "issues": issues,
        "issue_count": len(issues),
        "data_ready": len([i for i in issues if i["severity"] == "error"]) == 0,
    }), 200


# ---------------------------------------------------------------------------
# POST /api/onboard/create-starter-recipes — Auto-create starter recipes
# ---------------------------------------------------------------------------

@bp.route("/api/onboard/create-starter-recipes", methods=["POST"])
def create_starter_recipes():
    """Auto-create starter recipes for common role types based on loaded data.

    Analyzes career history and skills to determine appropriate role types,
    then creates recipe outlines for each.

    Body (JSON, optional):
        role_types: list of role types to create (default: auto-detect)
    """
    data = request.get_json(force=True) if request.data else {}
    requested_types = data.get("role_types")

    # Pull career and skills data
    career = db.query("SELECT * FROM career_history ORDER BY start_date DESC") or []
    skills = db.query("SELECT name, category, proficiency FROM skills ORDER BY proficiency DESC NULLS LAST") or []
    bullets = db.query("SELECT id, text, career_history_id FROM bullets ORDER BY id DESC LIMIT 50") or []

    if not career:
        return jsonify({"error": "No career history loaded. Upload a resume first."}), 400

    # Auto-detect role types from career titles
    if not requested_types:
        titles = [c.get("title", "").lower() for c in career]
        detected_types = set()

        type_keywords = {
            "engineering_manager": ["engineering manager", "eng manager", "dev manager", "technical manager"],
            "director_engineering": ["director", "vp engineering", "head of engineering"],
            "senior_engineer": ["senior engineer", "staff engineer", "principal engineer", "lead engineer"],
            "product_manager": ["product manager", "product lead", "pm"],
            "cto": ["cto", "chief technology", "chief technical"],
            "general_tech_lead": ["tech lead", "technical lead", "architect"],
        }

        for role_type, keywords in type_keywords.items():
            for title in titles:
                if any(kw in title for kw in keywords):
                    detected_types.add(role_type)
                    break

        # Always include a general type
        if not detected_types:
            detected_types.add("general_tech_lead")

        requested_types = list(detected_types)

    # Check for existing recipes
    existing = db.query("SELECT name FROM resume_recipes") or []
    existing_names = {r["name"].lower() for r in existing}

    created = []
    skipped = []

    for role_type in requested_types:
        recipe_name = f"Starter - {role_type.replace('_', ' ').title()}"

        if recipe_name.lower() in existing_names:
            skipped.append(recipe_name)
            continue

        # Build recipe JSON
        top_skills = [s["name"] for s in skills[:12]]
        top_bullets_ids = [b["id"] for b in bullets[:10]]

        recipe_json = {
            "role_type": role_type,
            "sections": {
                "summary": {"type": "summary_variant", "role_type": role_type},
                "experience": {
                    "entries": [
                        {
                            "career_history_id": c.get("id"),
                            "employer": c.get("employer"),
                            "title": c.get("title"),
                        }
                        for c in career[:5]
                    ],
                },
                "skills": {"items": top_skills},
            },
            "bullet_ids": top_bullets_ids,
            "auto_generated": True,
        }

        # Get default template_id
        default_template = db.query_one("SELECT id FROM resume_templates ORDER BY id LIMIT 1")
        if not default_template:
            return jsonify({"error": "No resume template found. Upload a template first."}), 400
        template_id = default_template["id"]

        row = db.execute_returning(
            """
            INSERT INTO resume_recipes (name, description, template_id, recipe, is_active)
            VALUES (%s, %s, %s, %s, true)
            RETURNING id, name
            """,
            (
                recipe_name,
                f"Auto-generated starter recipe for {role_type.replace('_', ' ')} roles",
                template_id,
                json.dumps(recipe_json),
            ),
        )
        if row:
            created.append(row)

    return jsonify({
        "created": created,
        "skipped": skipped,
        "role_types_detected": requested_types,
        "created_count": len(created),
        "skipped_count": len(skipped),
    }), 201


# ---------------------------------------------------------------------------
# Onboarding Checklist
# ---------------------------------------------------------------------------

ONBOARD_STEPS = [
    {"key": "upload_resume", "name": "Upload Resume", "description": "Upload your primary resume (.docx or .pdf)"},
    {"key": "parse_career", "name": "Parse Career History", "description": "Extract roles, bullets, and skills from resume"},
    {"key": "set_target_roles", "name": "Set Target Roles", "description": "Define the roles you are targeting"},
    {"key": "configure_voice", "name": "Configure Voice Rules", "description": "Set up writing style preferences"},
    {"key": "add_contacts", "name": "Add Contacts", "description": "Import or add networking contacts"},
    {"key": "connect_integrations", "name": "Connect Integrations", "description": "Link Gmail, Calendar, or LinkedIn"},
    {"key": "first_application", "name": "Track First Application", "description": "Add your first job application"},
    {"key": "generate_resume", "name": "Generate Tailored Resume", "description": "Create a recipe and generate a resume"},
]


@bp.route("/api/onboard/checklist", methods=["GET"])
def onboard_checklist():
    """Step-by-step onboarding checklist with completion status."""
    steps = []
    for step_def in ONBOARD_STEPS:
        completed = False
        key = step_def["key"]

        try:
            if key == "upload_resume":
                r = db.query_one("SELECT COUNT(*) AS cnt FROM resume_templates")
                completed = (r and r["cnt"] > 0)
            elif key == "parse_career":
                r = db.query_one("SELECT COUNT(*) AS cnt FROM career_history")
                completed = (r and r["cnt"] > 0)
            elif key == "set_target_roles":
                r = db.query_one("SELECT preferences FROM settings WHERE id = 1")
                prefs = r.get("preferences") or {} if r else {}
                if isinstance(prefs, str):
                    prefs = json.loads(prefs) if prefs else {}
                completed = bool(prefs.get("target_roles"))
            elif key == "configure_voice":
                r = db.query_one("SELECT COUNT(*) AS cnt FROM voice_rules")
                completed = (r and r["cnt"] > 0)
            elif key == "add_contacts":
                r = db.query_one("SELECT COUNT(*) AS cnt FROM contacts")
                completed = (r and r["cnt"] > 0)
            elif key == "connect_integrations":
                completed = bool(os.environ.get("GMAIL_TOKEN") or os.environ.get("GOOGLE_TOKEN"))
            elif key == "first_application":
                r = db.query_one("SELECT COUNT(*) AS cnt FROM applications")
                completed = (r and r["cnt"] > 0)
            elif key == "generate_resume":
                r = db.query_one("SELECT COUNT(*) AS cnt FROM resume_recipes")
                completed = (r and r["cnt"] > 0)
        except Exception:
            completed = False

        # Check if step was explicitly skipped
        skip_row = db.query_one(
            "SELECT 1 FROM settings WHERE id = 1 AND (preferences->>'skipped_onboard_steps')::jsonb ? %s",
            (key,),
        ) if key else None
        skipped = bool(skip_row) if skip_row else False

        steps.append({**step_def, "completed": completed, "skipped": skipped})

    completed_count = sum(1 for s in steps if s["completed"] or s["skipped"])
    total = len(steps)

    return jsonify({
        "steps": steps,
        "completed_count": completed_count,
        "total_steps": total,
        "completion_pct": round(completed_count / total * 100) if total else 0,
    }), 200


@bp.route("/api/onboard/skip-step", methods=["POST"])
def skip_onboard_step():
    """Mark an onboarding step as skipped.

    Body JSON: {"step_key": str}
    """
    data = request.get_json(force=True)
    step_key = data.get("step_key")
    if not step_key:
        return jsonify({"error": "step_key is required"}), 400

    valid_keys = {s["key"] for s in ONBOARD_STEPS}
    if step_key not in valid_keys:
        return jsonify({"error": f"Invalid step_key. Valid: {', '.join(sorted(valid_keys))}"}), 400

    # Read current preferences
    row = db.query_one("SELECT preferences FROM settings WHERE id = 1")
    prefs = (row.get("preferences") or {}) if row else {}
    if isinstance(prefs, str):
        prefs = json.loads(prefs) if prefs else {}

    skipped = prefs.get("skipped_onboard_steps", [])
    if step_key not in skipped:
        skipped.append(step_key)
    prefs["skipped_onboard_steps"] = skipped

    db.execute(
        "UPDATE settings SET preferences = %s::jsonb, updated_at = NOW() WHERE id = 1",
        (json.dumps(prefs),),
    )

    return jsonify({"skipped_step": step_key, "all_skipped": skipped}), 200
