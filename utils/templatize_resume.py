"""Convert a full .docx resume into a placeholder template with generic job blocks.

Reads the V32 resume, replaces all content paragraphs with named placeholders,
and outputs both:
  1. A .docx template file with placeholder text
  2. A JSON template_map describing each slot's name, type, formatting rules,
     and position

The template uses generic numbered job blocks (JOB_1, JOB_2, etc.) so any
employer data can fill any slot. This is the foundation for the future
drag-and-drop template editor.

Usage:
    python templatize_resume.py --input Originals/Stephen_Salaka_Resume_v32.docx \
        --output-docx Output/template_v32_placeholder.docx \
        --output-map Output/template_v32_map.json

Dependencies:
    pip install python-docx
"""

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Optional

from docx import Document
from docx.shared import Pt


# -- V32 layout definition --------------------------------------------------
# This defines the semantic meaning of each paragraph in the V32 layout.
# The templatizer uses this to assign placeholder names.

V32_LAYOUT = [
    # (para_index, placeholder_name, slot_type, formatting_rules)
    (0,  "HEADER_NAME",          "header",    {"bold": True, "size_pt": 23}),
    (1,  "HEADER_CONTACT",       "header",    {"size_pt": 10}),
    (2,  None,                   "spacer",    {}),
    (3,  "HEADLINE",             "headline",  {"bold": True, "size_pt": 15}),
    (4,  None,                   "spacer",    {}),
    (5,  "SUMMARY",              "summary",   {"size_pt": 10}),
    (6,  "HIGHLIGHT_1",          "highlight", {"bold_label": True, "size_pt": 10}),
    (7,  "HIGHLIGHT_2",          "highlight", {"bold_label": True, "size_pt": 10}),
    (8,  "HIGHLIGHT_3",          "highlight", {"bold_label": True, "size_pt": 10}),
    (9,  "HIGHLIGHT_4",          "highlight", {"bold_label": True, "size_pt": 10}),
    (10, "HIGHLIGHT_5",          "highlight", {"bold_label": True, "size_pt": 10}),
    (11, "KEYWORDS",             "keywords",  {"size_pt": 10}),
    (12, None,                   "spacer",    {}),
    (13, None,                   "section_header", {"bold": True, "size_pt": 12, "static_text": "Professional Experience"}),
    (14, None,                   "spacer",    {}),

    # --- Job Block 1 (MealMatch AI in V32) ---
    (15, "JOB_1_HEADER",         "job_header",  {"bold_label": True, "size_pt": 10}),
    (16, "JOB_1_TITLE",          "job_title",   {"bold": True, "size_pt": 10}),
    (17, "JOB_1_INTRO",          "job_intro",   {"size_pt": 10}),
    (18, "JOB_1_BULLET_1",       "job_bullet",  {"bold_label": True, "size_pt": 10, "style": "List Paragraph"}),
    (19, "JOB_1_BULLET_2",       "job_bullet",  {"bold_label": True, "size_pt": 10, "style": "List Paragraph"}),
    (20, "JOB_1_BULLET_3",       "job_bullet",  {"bold_label": True, "size_pt": 10, "style": "List Paragraph"}),
    (21, "JOB_1_BULLET_4",       "job_bullet",  {"bold_label": True, "size_pt": 10, "style": "List Paragraph"}),
    (22, "JOB_1_BULLET_5",       "job_bullet",  {"bold_label": True, "size_pt": 10, "style": "List Paragraph"}),

    # --- Job Block 2 (SMTC in V32) ---
    (23, "JOB_2_HEADER",         "job_header",  {"bold_label": True, "size_pt": 10}),
    (24, "JOB_2_TITLE",          "job_title",   {"bold": True, "size_pt": 10}),
    (25, "JOB_2_INTRO",          "job_intro",   {"size_pt": 10}),
    (26, "JOB_2_BULLET_1",       "job_bullet",  {"bold_label": True, "size_pt": 10, "style": "List Paragraph"}),
    (27, "JOB_2_BULLET_2",       "job_bullet",  {"bold_label": True, "size_pt": 10, "style": "List Paragraph"}),
    (28, "JOB_2_BULLET_3",       "job_bullet",  {"bold_label": True, "size_pt": 10, "style": "List Paragraph"}),
    (29, "JOB_2_BULLET_4",       "job_bullet",  {"bold_label": True, "size_pt": 10, "style": "List Paragraph"}),
    (30, "JOB_2_BULLET_5",       "job_bullet",  {"bold_label": True, "size_pt": 10, "style": "List Paragraph"}),
    (31, "JOB_2_BULLET_6",       "job_bullet",  {"bold_label": True, "size_pt": 10, "style": "List Paragraph"}),

    # --- Job Block 3 (Tsunami in V32 — has sub-roles) ---
    (32, "JOB_3_HEADER",         "job_header",  {"bold_label": True, "size_pt": 10}),
    (33, "JOB_3_TITLE_1",        "job_title",   {"bold_label": True, "size_pt": 10}),
    (34, "JOB_3_TITLE_2",        "job_title",   {"bold_label": True, "size_pt": 10}),
    (35, "JOB_3_INTRO",          "job_intro",   {"size_pt": 10}),
    (36, "JOB_3_SUBTITLE_1",     "job_subtitle", {"bold": True, "size_pt": 10}),
    (37, "JOB_3_BULLET_1",       "job_bullet",  {"bold_label": True, "size_pt": 10, "style": "List Paragraph"}),
    (38, "JOB_3_BULLET_2",       "job_bullet",  {"bold_label": True, "size_pt": 10, "style": "List Paragraph"}),
    (39, "JOB_3_BULLET_3",       "job_bullet",  {"bold_label": True, "size_pt": 10, "style": "List Paragraph"}),
    (40, "JOB_3_SUBTITLE_2",     "job_subtitle", {"bold": True, "size_pt": 10}),
    (41, "JOB_3_BULLET_4",       "job_bullet",  {"bold_label": True, "size_pt": 10, "style": "List Paragraph"}),
    (42, "JOB_3_BULLET_5",       "job_bullet",  {"bold_label": True, "size_pt": 10, "style": "List Paragraph"}),

    # --- Job Block 4 (Atex in V32) ---
    (43, "JOB_4_HEADER",         "job_header",  {"bold_label": True, "size_pt": 10}),
    (44, "JOB_4_TITLE",          "job_title",   {"bold": True, "size_pt": 10}),
    (45, "JOB_4_INTRO",          "job_intro",   {"size_pt": 10}),
    (46, "JOB_4_BULLET_1",       "job_bullet",  {"bold_label": True, "size_pt": 10, "style": "List Paragraph"}),
    (47, "JOB_4_BULLET_2",       "job_bullet",  {"bold_label": True, "size_pt": 10, "style": "List Paragraph"}),
    (48, "JOB_4_BULLET_3",       "job_bullet",  {"bold_label": True, "size_pt": 10, "style": "List Paragraph"}),
    (49, "JOB_4_BULLET_4",       "job_bullet",  {"bold_label": True, "size_pt": 10, "style": "List Paragraph"}),

    # --- Additional Experience ---
    (50, None,                   "section_header", {"bold": True, "size_pt": 12, "static_text": "Additional Work Experience"}),
    (51, "ADDL_EXP_1",           "additional_exp", {"bold_label": True, "size_pt": 10}),
    (52, "ADDL_EXP_2",           "additional_exp", {"bold_label": True, "size_pt": 10}),
    (53, "ADDL_EXP_3",           "additional_exp", {"bold_label": True, "size_pt": 10}),
    (54, "ADDL_EXP_4",           "additional_exp", {"bold_label": True, "size_pt": 10}),
    (55, "ADDL_EXP_5",           "additional_exp", {"bold_label": True, "size_pt": 10}),
    (56, "ADDL_EXP_6",           "additional_exp", {"bold_label": True, "size_pt": 10}),
    (57, "ADDL_EXP_7",           "additional_exp", {"bold_label": True, "size_pt": 10}),
    (58, "ADDL_EXP_8",           "additional_exp", {"bold_label": True, "size_pt": 10}),

    # --- Education ---
    (59, None,                   "section_header", {"bold": True, "size_pt": 12, "static_text": "Education & Professional Development"}),
    (60, "EDUCATION_1",          "education",  {"bold_label": True, "size_pt": 10}),
    (61, "EDUCATION_2",          "education",  {"bold_label": True, "size_pt": 10}),
    (62, "EDUCATION_3",          "education",  {"bold_label": True, "size_pt": 10}),
    (63, "EDUCATION_4",          "education",  {"bold_label": True, "size_pt": 10}),

    # --- Certifications ---
    (64, None,                   "section_header", {"bold": True, "size_pt": 12, "static_text": "Certifications"}),
    (65, "CERT_1",               "certification", {"bold_label": True, "size_pt": 10}),
    (66, "CERT_2",               "certification", {"bold_label": True, "size_pt": 10}),
    (67, "CERT_3",               "certification", {"bold_label": True, "size_pt": 10}),
    (68, "CERT_4",               "certification", {"bold_label": True, "size_pt": 10}),
    (69, "CERT_5",               "certification", {"bold_label": True, "size_pt": 10}),
    (70, "CERT_6",               "certification", {"bold_label": True, "size_pt": 10}),
    (71, "CERT_7",               "certification", {"bold_label": True, "size_pt": 10}),
    (72, "CERT_8",               "certification", {"bold_label": True, "size_pt": 10}),

    # --- Executive Keywords ---
    (73, None,                   "section_header", {"bold": True, "size_pt": 12, "static_text": "Executive Leadership"}),
    (74, "EXEC_KEYWORDS",        "keywords",  {"size_pt": 10}),

    # --- Technical Keywords ---
    (75, None,                   "section_header", {"bold": True, "size_pt": 12, "static_text": "Technical Expertise"}),
    (76, "TECH_KEYWORDS",        "keywords",  {"size_pt": 10}),

    # --- Spacer ---
    (77, None,                   "spacer",    {}),

    # --- References ---
    (78, None,                   "section_header", {"bold": True, "size_pt": 12, "static_text": "References"}),
    (79, "REF_SECTION_1_HEADER", "ref_header", {"bold": True, "size_pt": 10}),
    (80, "REF_1_LINK_1",         "ref_link",  {"bold_label": True, "size_pt": 10}),
    (81, "REF_1_LINK_2",         "ref_link",  {"bold_label": True, "size_pt": 10}),
    (82, "REF_SECTION_2_HEADER", "ref_header", {"bold": True, "size_pt": 10}),
    (83, "REF_2_LINK_1",         "ref_link",  {"bold_label": True, "size_pt": 10}),
    (84, "REF_2_LINK_2",         "ref_link",  {"bold_label": True, "size_pt": 10}),
    (85, "REF_2_LINK_3",         "ref_link",  {"bold_label": True, "size_pt": 10}),
    (86, "REF_SECTION_3_HEADER", "ref_header", {"bold": True, "size_pt": 10}),
    (87, "REF_3_LINK_1",         "ref_link",  {"bold_label": True, "size_pt": 10}),
    (88, "REF_3_LINK_2",         "ref_link",  {"bold_label": True, "size_pt": 10}),
    (89, "REF_SECTION_4_HEADER", "ref_header", {"bold": True, "size_pt": 10}),
    (90, "REF_4_LINK_1",         "ref_link",  {"bold_label": True, "size_pt": 10}),

    # --- Trailing spacers ---
    (91, None,                   "spacer",    {}),
    (92, None,                   "spacer",    {}),
]


