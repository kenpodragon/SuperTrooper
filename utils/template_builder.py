"""Template builder — converts a parsed resume into a placeholder .docx template + map JSON.

Takes a .docx resume, parses it with resume_parser, replaces content with {{SLOT_NAME}}
placeholders while preserving formatting, and outputs a template .docx + template_map.json.
"""

import json
from pathlib import Path

from docx import Document

from utils.resume_parser import parse_resume_structure


def _generate_slot_names(sections: list[dict]) -> list[dict]:
    """Generate unique slot names for each parsed section.

    Returns sections augmented with 'slot_name' key (None for section_headers).
    """
    counters = {
        'header_contact': 0,
        'headline': 0,
        'summary': 0,
        'highlight': 0,
        'job': 0,
        'job_bullet': {},  # job_num -> bullet_count
        'job_intro': {},   # job_num -> intro_count
        'job_subheading': {},  # job_num -> subheading_count (for dup matches)
        'education': 0,
        'certification': 0,
        'skills': 0,
        'keywords': 0,
        'additional': 0,
        'unknown': 0,
    }

    current_job = 0
    header_name_assigned = False
    results = []

    for section in sections:
        sec_type = section['type']
        slot_name = None

        if sec_type == 'section_header':
            # Skip — no placeholder for section headers
            slot_name = None

        elif sec_type == 'header':
            if not header_name_assigned:
                slot_name = 'HEADER_NAME'
                header_name_assigned = True
            else:
                counters['header_contact'] += 1
                slot_name = f"HEADER_CONTACT_{counters['header_contact']}"

        elif sec_type == 'headline':
            counters['headline'] += 1
            slot_name = 'HEADLINE' if counters['headline'] == 1 else f"HEADLINE_{counters['headline']}"

        elif sec_type == 'summary':
            counters['summary'] += 1
            slot_name = 'SUMMARY' if counters['summary'] == 1 else f"SUMMARY_{counters['summary']}"

        elif sec_type == 'highlights':
            counters['highlight'] += 1
            slot_name = f"HIGHLIGHT_{counters['highlight']}"

        elif sec_type == 'job_header':
            current_job += 1
            counters['job_bullet'][current_job] = 0
            counters['job_intro'][current_job] = 0
            slot_name = f"JOB_{current_job}_HEADER"

        elif sec_type == 'job_subheading':
            # Visual sibling-role marker. Fuzzy-match against prior JOB_N_HEADER
            # texts (most-recent first). On match, switch current_job so following
            # bullets route to the matched role. No match → new role under current
            # employer (increment current_job).
            text_lower = section.get('text', '').lower()
            matched_job = None
            for prior in reversed(results):
                prior_slot = prior.get('slot_name') or ''
                if prior_slot.startswith('JOB_') and prior_slot.endswith('_HEADER'):
                    prior_title_word = prior.get('text', '').split(',')[0].strip().lower()
                    if prior_title_word and len(prior_title_word) > 3 and prior_title_word in text_lower:
                        try:
                            matched_job = int(prior_slot.split('_')[1])
                        except (IndexError, ValueError):
                            matched_job = None
                        break
            if matched_job is not None:
                current_job = matched_job
            else:
                current_job += 1
                counters['job_bullet'].setdefault(current_job, 0)
                counters['job_intro'].setdefault(current_job, 0)
            counters['job_subheading'].setdefault(current_job, 0)
            counters['job_subheading'][current_job] += 1
            n = counters['job_subheading'][current_job]
            slot_name = (
                f"JOB_{current_job}_SUBHEADING"
                if n == 1
                else f"JOB_{current_job}_SUBHEADING_{n}"
            )

        elif sec_type == 'job_intro':
            # Associate with current job
            job_num = max(current_job, 1)
            if job_num not in counters['job_intro']:
                counters['job_intro'][job_num] = 0
            counters['job_intro'][job_num] += 1
            intro_num = counters['job_intro'][job_num]
            slot_name = f"JOB_{job_num}_INTRO" if intro_num == 1 else f"JOB_{job_num}_INTRO_{intro_num}"

        elif sec_type == 'bullet':
            job_num = max(current_job, 1)
            if job_num not in counters['job_bullet']:
                counters['job_bullet'][job_num] = 0
            counters['job_bullet'][job_num] += 1
            slot_name = f"JOB_{job_num}_BULLET_{counters['job_bullet'][job_num]}"

        elif sec_type == 'education':
            counters['education'] += 1
            slot_name = f"EDUCATION_{counters['education']}"

        elif sec_type == 'certification':
            counters['certification'] += 1
            slot_name = f"CERT_{counters['certification']}"

        elif sec_type == 'skills':
            counters['skills'] += 1
            slot_name = f"SKILLS_{counters['skills']}"

        elif sec_type == 'keywords':
            counters['keywords'] += 1
            slot_name = f"KEYWORDS_{counters['keywords']}"

        elif sec_type == 'additional':
            counters['additional'] += 1
            slot_name = f"ADDL_EXP_{counters['additional']}"

        else:
            counters['unknown'] += 1
            slot_name = f"SLOT_{counters['unknown']}"

        results.append({**section, 'slot_name': slot_name})

    return results


