"""Routes for resume generation, templates, header, education, certifications."""

from flask import Blueprint, request, jsonify, send_file
import io
import json
import re
import db
from docx import Document

bp = Blueprint("resume", __name__)


# ---------------------------------------------------------------------------
# Resume Header
# ---------------------------------------------------------------------------

@bp.route("/api/resume/header", methods=["GET"])
def get_resume_header():
    """Get resume header info (name, credentials, contact details)."""
    row = db.query_one("SELECT * FROM resume_header LIMIT 1")
    return jsonify(row or {"error": "No header data found"})


# ---------------------------------------------------------------------------
# Education
# ---------------------------------------------------------------------------

@bp.route("/api/education", methods=["GET"])
def get_education():
    """Get education entries."""
    rows = db.query("SELECT * FROM education ORDER BY sort_order")
    return jsonify({"education": rows, "count": len(rows)})


# ---------------------------------------------------------------------------
# Certifications
# ---------------------------------------------------------------------------

@bp.route("/api/certifications", methods=["GET"])
def get_certifications():
    """Get certification entries."""
    rows = db.query("SELECT * FROM certifications WHERE is_active = TRUE ORDER BY sort_order")
    return jsonify({"certifications": rows, "count": len(rows)})


# ---------------------------------------------------------------------------
# Resume Templates
# ---------------------------------------------------------------------------

@bp.route("/api/resume/templates", methods=["GET"])
def list_templates():
    """List available resume templates (without blob data)."""
    rows = db.query(
        "SELECT id, name, filename, description, is_active, length(template_blob) as size_bytes, created_at FROM resume_templates ORDER BY name"
    )
    return jsonify({"templates": rows, "count": len(rows)})


@bp.route("/api/resume/templates/<int:template_id>/download", methods=["GET"])
def download_template(template_id):
    """Download a resume template .docx file."""
    row = db.query_one(
        "SELECT filename, template_blob FROM resume_templates WHERE id = %s", (template_id,)
    )
    if not row:
        return jsonify({"error": "Template not found"}), 404
    return send_file(
        io.BytesIO(row["template_blob"]),
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        as_attachment=True,
        download_name=row["filename"],
    )


# ---------------------------------------------------------------------------
# Resume Versions & Specs
# ---------------------------------------------------------------------------

@bp.route("/api/resume/versions", methods=["GET"])
def list_resume_versions():
    """List resume versions with their specs."""
    rows = db.query(
        """SELECT id, version, variant, is_current, spec IS NOT NULL as has_spec,
                  docx_path, pdf_path, summary, target_role_type, created_at
           FROM resume_versions ORDER BY created_at DESC"""
    )
    return jsonify({"versions": rows, "count": len(rows)})


@bp.route("/api/resume/versions/<int:version_id>/spec", methods=["GET"])
def get_resume_spec(version_id):
    """Get the full spec for a resume version."""
    row = db.query_one("SELECT * FROM resume_versions WHERE id = %s", (version_id,))
    if not row:
        return jsonify({"error": "Version not found"}), 404
    return jsonify(row)


# ---------------------------------------------------------------------------
# Resume Data (full reconstruction data for a version)
# ---------------------------------------------------------------------------

@bp.route("/api/resume/data", methods=["GET"])
def get_resume_data():
    """Get all data needed to reconstruct a resume.

    Query params:
        version: resume version (default: v32)
        variant: resume variant (default: base)
        format: 'full' returns everything, 'spec_only' returns just the spec

    Returns header, education, certs, career history with bullets, spec, etc.
    """
    version = request.args.get("version", "v32")
    variant = request.args.get("variant", "base")
    fmt = request.args.get("format", "full")

    # Get the resume spec
    rv = db.query_one(
        "SELECT * FROM resume_versions WHERE version = %s AND variant = %s AND spec IS NOT NULL",
        (version, variant),
    )
    if not rv:
        return jsonify({"error": f"No spec found for {version}/{variant}"}), 404

    if fmt == "spec_only":
        return jsonify(rv)

    spec = rv["spec"] if isinstance(rv["spec"], dict) else json.loads(rv["spec"])

    # Get header
    header = db.query_one("SELECT * FROM resume_header LIMIT 1")

    # Get education
    education = db.query("SELECT * FROM education ORDER BY sort_order")

    # Get certifications
    certifications = db.query("SELECT * FROM certifications WHERE is_active = TRUE ORDER BY sort_order")

    # Get experience sections with bullets
    experience = []
    for employer_name in spec.get("experience_employers", []):
        ch = db.query_one(
            "SELECT * FROM career_history WHERE employer ILIKE %s",
            (f"%{employer_name}%",),
        )
        if ch:
            bullets = db.query(
                """SELECT id, text, type, tags, role_suitability, industry_suitability, metrics_json
                   FROM bullets WHERE career_history_id = %s ORDER BY id""",
                (ch["id"],),
            )
            ch["bullets"] = bullets
            experience.append(ch)

    return jsonify({
        "version": version,
        "variant": variant,
        "spec": spec,
        "header": header,
        "education": education,
        "certifications": certifications,
        "experience": experience,
        "template_available": db.query_one(
            "SELECT id, name FROM resume_templates WHERE is_active = TRUE LIMIT 1"
        ),
    })


