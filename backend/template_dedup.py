"""Template duplicate detection — exact hash match + AI-assisted near-duplicate detection.

Flow:
  1. Python: SHA-256 hash of blob → exact match
  2. AI (if enabled): compare template_map structure for near-duplicates
  3. Python fallback: if AI fails, skip near-duplicate check
"""

import hashlib
import json
import logging

import db
from ai_providers.router import route_inference

logger = logging.getLogger(__name__)


def compute_hash(blob: bytes) -> str:
    """SHA-256 hex digest of raw bytes."""
    return hashlib.sha256(blob).hexdigest()


def check_exact_duplicate(content_hash: str, template_type: str) -> dict | None:
    """Check for an exact duplicate by hash + type. Returns the existing row or None."""
    return db.query_one(
        """SELECT id, name, filename, template_type, is_active, created_at
             FROM resume_templates
            WHERE content_hash = %s AND template_type = %s""",
        (content_hash, template_type),
    )


def _extract_structure(template_blob: bytes) -> dict:
    """Extract structural fingerprint from a .docx template for comparison.

    Returns slot names, section order, paragraph count, and placeholder list.
    """
    try:
        import io
        from docx import Document
        import re

        doc = Document(io.BytesIO(template_blob))
        placeholder_re = re.compile(r"\{\{([A-Z0-9_]+)\}\}")
        placeholders = []
        para_count = 0
        for para in doc.paragraphs:
            para_count += 1
            match = placeholder_re.search(para.text)
            if match:
                placeholders.append(match.group(1))

        return {
            "paragraph_count": para_count,
            "placeholder_count": len(placeholders),
            "placeholders": placeholders,
        }
    except Exception as e:
        logger.warning(f"Template structure extraction failed: {e}")
        return {}


def _python_near_duplicate(context: dict) -> dict:
    """Python-only near-duplicate check using structural comparison.

    Compares placeholder lists between the new template and existing templates
    of the same type. If >80% of placeholders overlap, flags as near-duplicate.
    """
    new_struct = context["new_structure"]
    template_type = context["template_type"]
    new_placeholders = set(new_struct.get("placeholders", []))

    if not new_placeholders:
        return {"duplicates": [], "method": "python_structural"}

    # Get existing templates with template_map (they have parsed structure)
    existing = db.query(
        """SELECT id, name, filename, template_map
             FROM resume_templates
            WHERE template_type = %s AND template_map IS NOT NULL
            LIMIT 50""",
        (template_type,),
    )

    candidates = []
    for row in existing:
        tmap = row["template_map"]
        if isinstance(tmap, str):
            tmap = json.loads(tmap)
        if not tmap:
            continue

        # Extract placeholders from template_map
        existing_placeholders = set()
        if "slots" in tmap:
            for slot in tmap["slots"]:
                ph = slot.get("placeholder", "") or slot.get("name", "")
                if ph:
                    existing_placeholders.add(ph)
        else:
            existing_placeholders = set(tmap.keys())

        if not existing_placeholders:
            continue

        # Jaccard similarity
        intersection = new_placeholders & existing_placeholders
        union = new_placeholders | existing_placeholders
        similarity = len(intersection) / len(union) if union else 0

        if similarity >= 0.80:
            candidates.append({
                "id": row["id"],
                "name": row["name"],
                "filename": row["filename"],
                "similarity": round(similarity * 100, 1),
                "shared_slots": len(intersection),
                "total_slots": len(union),
            })

    candidates.sort(key=lambda c: c["similarity"], reverse=True)
    return {"duplicates": candidates[:5], "method": "python_structural"}


def _ai_near_duplicate(context: dict) -> dict:
    """AI-enhanced near-duplicate check — compares layout and content similarity."""
    from ai_providers import get_provider

    provider = get_provider()
    new_struct = context["new_structure"]
    template_type = context["template_type"]

    # Get top 10 existing templates with structure info
    existing = db.query(
        """SELECT id, name, filename, template_map
             FROM resume_templates
            WHERE template_type = %s AND template_map IS NOT NULL
            LIMIT 10""",
        (template_type,),
    )

    if not existing:
        return {"duplicates": [], "method": "ai"}

    existing_summaries = []
    for row in existing:
        tmap = row["template_map"]
        if isinstance(tmap, str):
            tmap = json.loads(tmap)
        slots = []
        if tmap and "slots" in tmap:
            slots = [s.get("placeholder", "") or s.get("name", "") for s in tmap["slots"]]
        elif tmap:
            slots = list(tmap.keys())
        existing_summaries.append({
            "id": row["id"],
            "name": row["name"],
            "filename": row["filename"],
            "slots": slots[:30],
        })

    prompt = f"""Compare this new resume template structure against existing templates and identify near-duplicates.

New template:
- Paragraphs: {new_struct.get('paragraph_count', 0)}
- Placeholders: {new_struct.get('placeholders', [])}

Existing templates:
{json.dumps(existing_summaries, indent=2)}

Return a JSON array of matches with similarity > 70%. Each match should have:
- "id": template ID
- "name": template name
- "similarity": percentage (0-100)
- "reason": brief explanation of why they're similar

Return empty array [] if no near-duplicates found.
Respond with ONLY the JSON array, no markdown fences."""

    response = provider.generate(prompt)
    try:
        # Parse AI response
        text = response.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        matches = json.loads(text)
        if not isinstance(matches, list):
            matches = []
        return {"duplicates": matches[:5], "method": "ai"}
    except (json.JSONDecodeError, Exception) as e:
        logger.warning(f"AI near-duplicate parsing failed: {e}")
        raise  # Let route_inference fall back to Python


def check_duplicates(blob: bytes, template_type: str, check_near: bool = True) -> dict:
    """Full duplicate detection pipeline.

    Returns:
        {
            "exact_match": {...} or None,
            "near_matches": [...] or [],
            "content_hash": "...",
            "analysis_mode": "rule_based" | "ai"
        }
    """
    content_hash = compute_hash(blob)

    # Step 1: Exact hash match (always Python)
    exact = check_exact_duplicate(content_hash, template_type)
    if exact:
        return {
            "exact_match": exact,
            "near_matches": [],
            "content_hash": content_hash,
            "analysis_mode": "rule_based",
        }

    # Step 2: Near-duplicate detection (AI-routed)
    near_matches = []
    analysis_mode = "rule_based"
    if check_near:
        new_structure = _extract_structure(blob)
        if new_structure.get("placeholders"):
            context = {
                "new_structure": new_structure,
                "template_type": template_type,
            }
            result = route_inference(
                task="template_near_duplicate_detection",
                context=context,
                python_fallback=_python_near_duplicate,
                ai_handler=_ai_near_duplicate,
            )
            near_matches = result.get("duplicates", [])
            analysis_mode = result.get("analysis_mode", "rule_based")

    return {
        "exact_match": None,
        "near_matches": near_matches,
        "content_hash": content_hash,
        "analysis_mode": analysis_mode,
    }
