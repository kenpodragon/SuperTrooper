"""General-purpose .docx resume parser with section detection and formatting extraction.

Parses any resume layout, detecting sections like header, experience, education,
bullets, etc. based on formatting heuristics (font size, bold, alignment, patterns).

Also provides parse_resume_for_kb() which converts the flat paragraph list into
the nested career_history + bullets format expected by the onboard DB insert pipeline.
"""

import logging
import re
from datetime import date
from pathlib import Path
from docx import Document
from docx.shared import Pt, Emu

logger = logging.getLogger(__name__)


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
    'references': 'references',
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
        # Bullet items (explicit bullet chars)
        if _is_bullet_text(text):
            return 'bullet', current_section

        # Non-bold longer text = job intro / description
        if not bold and len(text) > 80:
            return 'job_intro', current_section

        # Bold text with a colon pattern = achievement bullet (check BEFORE date
        # pattern so bullets mentioning dates like "October 2025" aren't misclassified)
        if bold and ':' in text and len(text) > 50:
            return 'bullet', current_section

        # Job header: has date pattern, typically bold or short
        if _has_date_pattern(text):
            return 'job_header', current_section

        # Bold short text under experience could be a job title
        if bold and len(text) < 120 and prev_type in ('job_header', 'section_header'):
            return 'job_header', current_section

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
        # Bold text with colon = highlight bullet (common in executive resumes)
        if bold and ':' in text and len(text) > 50:
            return 'highlights', 'highlights'
        # Pipe-separated = keywords/skills line
        if '|' in text and text.count('|') >= 3:
            return 'keywords', 'keywords'
        return 'summary', current_section

    if current_section == 'highlights':
        # Bold text with colon = highlight bullet
        if bold and ':' in text:
            return 'highlights', current_section
        # Pipe-separated = keywords/skills line
        if '|' in text and text.count('|') >= 3:
            return 'keywords', 'keywords'
        return 'highlights', current_section

    if current_section == 'references':
        return 'reference', current_section

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


# ---------------------------------------------------------------------------
# KB conversion helpers
# ---------------------------------------------------------------------------

_MONTH_MAP = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
    'january': 1, 'february': 2, 'march': 3, 'april': 4, 'june': 6,
    'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12,
}


def _parse_date_str(s: str | None) -> date | None:
    """Convert a date string like 'June 2024', 'Aug 2021', '2012' to a date object."""
    if not s:
        return None
    s = s.strip()
    if s.lower() in ('present', 'current'):
        return None

    # Try "Month Year" format
    m = re.match(r'^([A-Za-z]+)\s*,?\s*(\d{4})$', s)
    if m:
        month_str = m.group(1).lower()
        year = int(m.group(2))
        month = _MONTH_MAP.get(month_str)
        if month:
            return date(year, month, 1)

    # Try bare year "2012"
    m = re.match(r'^(\d{4})$', s)
    if m:
        return date(int(m.group(1)), 1, 1)

    return None


_BRACES_RE = re.compile(r'\{([^})]+)[})]')
_PARENS_NOTE_RE = re.compile(r'\(([^)]*(?:Onsite|Remote|Hybrid)[^)]*)\)', re.IGNORECASE)
_LOCATION_RE = re.compile(r'([A-Z][a-z]+(?:\s[A-Z][a-z]+)*),\s*([A-Z]{2})\b')
_DATE_RANGE_RE = re.compile(
    r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*[\s,]*\d{4})'
    r'\s*[-–—]\s*'
    r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*[\s,]*\d{4}|[Pp]resent|[Cc]urrent)',
)
_YEAR_RANGE_RE = re.compile(r'(\d{4})\s*[-–—]\s*(\d{4}|[Pp]resent|[Cc]urrent)')
_TITLE_WORDS = re.compile(
    r'\b(?:Director|VP|Vice President|President|Chief|CTO|CEO|CIO|CFO|COO|CPO|CMO|'
    r'Manager|Engineer|Architect|Lead|Head|Senior|Principal|Staff|Founder|'
    r'Consultant|Analyst|Developer|Coordinator|Officer|Advisor)\b',
    re.IGNORECASE
)


def _is_company_line(text: str) -> bool:
    """Heuristic: line is a company header (vs a title line)."""
    if _BRACES_RE.search(text):
        return True
    if _PARENS_NOTE_RE.search(text):
        return True
    loc = _LOCATION_RE.search(text)
    if loc and not _TITLE_WORDS.match(text.split(',')[0].strip()):
        return True
    return False


