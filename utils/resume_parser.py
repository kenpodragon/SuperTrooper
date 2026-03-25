"""General-purpose .docx resume parser with section detection and formatting extraction.

Parses any resume layout, detecting sections like header, experience, education,
bullets, etc. based on formatting heuristics (font size, bold, alignment, patterns).
"""

import re
from pathlib import Path
from docx import Document
from docx.shared import Pt, Emu


# --- Contact pattern regexes ---
EMAIL_RE = re.compile(r'[\w.+-]+@[\w-]+\.[\w.-]+')
PHONE_RE = re.compile(r'\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4}')
LINKEDIN_RE = re.compile(r'linkedin\.com/in/', re.IGNORECASE)

# --- Date patterns for job headers ---
DATE_RE = re.compile(
    r'(?:'
    r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*[\s,.]*\d{4}'
    r'|\d{4}\s*[-–—]\s*(?:\d{4}|[Pp]resent|[Cc]urrent)'
    r'|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{4}\s*[-–—]'
    r')',
    re.IGNORECASE
)

# --- Section header keywords (case-insensitive match) ---
SECTION_KEYWORDS = {
    'experience': 'experience',
    'education': 'education',
    'certification': 'certification',
    'skills': 'skills',
    'summary': 'summary',
    'highlights': 'highlights',
    'objective': 'summary',
    'profile': 'summary',
    'qualifications': 'highlights',
    'competencies': 'highlights',
    'expertise': 'skills',
    'technical': 'skills',
    'additional': 'additional',
    'references': 'additional',
    'awards': 'additional',
    'honors': 'additional',
    'publications': 'additional',
    'projects': 'experience',
    'volunteer': 'additional',
    'interests': 'additional',
    'languages': 'skills',
    'professional development': 'education',
    'training': 'education',
    'keywords': 'keywords',
}

# Bullet prefix characters
BULLET_CHARS = set('•●○▪▸►–—‣⁃◦◆◇■□▶')


def _extract_formatting(paragraph) -> dict:
    """Extract formatting metadata from a paragraph."""
    fmt = {
        'font_size': None,
        'bold': None,
        'italic': None,
        'alignment': None,
        'font_name': None,
        'underline': None,
        'space_before': None,
        'space_after': None,
    }

    # Paragraph-level formatting
    pf = paragraph.paragraph_format
    if pf.alignment is not None:
        fmt['alignment'] = str(pf.alignment)
    if pf.space_before is not None:
        fmt['space_before'] = pf.space_before
    if pf.space_after is not None:
        fmt['space_after'] = pf.space_after

    # Run-level formatting (use first run as representative)
    if paragraph.runs:
        run = paragraph.runs[0]
        if run.font.size is not None:
            # Convert EMUs to points
            fmt['font_size'] = round(run.font.size / 12700, 1)
        fmt['bold'] = run.bold
        fmt['italic'] = run.italic
        fmt['font_name'] = run.font.name
        fmt['underline'] = run.underline

    # Try style-level font size if run didn't have one
    if fmt['font_size'] is None and paragraph.style and paragraph.style.font:
        if paragraph.style.font.size is not None:
            fmt['font_size'] = round(paragraph.style.font.size / 12700, 1)

    return fmt


def _has_contact_info(text: str) -> bool:
    """Check if text contains contact information patterns."""
    return bool(EMAIL_RE.search(text) or PHONE_RE.search(text) or LINKEDIN_RE.search(text))


def _has_date_pattern(text: str) -> bool:
    """Check if text contains date patterns typical of job entries."""
    return bool(DATE_RE.search(text))


def _is_bullet_text(text: str) -> bool:
    """Check if text starts with a bullet character or dash-space pattern."""
    if not text:
        return False
    if text[0] in BULLET_CHARS:
        return True
    # Dash followed by space (but not em-dash which is in BULLET_CHARS)
    if text.startswith('- '):
        return True
    return False


def _match_section_keyword(text: str) -> str | None:
    """Match text against known section header keywords. Returns section category or None."""
    lower = text.strip().lower()
    # Remove common decorators
    lower = lower.strip(':').strip()

    for keyword, category in SECTION_KEYWORDS.items():
        if keyword in lower:
            return category
    return None