# ---------------------------------------------------------------------------
# Resume Generation
# ---------------------------------------------------------------------------

PLACEHOLDER_RE = re.compile(r"\{\{([A-Z0-9_]+)\}\}")

BOLD_SEPARATORS = {
    "highlight": ": ",
    "job_bullet": ": ",
    "education": " | ",
    "certification": " | ",
    "additional_exp": " | ",
    "ref_link": " | ",
    "job_header": ", ",
}


def _fill_simple(paragraph, text):
    """Replace placeholder text, preserving first run formatting."""
    if paragraph.runs:
        paragraph.runs[0].text = text
        for run in paragraph.runs[1:]:
            run.text = ""
    else:
        paragraph.text = text


def _fill_bold_label(paragraph, text, separator=": "):
    """Replace with bold label + non-bold body, split at separator."""
    idx = text.find(separator)
    if idx < 0 or not paragraph.runs:
        _fill_simple(paragraph, text)
        return
    paragraph.runs[0].text = text[:idx]
    paragraph.runs[0].bold = True
    if len(paragraph.runs) > 1:
        paragraph.runs[1].text = text[idx:]
        paragraph.runs[1].bold = None  # inherit = not bold
        for run in paragraph.runs[2:]:
            run.text = ""
            run.bold = None
    else:
        paragraph.runs[0].text = text


def _build_content_map(spec, header, education, certifications, career, template_map):
    """Build placeholder_name -> content_text mapping."""
    content = {}

    # Seed from template_map original_text
    for slot in template_map.get("slots", []):
        placeholder = slot.get("placeholder")
        original = slot.get("original_text")
        if placeholder and original:
            content[placeholder] = original

    # Overlay with spec-derived content
    if header:
        content["HEADER_NAME"] = f"{header['full_name']}, {header['credentials']}"
        parts = [header["location"]]
        if header.get("location_note"):
            parts[0] += f" ({header['location_note']})"
        parts.append(header["email"])
        parts.append(header["phone"])
        if header.get("linkedin_url"):
            parts.append(header["linkedin_url"])
        content["HEADER_CONTACT"] = " \u2022 ".join(parts)

    if "headline" in spec:
        content["HEADLINE"] = spec["headline"]
    if "summary_text" in spec:
        content["SUMMARY"] = spec["summary_text"]

    for i, bullet in enumerate(spec.get("highlight_bullets", []), 1):
        content[f"HIGHLIGHT_{i}"] = bullet

    if "keywords" in spec:
        content["KEYWORDS"] = " | ".join(spec["keywords"])

    # Experience blocks
    employers = spec.get("experience_employers", [])
    exp_bullets = spec.get("experience_bullets", {})

    for job_n, emp_name in enumerate(employers, 1):
        emp_data = career.get(emp_name, {})
        bullets_raw = exp_bullets.get(emp_name, [])

        if emp_data.get("intro_text"):
            content[f"JOB_{job_n}_INTRO"] = emp_data["intro_text"]
        elif bullets_raw and len(bullets_raw[0]) > 200 and ": " not in bullets_raw[0][:80]:
            content[f"JOB_{job_n}_INTRO"] = bullets_raw[0]

        bullet_texts = []
        subtitle_texts = {content.get(f"JOB_{job_n}_SUBTITLE_1", ""),
                          content.get(f"JOB_{job_n}_SUBTITLE_2", "")}

        for b in bullets_raw:
            if b == content.get(f"JOB_{job_n}_INTRO"):
                continue
            if b in subtitle_texts:
                continue
            bullet_texts.append(b)

        for i, bt in enumerate(bullet_texts, 1):
            content[f"JOB_{job_n}_BULLET_{i}"] = bt

    if "executive_keywords" in spec:
        content["EXEC_KEYWORDS"] = " | ".join(spec["executive_keywords"])
    if "technical_keywords" in spec:
        content["TECH_KEYWORDS"] = " | ".join(spec["technical_keywords"])

    for i, ref_section in enumerate(spec.get("references", []), 1):
        for j, link in enumerate(ref_section.get("links", []), 1):
            content[f"REF_{i}_LINK_{j}"] = f"{link['text']} | {link['desc']}"

    return content