def _parse_company_line(text: str) -> dict:
    """Extract employer, location, dates, industry from a company line."""
    industry = None
    m = _BRACES_RE.search(text)
    if m:
        industry = m.group(1).strip()
        text = text[:m.start()] + text[m.end():]

    work_mode = None
    m = _PARENS_NOTE_RE.search(text)
    if m:
        work_mode = m.group(1).strip()
        text = text[:m.start()] + text[m.end():]

    start_date, end_date = None, None
    m = _DATE_RANGE_RE.search(text)
    if m:
        start_date = m.group(1).strip()
        end_date = m.group(2).strip()
        text = text[:m.start()] + text[m.end():]
    else:
        m = _YEAR_RANGE_RE.search(text)
        if m:
            start_date = m.group(1).strip()
            end_date = m.group(2).strip()
            text = text[:m.start()] + text[m.end():]

    location = None
    m = _LOCATION_RE.search(text)
    if m:
        location = f"{m.group(1)}, {m.group(2)}"

    employer = re.sub(r'\s*,\s*$', '', text.strip()).strip()
    employer = re.sub(r'\s{2,}', ' ', employer).strip(' ,\t')

    is_current = end_date is not None and end_date.lower() in ('present', 'current')

    return {
        'employer': employer or 'Unknown',
        'title': '',
        'start_date': start_date,
        'end_date': None if is_current else end_date,
        'location': location,
        'industry': industry,
        'intro_text': '',
        'is_current': is_current,
        'bullets': [],
        'notes': work_mode,
    }


def _parse_title_dates(text: str) -> tuple[str, str | None, str | None]:
    """Extract title and optional date range from a title line."""
    start, end = None, None
    m = _DATE_RANGE_RE.search(text)
    if m:
        start = m.group(1).strip()
        end = m.group(2).strip()
        text = text[:m.start()].strip().rstrip(',').strip()
    else:
        m = _YEAR_RANGE_RE.search(text)
        if m:
            start = m.group(1).strip()
            end = m.group(2).strip()
            text = text[:m.start()].strip().rstrip(',').strip()
    return text, start, end


def _parse_oneliner(text: str) -> dict | None:
    """Parse a one-liner 'Title | Company (Industry)  Dates' entry.

    Handles multi-pipe entries like:
        Senior Testing AI Manager | QA Engineering (Part Time) | Fact Finders Pro (NPO Startup)  May 2025 - Present
    The LAST pipe-separated segment is the company (possibly with industry in parens).
    Everything before is the title.
    """
    # Split off dates from end (tab or multi-space separated)
    parts = re.split(r'\t+|\s{3,}', text, maxsplit=1)
    main_part = parts[0].strip()
    date_part = parts[1].strip() if len(parts) > 1 else ''

    if '|' not in main_part:
        return None

    segments = [s.strip() for s in main_part.split('|')]
    if len(segments) < 2:
        return None

    # Last segment is the company (possibly with industry in parens)
    company_seg = segments[-1]
    title_seg = ' | '.join(segments[:-1])

    # Extract industry from nested parens at end of company segment
    industry = None
    m = re.search(r'\((.+)\)\s*$', company_seg)
    if m:
        industry = m.group(1).strip()
        company_seg = company_seg[:m.start()].strip()

    # Parse dates
    start_date, end_date = None, None
    dm = _DATE_RANGE_RE.search(date_part)
    if dm:
        start_date = dm.group(1).strip()
        end_date = dm.group(2).strip()
    else:
        dm = _YEAR_RANGE_RE.search(date_part)
        if dm:
            start_date = dm.group(1).strip()
            end_date = dm.group(2).strip()

    is_current = end_date is not None and end_date.lower() in ('present', 'current')
    return {
        'employer': company_seg or 'Unknown',
        'title': title_seg,
        'start_date': start_date,
        'end_date': None if is_current else end_date,
        'location': None,
        'industry': industry,
        'intro_text': '',
        'is_current': is_current,
        'bullets': [],
        'notes': None,
    }


