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