V31_LAYOUT = [
    (0,  "HEADER_NAME",          "header",    {"bold": True, "size_pt": 23}),
    (1,  "HEADER_CONTACT",       "header",    {"size_pt": 10}),
    (2,  None,                   "spacer",    {}),
    (3,  "HEADLINE",             "headline",  {"bold": True, "size_pt": 15}),
    (4,  None,                   "spacer",    {}),
    (5,  "SUMMARY",              "summary",   {"size_pt": 10}),
    (6,  "HIGHLIGHT_1",          "highlight", {"bold_label": True, "size_pt": 10}),
    (7,  "HIGHLIGHT_2",          "highlight", {"bold_label": True, "size_pt": 10}),
    (8,  "HIGHLIGHT_3",          "highlight", {"bold_label": True, "size_pt": 10}),
    (9,  "HIGHLIGHT_4",          "highlight", {"bold_label": True, "size_pt": 10}),
    (10, "HIGHLIGHT_5",          "highlight", {"bold_label": True, "size_pt": 10}),
    (11, "KEYWORDS_1",           "keywords",  {"size_pt": 10}),
    (12, "KEYWORDS_2",           "keywords",  {"size_pt": 10}),
    (13, "KEYWORDS_3",           "keywords",  {"size_pt": 10}),
    (14, None,                   "section_header", {"bold": True, "size_pt": 12, "static_text": "Professional Experience"}),
    (15, None,                   "spacer",    {}),

    # --- Job Block 1 (MealMatch AI) ---
    (16, "JOB_1_HEADER",         "job_header",  {"bold_label": True, "size_pt": 10}),
    (17, "JOB_1_TITLE",          "job_title",   {"bold": True, "size_pt": 10}),
    (18, "JOB_1_INTRO",          "job_intro",   {"size_pt": 10}),
    (19, "JOB_1_BULLET_1",       "job_bullet",  {"bold_label": True, "size_pt": 10, "style": "List Paragraph"}),
    (20, "JOB_1_BULLET_2",       "job_bullet",  {"bold_label": True, "size_pt": 10, "style": "List Paragraph"}),
    (21, "JOB_1_BULLET_3",       "job_bullet",  {"bold_label": True, "size_pt": 10, "style": "List Paragraph"}),
    (22, "JOB_1_BULLET_4",       "job_bullet",  {"bold_label": True, "size_pt": 10, "style": "List Paragraph"}),
    (23, "JOB_1_BULLET_5",       "job_bullet",  {"bold_label": True, "size_pt": 10, "style": "List Paragraph"}),

    # --- Job Block 2 (SMTC) ---
    (24, "JOB_2_HEADER",         "job_header",  {"bold_label": True, "size_pt": 10}),
    (25, "JOB_2_TITLE",          "job_title",   {"bold": True, "size_pt": 10}),
    (26, "JOB_2_INTRO",          "job_intro",   {"size_pt": 10}),
    (27, "JOB_2_BULLET_1",       "job_bullet",  {"bold_label": True, "size_pt": 10, "style": "List Paragraph"}),
    (28, "JOB_2_BULLET_2",       "job_bullet",  {"bold_label": True, "size_pt": 10, "style": "List Paragraph"}),
    (29, "JOB_2_BULLET_3",       "job_bullet",  {"bold_label": True, "size_pt": 10, "style": "List Paragraph"}),
    (30, "JOB_2_BULLET_4",       "job_bullet",  {"bold_label": True, "size_pt": 10, "style": "List Paragraph"}),
    (31, "JOB_2_BULLET_5",       "job_bullet",  {"bold_label": True, "size_pt": 10, "style": "List Paragraph"}),
    (32, "JOB_2_BULLET_6",       "job_bullet",  {"bold_label": True, "size_pt": 10, "style": "List Paragraph"}),
    (33, "JOB_2_BULLET_7",       "job_bullet",  {"bold_label": True, "size_pt": 10, "style": "List Paragraph"}),
    (34, "JOB_2_BULLET_8",       "job_bullet",  {"bold_label": True, "size_pt": 10, "style": "List Paragraph"}),

    # --- Job Block 3 (Tsunami — has sub-roles) ---
    (35, "JOB_3_HEADER",         "job_header",  {"bold_label": True, "size_pt": 10}),
    (36, "JOB_3_TITLE_1",        "job_title",   {"bold_label": True, "size_pt": 10}),
    (37, "JOB_3_INTRO",          "job_intro",   {"size_pt": 10}),
    (38, "JOB_3_BULLET_1",       "job_bullet",  {"bold_label": True, "size_pt": 10, "style": "List Paragraph"}),
    (39, "JOB_3_BULLET_2",       "job_bullet",  {"bold_label": True, "size_pt": 10, "style": "List Paragraph"}),
    (40, "JOB_3_BULLET_3",       "job_bullet",  {"bold_label": True, "size_pt": 10, "style": "List Paragraph"}),
    (41, "JOB_3_BULLET_4",       "job_bullet",  {"bold_label": True, "size_pt": 10, "style": "List Paragraph"}),
    (42, "JOB_3_BULLET_5",       "job_bullet",  {"bold_label": True, "size_pt": 10, "style": "List Paragraph"}),
    (43, "JOB_3_BULLET_6",       "job_bullet",  {"bold_label": True, "size_pt": 10, "style": "List Paragraph"}),
    (44, "JOB_3_BULLET_7",       "job_bullet",  {"bold_label": True, "size_pt": 10, "style": "List Paragraph"}),
    (45, "JOB_3_TITLE_2",        "job_title",   {"bold_label": True, "size_pt": 10}),
    (46, "JOB_3_INTRO_2",        "job_intro",   {"size_pt": 10}),
    (47, "JOB_3_BULLET_8",       "job_bullet",  {"bold_label": True, "size_pt": 10, "style": "List Paragraph"}),
    (48, "JOB_3_BULLET_9",       "job_bullet",  {"bold_label": True, "size_pt": 10, "style": "List Paragraph"}),

    # --- Job Block 4 (Live Music Tutor) ---
    (49, "JOB_4_HEADER",         "job_header",  {"bold_label": True, "size_pt": 10}),
    (50, "JOB_4_TITLE",          "job_title",   {"bold": True, "size_pt": 10}),
    (51, "JOB_4_INTRO",          "job_intro",   {"size_pt": 10}),
    (52, "JOB_4_BULLET_1",       "job_bullet",  {"bold_label": True, "size_pt": 10, "style": "List Paragraph"}),
    (53, "JOB_4_BULLET_2",       "job_bullet",  {"bold_label": True, "size_pt": 10, "style": "List Paragraph"}),
    (54, "JOB_4_BULLET_3",       "job_bullet",  {"bold_label": True, "size_pt": 10, "style": "List Paragraph"}),
    (55, "JOB_4_BULLET_4",       "job_bullet",  {"bold_label": True, "size_pt": 10, "style": "List Paragraph"}),
    (56, "JOB_4_BULLET_5",       "job_bullet",  {"bold_label": True, "size_pt": 10, "style": "List Paragraph"}),
    (57, "JOB_4_BULLET_6",       "job_bullet",  {"bold_label": True, "size_pt": 10, "style": "List Paragraph"}),
    (58, "JOB_4_BULLET_7",       "job_bullet",  {"bold_label": True, "size_pt": 10, "style": "List Paragraph"}),
    (59, "JOB_4_BULLET_8",       "job_bullet",  {"bold_label": True, "size_pt": 10, "style": "List Paragraph"}),

    # --- Additional Experience ---
    (60, None,                   "section_header", {"bold": True, "size_pt": 12, "static_text": "Additional Work Experience"}),
    (61, "ADDL_EXP_1",           "additional_exp", {"bold_label": True, "size_pt": 10}),
    (62, "ADDL_EXP_2",           "additional_exp", {"bold_label": True, "size_pt": 10}),
    (63, "ADDL_EXP_3",           "additional_exp", {"bold_label": True, "size_pt": 10}),
    (64, "ADDL_EXP_4",           "additional_exp", {"bold_label": True, "size_pt": 10}),
    (65, "ADDL_EXP_5",           "additional_exp", {"bold_label": True, "size_pt": 10}),

    # --- Education ---
    (66, None,                   "section_header", {"bold": True, "size_pt": 12, "static_text": "Education & Professional Development"}),
    (67, "EDUCATION_1",          "education",  {"bold_label": True, "size_pt": 10}),
    (68, "EDUCATION_2",          "education",  {"bold_label": True, "size_pt": 10}),
    (69, "EDUCATION_3",          "education",  {"bold_label": True, "size_pt": 10}),
    (70, "EDUCATION_4",          "education",  {"bold_label": True, "size_pt": 10}),

    # --- Certifications ---
    (71, None,                   "section_header", {"bold": True, "size_pt": 12, "static_text": "Certifications"}),
    (72, "CERT_1",               "certification", {"bold_label": True, "size_pt": 10}),
    (73, "CERT_2",               "certification", {"bold_label": True, "size_pt": 10}),
    (74, "CERT_3",               "certification", {"bold_label": True, "size_pt": 10}),
    (75, "CERT_4",               "certification", {"bold_label": True, "size_pt": 10}),
    (76, "CERT_5",               "certification", {"bold_label": True, "size_pt": 10}),
    (77, "CERT_6",               "certification", {"bold_label": True, "size_pt": 10}),
    (78, "CERT_7",               "certification", {"bold_label": True, "size_pt": 10}),
    (79, "CERT_8",               "certification", {"bold_label": True, "size_pt": 10}),

    # --- Technical Skills ---
    (80, None,                   "section_header", {"bold": True, "size_pt": 12, "static_text": "Technical Skills"}),
    (81, "TECH_SKILLS",          "keywords",  {"size_pt": 10}),

    # --- Other Skills ---
    (82, None,                   "section_header", {"bold": True, "size_pt": 12, "static_text": "Other Skills"}),
    (83, "OTHER_SKILLS_1",       "keywords",  {"size_pt": 10}),
    (84, "OTHER_SKILLS_2",       "keywords",  {"size_pt": 10}),
    (85, "OTHER_SKILLS_3",       "keywords",  {"size_pt": 10}),

    # --- Trailing spacer ---
    (86, None,                   "spacer",    {}),
]


