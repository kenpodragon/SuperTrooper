"""Rule-based resume parser.

Extracts career history, bullets, skills, and education from plain resume text
using regex and heuristics. No external dependencies or API calls.
"""

import re
from typing import Any


# Section header patterns (case-insensitive)
_SECTION_PATTERNS = {
    "experience": re.compile(
        r"^\s*(experience|work experience|employment|career history|professional experience)\s*$",
        re.IGNORECASE,
    ),
    "education": re.compile(
        r"^\s*(education|academic background|qualifications)\s*$",
        re.IGNORECASE,
    ),
    "skills": re.compile(
        r"^\s*(skills|technical skills|core competencies|technologies|expertise)\s*$",
        re.IGNORECASE,
    ),
    "summary": re.compile(
        r"^\s*(summary|professional summary|profile|objective|about me)\s*$",
        re.IGNORECASE,
    ),
}

# Employer line: "Company | Title | Date range | Location"  (pipes optional)
# Also handles: "Company  -  Title  |  Date range"
_EMPLOYER_PATTERN = re.compile(
    r"^(?P<employer>[A-Z][^|\n]{2,50}?)"
    r"\s*\|\s*"
    r"(?P<title>[^|\n]{3,80}?)"
    r"\s*\|\s*"
    r"(?P<dates>[A-Z][a-z]{2,8}\s+\d{4}\s*[-–]\s*(?:[A-Z][a-z]{2,8}\s+\d{4}|Present|Current))"
    r"(?:\s*\|\s*(?P<location>[^|\n]+?))?$",
    re.IGNORECASE,
)

# Bullet characters
_BULLET_CHARS = re.compile(r"^[\s]*[•\-\*▪▸◦·>]\s+(.+)$")

# Metrics that flag a bullet as a highlight
_METRIC_PATTERN = re.compile(r"\d+[\.,]?\d*\s*[%KMBkmbx]|\b\d{4,}\b|\bteam of \d+\b", re.IGNORECASE)


def _detect_sections(lines: list[str]) -> dict[str, list[str]]:
    """Split lines into named sections based on header patterns."""
    sections: dict[str, list[str]] = {
        "experience": [],
        "education": [],
        "skills": [],
        "summary": [],
        "_other": [],
    }
    current = "_other"

    for line in lines:
        matched = False
        for name, pattern in _SECTION_PATTERNS.items():
            if pattern.match(line):
                current = name
                matched = True
                break
        if not matched:
            sections[current].append(line)

    return sections


def _extract_employers(lines: list[str]) -> list[dict[str, Any]]:
    """Extract employer records from experience section lines."""
    employers = []
    for line in lines:
        m = _EMPLOYER_PATTERN.match(line.strip())
        if m:
            employers.append(
                {
                    "employer": m.group("employer").strip(),
                    "title": m.group("title").strip(),
                    "dates": m.group("dates").strip(),
                    "location": (m.group("location") or "").strip(),
                }
            )
    return employers


def _extract_bullets(lines: list[str], section: str = "experience") -> list[dict[str, Any]]:
    """Extract bullet points, tagging metrics-containing ones as 'highlight'."""
    bullets = []
    for line in lines:
        m = _BULLET_CHARS.match(line)
        if m:
            text = m.group(1).strip()
            has_metric = bool(_METRIC_PATTERN.search(text))
            bullets.append(
                {
                    "text": text,
                    "type": "highlight" if has_metric else "standard",
                    "section": section,
                }
            )
    return bullets


def _extract_skills(lines: list[str]) -> list[str]:
    """Extract skills from comma- or pipe-separated lines."""
    skills: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        # Split on commas or pipes
        parts = re.split(r"[,|]", stripped)
        for part in parts:
            skill = part.strip()
            if skill and len(skill) < 60:
                skills.append(skill)
    return skills


def parse_resume_text(text: str) -> dict[str, Any]:
    """Parse resume plain text into structured data.

    Args:
        text: Full resume text extracted from a document.

    Returns:
        dict with keys:
            career_history: list of employer dicts
            bullets: list of bullet dicts (text, type, section)
            skills: list of skill strings
            education: list of education line strings
            confidence: float 0-1 based on signals found
    """
    if not text or not text.strip():
        return {
            "career_history": [],
            "bullets": [],
            "skills": [],
            "education": [],
            "confidence": 0.0,
        }

    lines = text.splitlines()
    sections = _detect_sections(lines)

    career_history = _extract_employers(sections["experience"])
    bullets = _extract_bullets(sections["experience"], section="experience")
    skills = _extract_skills(sections["skills"])
    education = [ln.strip() for ln in sections["education"] if ln.strip()]

    # Confidence: one signal per found category (max 4)
    signals = sum(
        [
            1 if career_history else 0,
            1 if bullets else 0,
            1 if skills else 0,
            1 if education else 0,
        ]
    )
    confidence = round(signals / 4, 2)

    return {
        "career_history": career_history,
        "bullets": bullets,
        "skills": skills,
        "education": education,
        "confidence": confidence,
    }