def _classify_paragraph(
    text: str,
    formatting: dict,
    para_index: int,
    current_section: str,
    is_early: bool,
    prev_type: str | None,
) -> tuple[str, str]:
    """Classify a paragraph into a type and update the current section.

    Returns (paragraph_type, updated_current_section).
    """
    font_size = formatting.get('font_size')
    bold = formatting.get('bold')

    # --- Header detection (early paragraphs with large font or contact info) ---
    if is_early and font_size and font_size >= 14:
        return 'header', 'header'

    if is_early and _has_contact_info(text) and current_section in ('header', ''):
        return 'header', 'header'

    # --- Section header detection ---
    # Bold text that matches section keywords and is relatively short
    section_cat = _match_section_keyword(text)
    if section_cat and len(text) < 80:
        # Check if it looks like a standalone header (bold or larger font)
        if bold or (font_size and font_size >= 11):
            return 'section_header', section_cat

    # --- Headline (title/tagline after name, before content) ---
    if is_early and font_size and 12 < font_size < 20 and bold:
        return 'headline', 'header'

    # --- Within specific sections ---
    if current_section == 'experience' or current_section == 'additional':
        # Job header: has date pattern, typically bold
        if _has_date_pattern(text):
            return 'job_header', current_section

        # Bullet items
        if _is_bullet_text(text):
            return 'bullet', current_section

        # Bold short text under experience could be a job title
        if bold and len(text) < 120 and not _has_date_pattern(text) and prev_type in ('job_header', 'section_header'):
            return 'job_header', current_section

        # Bold text with a colon pattern (highlight-style bullets)
        if bold and ':' in text and len(text) > 50:
            return 'bullet', current_section

        # Non-bold longer text = job intro / description
        if not bold and len(text) > 80:
            return 'job_intro', current_section

        # Short non-bold text that isn't a header
        if len(text) < 80 and not bold:
            return 'job_intro', current_section

        # Fallback for experience content: bold longer text is likely a bullet
        if bold and len(text) > 50:
            return 'bullet', current_section

        return 'bullet', current_section

    if current_section == 'education':
        return 'education', current_section

    if current_section == 'certification':
        return 'certification', current_section

    if current_section == 'skills':
        return 'skills', current_section

    if current_section == 'keywords':
        return 'keywords', current_section

    if current_section == 'summary':
        return 'summary', current_section

    if current_section == 'highlights':
        # Bold text with colon = highlight bullet
        if bold and ':' in text:
            return 'highlights', current_section
        return 'highlights', current_section

    if current_section == 'header':
        # Still in header area
        if _has_contact_info(text):
            return 'header', 'header'
        # Summary text after header
        if not bold and len(text) > 80:
            return 'summary', 'summary'
        # Highlight bullets with bold + colon
        if bold and ':' in text:
            return 'highlights', 'highlights'
        # Keywords line (pipe-separated)
        if '|' in text and text.count('|') >= 3:
            return 'keywords', 'keywords'
        return 'header', 'header'

    # --- Fallback ---
    return 'unknown', current_section


def parse_resume_structure(file_path: str) -> list[dict]:
    """Parse a .docx resume into structured sections with formatting metadata.

    Args:
        file_path: Path to a .docx resume file.

    Returns:
        Ordered list of dicts, each with:
            - type: str - paragraph classification
            - text: str - paragraph text content
            - formatting: dict - font_size, bold, italic, alignment, font_name, underline, space_before, space_after
            - paragraph_index: int - position in document
            - parent_section: str - which section this paragraph belongs to
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Resume file not found: {file_path}")
    if path.suffix.lower() != '.docx':
        raise ValueError(f"Expected .docx file, got: {path.suffix}")

    doc = Document(str(path))

    results = []
    current_section = ''
    total_paragraphs = len(doc.paragraphs)
    prev_type = None

    for i, paragraph in enumerate(doc.paragraphs):
        text = paragraph.text.strip()
        if not text:
            continue

        formatting = _extract_formatting(paragraph)
        is_early = i < min(12, total_paragraphs * 0.15)

        para_type, current_section = _classify_paragraph(
            text=text,
            formatting=formatting,
            para_index=i,
            current_section=current_section,
            is_early=is_early,
            prev_type=prev_type,
        )

        results.append({
            'type': para_type,
            'text': text,
            'formatting': formatting,
            'paragraph_index': i,
            'parent_section': current_section,
        })

        prev_type = para_type

    return results