def build_template(
    input_path: str,
    output_docx: str,
    output_map: str,
    layout: str = "auto",
) -> dict:
    """Build a placeholder .docx template from a resume.

    Args:
        input_path: Path to source .docx resume.
        output_docx: Path to write the placeholder template .docx.
        output_map: Path to write the template_map JSON.
        layout: Layout mode (default "auto").

    Returns:
        Dict with slot_count, sections_detected, and layout.
    """
    # 1. Parse the resume structure
    sections = parse_resume_structure(input_path)

    # 2. Generate slot names
    slotted = _generate_slot_names(sections)

    # 3. Build template_map (only for slots that have names)
    template_map = {}
    for item in slotted:
        if item['slot_name'] is not None:
            template_map[item['slot_name']] = {
                'type': item['type'],
                'original_text': item['text'],
                'formatting': item['formatting'],
                'parent_section': item['parent_section'],
            }

    # 4. Build paragraph_index -> slot_name lookup
    index_to_slot = {}
    for item in slotted:
        if item['slot_name'] is not None:
            index_to_slot[item['paragraph_index']] = item['slot_name']

    # 5. Open original doc and replace content with placeholders
    doc = Document(input_path)
    for i, paragraph in enumerate(doc.paragraphs):
        if i not in index_to_slot:
            continue

        slot_name = index_to_slot[i]
        placeholder = "{{" + slot_name + "}}"

        runs = paragraph.runs
        if not runs:
            # No runs — set paragraph text directly
            paragraph.text = placeholder
            continue

        # Preserve first run's formatting, set its text to placeholder
        runs[0].text = placeholder

        # Clear remaining runs
        for run in runs[1:]:
            run.text = ""

    # 6. Ensure output directories exist
    Path(output_docx).parent.mkdir(parents=True, exist_ok=True)
    Path(output_map).parent.mkdir(parents=True, exist_ok=True)

    # 7. Save outputs
    doc.save(output_docx)

    with open(output_map, 'w', encoding='utf-8') as f:
        json.dump(template_map, f, indent=2, default=str)

    # 8. Compute summary
    sections_detected = sorted(set(item['parent_section'] for item in slotted if item['parent_section']))

    return {
        'slot_count': len(template_map),
        'sections_detected': sections_detected,
        'layout': layout,
    }


# ---------------------------------------------------------------------------
# Section-based template map
# ---------------------------------------------------------------------------

_TYPE_TO_SECTION = {
    "header": "HEADER",
    "headline": "HEADLINE",
    "summary": "SUMMARY",
    "highlight": "HIGHLIGHTS",
    "job_header": "EXPERIENCE",
    "job_title": "EXPERIENCE",
    "job_intro": "EXPERIENCE",
    "job_bullet": "EXPERIENCE",
    "job_subtitle": "EXPERIENCE",
    "job_subheading": "EXPERIENCE",
    "education": "EDUCATION",
    "certification": "CERTIFICATIONS",
    "skills": "SKILLS",
    "keywords": "KEYWORDS",
    "additional_exp": "ADDITIONAL_EXP",
    "ref_link": "REF_LINKS",
}

_SINGULAR_SECTIONS = {"HEADER", "HEADLINE", "SUMMARY"}

_HEADER_TEXT_MAP = {
    "professional experience": "EXPERIENCE",
    "experience": "EXPERIENCE",
    "work experience": "EXPERIENCE",
    "certifications": "CERTIFICATIONS",
    "certification": "CERTIFICATIONS",
    "education": "EDUCATION",
    "skills": "SKILLS",
    "technical skills": "SKILLS",
    "core competencies": "SKILLS",
    "key skills": "SKILLS",
    "highlights": "HIGHLIGHTS",
    "key achievements": "HIGHLIGHTS",
    "career highlights": "HIGHLIGHTS",
    "additional experience": "ADDITIONAL_EXP",
    "keywords": "KEYWORDS",
}

_SECTION_FORMATS = {
    "HEADER": {"format": "header"},
    "HEADLINE": {"format": "simple"},
    "SUMMARY": {"format": "simple"},
    "HIGHLIGHTS": {"format": "bold_label", "separator": ": "},
    "EXPERIENCE": {
        "format": "job_block",
        "sub_sections": {
            "header": {"format": "bold_label", "separator": ", "},
            "title": {"format": "simple"},
            "synopsis": {"format": "simple"},
            "bullets": {"repeating": True, "format": "bold_label", "separator": ": "},
        },
    },
    "EDUCATION": {"format": "bold_label", "separator": " | "},
    "CERTIFICATIONS": {"format": "bold_label", "separator": " | "},
    "SKILLS": {"format": "simple"},
    "KEYWORDS": {"format": "simple"},
    "ADDITIONAL_EXP": {"format": "simple"},
    "REF_LINKS": {"format": "simple"},
}


def build_section_map(parsed_sections: list[dict]) -> dict:
    """Build a section-level template map from parsed resume sections.

    Groups individual parsed items by section type. The first occurrence of
    each section type defines the prototype entry in the map.

    Args:
        parsed_sections: List of dicts with keys 'type', 'text', 'para_index',
            as returned by parse_resume_structure().

    Returns:
        Dict mapping section names (e.g. "CERTIFICATIONS") to their metadata
        dicts, including repeating flag, para_index, format, and optionally
        section_header_para.
    """
    section_map = {}
    last_section_header = None
    last_section_header_idx = None

    for item in parsed_sections:
        sec_type = item["type"]
        para_idx = item.get("para_index", 0)

        if sec_type == "section_header":
            header_text = item.get("text", "").strip().lower().rstrip(":")
            last_section_header = _HEADER_TEXT_MAP.get(header_text)
            last_section_header_idx = para_idx
            continue

        section_name = _TYPE_TO_SECTION.get(sec_type)
        if not section_name:
            continue

        # First occurrence defines the prototype
        if section_name not in section_map:
            is_repeating = section_name not in _SINGULAR_SECTIONS
            entry = {
                "repeating": is_repeating,
                "para_index": para_idx,
                **_SECTION_FORMATS.get(section_name, {"format": "simple"}),
            }
            if last_section_header == section_name and last_section_header_idx is not None:
                entry["section_header_para"] = last_section_header_idx
            section_map[section_name] = entry

    return section_map