def parse_resume_for_kb(file_path: str) -> dict:
    """Parse a .docx resume into the nested KB format for DB insert.

    Uses parse_resume_structure() to classify paragraphs, then groups them
    into career_history entries with nested bullets, plus skills, education, etc.

    Returns:
        dict with:
            career_history: list of dicts (employer, title, dates, location, intro_text, bullets)
            skills: list of skill name strings
            education: list of education line strings
            certifications: list of certification line strings
            highlights: list of highlight bullet strings
            summary: str - professional summary text
            confidence: float 0-1
    """
    paragraphs = parse_resume_structure(file_path)

    career_history = []
    current_job = None
    in_additional = False
    skills = []
    education = []
    certifications = []
    highlights = []
    summary_parts = []

    for para in paragraphs:
        ptype = para['type']
        text = para['text']
        section = para['parent_section']

        # -- Section header: "Additional Work Experience" flips one-liner mode --
        if ptype == 'section_header':
            if current_job:
                career_history.append(current_job)
                current_job = None
            if 'additional' in text.lower():
                in_additional = True
            else:
                in_additional = False
            continue

        # -- Highlights (top-of-resume achievement bullets) --
        if ptype == 'highlights':
            highlights.append(text)
            continue

        # -- Summary --
        if ptype == 'summary':
            summary_parts.append(text)
            continue

        # -- Skills / Keywords (pipe or comma separated) --
        if ptype in ('skills', 'keywords'):
            for part in re.split(r'[|,]', text):
                skill = part.strip()
                if skill and len(skill) < 60:
                    skills.append(skill)
            continue

        # -- Education --
        if ptype == 'education':
            education.append(text)
            continue

        # -- Certifications --
        if ptype == 'certification':
            certifications.append(text)
            continue

        # -- Experience section content --
        if section in ('experience', 'additional') or in_additional:

            if ptype == 'job_header':
                # In additional section, try one-liner parse
                if in_additional:
                    entry = _parse_oneliner(text)
                    if entry:
                        career_history.append(entry)
                        continue

                # Determine if this is a company line or title line
                if _is_company_line(text):
                    if current_job:
                        career_history.append(current_job)
                    current_job = _parse_company_line(text)
                elif current_job is not None and not current_job['title']:
                    # First title for current company
                    title, start, end = _parse_title_dates(text)
                    current_job['title'] = title
                    if start:
                        current_job['start_date'] = start
                    if end:
                        current_job['end_date'] = None if end.lower() in ('present', 'current') else end
                        current_job['is_current'] = end.lower() in ('present', 'current')
                elif current_job is not None and current_job['title']:
                    # Additional role at same company — split into separate entry
                    career_history.append(current_job)
                    title, start, end = _parse_title_dates(text)
                    current_job = {
                        'employer': current_job['employer'],
                        'title': title,
                        'start_date': start or current_job.get('start_date'),
                        'end_date': (None if end and end.lower() in ('present', 'current') else end) or current_job.get('end_date'),
                        'location': current_job.get('location'),
                        'industry': current_job.get('industry'),
                        'intro_text': '',
                        'is_current': bool(end and end.lower() in ('present', 'current')),
                        'bullets': [],
                        'notes': current_job.get('notes'),
                    }
                else:
                    # No current job context — treat as company
                    if current_job:
                        career_history.append(current_job)
                    current_job = _parse_company_line(text)

            elif ptype == 'job_intro':
                if current_job:
                    if current_job['intro_text']:
                        current_job['intro_text'] += ' ' + text
                    else:
                        current_job['intro_text'] = text

            elif ptype == 'bullet':
                if current_job:
                    current_job['bullets'].append(text)

        # -- Header / headline / unknown — skip for KB purposes --

    # Flush last job
    if current_job:
        career_history.append(current_job)

    # Convert date strings to date objects for DB compatibility
    for job in career_history:
        job['start_date'] = _parse_date_str(job.get('start_date'))
        job['end_date'] = _parse_date_str(job.get('end_date'))

    # Deduplicate skills preserving order
    seen_skills = set()
    unique_skills = []
    for s in skills:
        key = s.lower()
        if key not in seen_skills:
            seen_skills.add(key)
            unique_skills.append(s)

    # Confidence score
    has_jobs = bool(career_history)
    has_bullets = any(j['bullets'] for j in career_history)
    has_skills = bool(unique_skills)
    has_edu = bool(education)
    signals = sum([has_jobs, has_bullets, has_skills, has_edu])

    logger.info(
        "KB parse: %d jobs, %d total bullets, %d skills, %d education, %d highlights",
        len(career_history),
        sum(len(j['bullets']) for j in career_history),
        len(unique_skills),
        len(education),
        len(highlights),
    )

    return {
        'career_history': career_history,
        'skills': unique_skills,
        'education': education,
        'certifications': certifications,
        'highlights': highlights,
        'summary': ' '.join(summary_parts),
        'confidence': round(signals / 4, 2),
    }