LAYOUTS = {
    "v32": V32_LAYOUT,
    "v31": V31_LAYOUT,
}


def _set_placeholder(paragraph, placeholder_name: str) -> None:
    """Replace paragraph content with a placeholder marker, preserving formatting.

    Preserves:
    - Hyperlink elements (for references section) — clears their text but keeps XML
    - VML shapes / drawings (for keyword bubble, headline banner) — untouched
    - Run formatting (bold, font, size) — only text is changed
    """
    from lxml import etree

    marker = "{{" + placeholder_name + "}}"
    nsmap = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}

    # Clear hyperlink text but KEEP the hyperlink elements (preserves URLs)
    for hyperlink in paragraph._element.findall(".//w:hyperlink", nsmap):
        for run in hyperlink.findall(".//w:r", nsmap):
            t = run.find("w:t", nsmap)
            if t is not None:
                t.text = ""

    # Find the first text-bearing run (skip runs with drawings/shapes)
    mc_ns = "http://schemas.openxmlformats.org/markup-compatibility/2006"
    pict_ns = nsmap["w"]
    first_text_run = None
    for run in paragraph.runs:
        # Skip runs containing VML shapes or drawings
        has_shape = (
            run._element.find(f"{{{mc_ns}}}AlternateContent") is not None
            or run._element.find(f"{{{pict_ns}}}pict") is not None
            or run._element.find(f"{{{pict_ns}}}drawing") is not None
        )
        if has_shape:
            continue
        if first_text_run is None:
            first_text_run = run
            run.text = marker
        else:
            run.text = ""

    if first_text_run is None:
        # No text runs found (all runs have shapes), fall back
        if paragraph.runs:
            paragraph.runs[0].text = marker
        else:
            paragraph.text = marker