@bp.route("/api/resume/generate", methods=["POST"])
def generate_resume():
    """Generate a .docx resume from placeholder template + spec.

    POST body (JSON):
        version: resume version (default: v32)
        variant: resume variant (default: base)
        template_name: template to use (default: V32 Placeholder)
        overrides: optional dict of placeholder_name -> text overrides

    Returns: .docx file download
    """
    data = request.get_json(silent=True) or {}
    version = data.get("version", "v32")
    variant = data.get("variant", "base")
    template_name = data.get("template_name", "V32 Placeholder")
    overrides = data.get("overrides", {})

    # Load template
    tmpl = db.query_one(
        "SELECT template_blob, template_map FROM resume_templates WHERE name = %s AND is_active = TRUE",
        (template_name,),
    )
    if not tmpl:
        return jsonify({"error": f"Template '{template_name}' not found"}), 404

    template_blob = bytes(tmpl["template_blob"])
    template_map = tmpl["template_map"] or {}

    # Load spec
    rv = db.query_one(
        "SELECT spec FROM resume_versions WHERE version = %s AND variant = %s AND spec IS NOT NULL",
        (version, variant),
    )
    if not rv:
        return jsonify({"error": f"No spec found for {version}/{variant}"}), 404
    spec = rv["spec"] if isinstance(rv["spec"], dict) else json.loads(rv["spec"])

    # Load supporting data
    header = db.query_one("SELECT * FROM resume_header LIMIT 1")
    education = db.query("SELECT * FROM education ORDER BY sort_order")
    certifications = db.query(
        "SELECT * FROM certifications WHERE is_active = TRUE ORDER BY sort_order"
    )

    employers = spec.get("experience_employers", [])
    career = {}
    for emp in employers:
        ch = db.query_one(
            "SELECT * FROM career_history WHERE employer ILIKE %s ORDER BY start_date DESC LIMIT 1",
            (f"%{emp}%",),
        )
        if ch:
            career[emp] = ch

    # Build content map
    content_map = _build_content_map(spec, header, education, certifications, career, template_map)
    content_map.update(overrides)

    # Build slot info lookup
    slot_info = {}
    for slot in template_map.get("slots", []):
        if slot.get("placeholder"):
            slot_info[slot["placeholder"]] = {
                "slot_type": slot.get("slot_type", ""),
                "formatting": slot.get("formatting", {}),
            }

    # Fill template
    doc = Document(io.BytesIO(template_blob))
    filled = 0
    for para in doc.paragraphs:
        match = PLACEHOLDER_RE.search(para.text)
        if not match:
            continue
        placeholder = match.group(1)
        if placeholder not in content_map:
            _fill_simple(para, "")
            continue

        text = content_map[placeholder]
        info = slot_info.get(placeholder, {})
        slot_type = info.get("slot_type", "")
        formatting = info.get("formatting", {})

        if formatting.get("bold_label") and slot_type in BOLD_SEPARATORS:
            _fill_bold_label(para, text, BOLD_SEPARATORS[slot_type])
        else:
            _fill_simple(para, text)
        filled += 1

    # Return as downloadable .docx
    output = io.BytesIO()
    doc.save(output)
    output.seek(0)

    filename = f"resume_{version}_{variant}.docx"
    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        as_attachment=True,
        download_name=filename,
    )