def _legacy_templatize(input_path: str, output_docx: str, output_map: str, layout_name: str = "v32") -> dict:
    """Convert a full resume .docx into a placeholder template.

    Args:
        input_path: Path to the full resume .docx.
        output_docx: Path to save the placeholder template .docx.
        output_map: Path to save the template map JSON.

    Returns:
        The template map dictionary.
    """
    doc = Document(input_path)
    paras = doc.paragraphs

    layout = LAYOUTS.get(layout_name)
    if not layout:
        raise ValueError(f"Unknown layout: {layout_name}. Available: {list(LAYOUTS.keys())}")

    if len(paras) != len(layout):
        print(f"Warning: expected {len(layout)} paragraphs, found {len(paras)}", file=sys.stderr)

    template_map = {
        "version": layout_name,
        "total_paragraphs": len(paras),
        "slots": [],
        "formatting_rules": {
            "bold_label": "First run is bold (the label before the colon), remaining runs are normal weight",
            "bold": "Entire paragraph is bold",
            "size_pt": "Font size in points",
            "style": "Word paragraph style name (e.g., 'List Paragraph')",
            "static_text": "This paragraph has fixed text that does not change between versions",
        },
        "slot_types": {
            "header": "Candidate name and contact information",
            "headline": "Target role headline",
            "summary": "Professional summary narrative",
            "highlight": "Top-level highlight bullets (above keywords)",
            "keywords": "Pipe-delimited keyword/skill lists",
            "section_header": "Static section divider (not replaceable content)",
            "spacer": "Empty paragraph for vertical spacing",
            "job_header": "Employer name, location, industry, dates",
            "job_title": "Role title and date range",
            "job_subtitle": "Sub-role header within a job block",
            "job_intro": "Narrative intro paragraph for a job",
            "job_bullet": "Achievement bullet under a job (List Paragraph style)",
            "additional_exp": "One-liner for additional/earlier roles",
            "education": "Degree, field, institution",
            "certification": "Certification name and issuer",
            "ref_header": "Reference section category header",
            "ref_link": "Reference link with description",
        },
    }

    # Capture hyperlink URLs from document relationships
    hyperlink_urls = {}
    for rel_id, rel in doc.part.rels.items():
        if "hyperlink" in str(rel.reltype).lower():
            hyperlink_urls[rel_id] = rel.target_ref

    nsmap_w = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    nsmap_r = {"r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}

    # Record original content for each slot and replace with placeholder
    for para_idx, placeholder, slot_type, fmt_rules in layout:
        if para_idx >= len(paras):
            break

        para = paras[para_idx]
        original_text = para.text

        slot_entry = {
            "para_index": para_idx,
            "slot_type": slot_type,
            "formatting": fmt_rules,
        }

        if placeholder:
            slot_entry["placeholder"] = placeholder
            slot_entry["original_text"] = original_text

            # Capture hyperlink URLs for this paragraph
            hlinks = para._element.findall(".//w:hyperlink", nsmap_w)
            if hlinks:
                slot_hyperlinks = []
                for h in hlinks:
                    rid = h.get(f"{{{nsmap_r['r']}}}id")
                    url = hyperlink_urls.get(rid, "")
                    texts = [t.text for t in h.findall(".//w:t", nsmap_w) if t.text]
                    slot_hyperlinks.append({
                        "rId": rid,
                        "url": url,
                        "text": " ".join(texts),
                    })
                slot_entry["hyperlinks"] = slot_hyperlinks

            _set_placeholder(para, placeholder)
        else:
            slot_entry["placeholder"] = None
            if "static_text" in fmt_rules:
                slot_entry["original_text"] = fmt_rules["static_text"]

        template_map["slots"].append(slot_entry)

    # Save template .docx
    doc.save(output_docx)

    # Save template map JSON
    with open(output_map, "w", encoding="utf-8") as f:
        json.dump(template_map, f, indent=2, ensure_ascii=False)

    return template_map


def templatize(input_path: str, output_docx: str, output_map: str, layout_name: str = "v32") -> dict:
    """Convert a full resume .docx into a placeholder template.

    Routes to the legacy layout-specific templatizer for v31/v32, or to the
    new general-purpose template_builder for 'auto' and any other layout.

    Args:
        input_path: Path to the full resume .docx.
        output_docx: Path to save the placeholder template .docx.
        output_map: Path to save the template map JSON.
        layout_name: Layout to use — "v31", "v32" for legacy, "auto" or
                     anything else for the new parser-based builder.

    Returns:
        A result dict. For legacy layouts this is the full template_map.
        For auto/new layouts this is {slot_count, sections_detected, layout}.
    """
    if layout_name in ("v31", "v32"):
        return _legacy_templatize(input_path, output_docx, output_map, layout_name)

    # New general-purpose path via template_builder
    try:
        from template_builder import build_template
    except ImportError:
        from utils.template_builder import build_template

    return build_template(input_path, output_docx, output_map, layout=layout_name)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert a full .docx resume into a placeholder template."
    )
    parser.add_argument("--input", required=True, help="Path to the full resume .docx")
    parser.add_argument("--output-docx", required=True, help="Path to save placeholder template .docx")
    parser.add_argument("--output-map", required=True, help="Path to save template map JSON")
    parser.add_argument("--layout", default="v32", choices=list(LAYOUTS.keys()) + ["auto"],
                        help="Layout definition to use (default: v32, 'auto' for parser-based)")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not Path(args.input).exists():
        print(f"Error: input not found: {args.input}", file=sys.stderr)
        return 1

    Path(args.output_docx).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output_map).parent.mkdir(parents=True, exist_ok=True)

    tmap = templatize(args.input, args.output_docx, args.output_map, args.layout)

    placeholders = [s for s in tmap["slots"] if s.get("placeholder")]
    print(f"Template created: {args.output_docx}")
    print(f"Template map: {args.output_map}")
    print(f"  Total paragraphs: {tmap['total_paragraphs']}")
    print(f"  Named placeholders: {len(placeholders)}")
    print(f"  Static/spacer: {len(tmap['slots']) - len(placeholders)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
