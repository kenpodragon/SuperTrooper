# Resume Builder Phase 4 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the Resume Builder with AI endpoints, general-purpose resume parser/templatizer, template browser, and E2E validation.

**Architecture:** Four new API endpoints follow the existing `route_inference` pattern (AI + Python fallback). The general-purpose parser replaces the V31/V32-only templatizer. Template browser adds a tab to the Resumes page. E2E test script validates the full pipeline.

**Tech Stack:** Flask, python-docx, React/TypeScript, PostgreSQL, route_inference AI routing, Pillow for thumbnails.

---

## File Structure

### New Files

| File | Responsibility |
|------|---------------|
| `code/utils/resume_parser.py` | General-purpose .docx section detection + content extraction |
| `code/utils/template_builder.py` | Formatting extraction + placeholder template generation from parsed sections |
| `code/frontend/src/pages/resume-builder/AiReviewPanel.tsx` | AI review sidebar with scores + feedback |
| `code/frontend/src/pages/resume-builder/AiGenerateModal.tsx` | AI slot generation modal |
| `code/frontend/src/pages/resume-builder/BestPicksPanel.tsx` | JD-based bullet/job ranking panel |
| `code/frontend/src/pages/resume-builder/AtsScoreModal.tsx` | ATS score modal in builder |
| `code/frontend/src/pages/resumes/TemplatesBrowser.tsx` | Template grid with thumbnails |
| `code/frontend/src/pages/resumes/TemplateDetail.tsx` | Template slot map detail view |
| `code/db/migrations/031_template_parser_version.sql` | parser_version column |
| `local_code/e2e_resume_test.py` | End-to-end validation script |
| `code/tests/test_resume_parser.py` | Parser unit tests |
| `code/tests/test_template_builder.py` | Template builder unit tests |
| `code/tests/test_ai_endpoints.py` | AI endpoint integration tests |

### Modified Files

| File | Changes |
|------|---------|
| `code/backend/routes/resume.py` | Add 5 new endpoints (ai-review, ai-generate-slot, best-picks, ats-score, thumbnail) |
| `code/backend/routes/onboard.py` | Wire new parser into upload pipeline |
| `code/utils/templatize_resume.py` | Refactor to delegate to resume_parser + template_builder |
| `code/utils/generate_resume.py` | Fix synopsis dict extraction bug |
| `code/frontend/src/pages/resume-builder/ResumeEditor.tsx` | Wire AI review + ATS score + generate-slot + best-picks callbacks |
| `code/frontend/src/pages/resume-builder/EditorToolbar.tsx` | Add best-picks + generate-slot buttons, enable AI Review button |
| `code/frontend/src/pages/resume-builder/ContentPickerModal.tsx` | Integrate best-picks results |
| `code/frontend/src/pages/resumes/Resumes.tsx` | Add Templates tab |
| `code/frontend/src/api/client.ts` | Add API functions for new endpoints |
| `code/backend/ai_providers/base.py` | Add abstract methods for new AI tasks |
| `code/backend/ai_providers/claude_provider.py` | Implement new AI methods |

---

## Task 1: General-Purpose Resume Parser

**Files:**
- Create: `code/utils/resume_parser.py`
- Create: `code/tests/test_resume_parser.py`

- [ ] **Step 1: Write failing test for section detection**

```python
# code/tests/test_resume_parser.py
import pytest
from pathlib import Path

# Use a known resume for testing
TEST_RESUME = Path("Archived/Originals/Stephen_Salaka_Resume_v32.docx")

def test_parser_detects_header():
    """Parser should detect the header section (name + contact info)."""
    from utils.resume_parser import parse_resume_structure
    if not TEST_RESUME.exists():
        pytest.skip("Test resume not available")
    sections = parse_resume_structure(str(TEST_RESUME))
    headers = [s for s in sections if s["type"] == "header"]
    assert len(headers) >= 1
    assert "Stephen" in headers[0]["text"]

def test_parser_detects_experience_sections():
    """Parser should detect job blocks with company/title/dates."""
    from utils.resume_parser import parse_resume_structure
    if not TEST_RESUME.exists():
        pytest.skip("Test resume not available")
    sections = parse_resume_structure(str(TEST_RESUME))
    jobs = [s for s in sections if s["type"] == "experience"]
    assert len(jobs) >= 3  # At least 3 job blocks expected

def test_parser_detects_education():
    """Parser should detect education entries."""
    from utils.resume_parser import parse_resume_structure
    if not TEST_RESUME.exists():
        pytest.skip("Test resume not available")
    sections = parse_resume_structure(str(TEST_RESUME))
    edu = [s for s in sections if s["type"] == "education"]
    assert len(edu) >= 1

def test_parser_detects_bullets():
    """Parser should extract bullets from job blocks."""
    from utils.resume_parser import parse_resume_structure
    if not TEST_RESUME.exists():
        pytest.skip("Test resume not available")
    sections = parse_resume_structure(str(TEST_RESUME))
    bullets = [s for s in sections if s["type"] == "bullet"]
    assert len(bullets) >= 15  # V32 has 25 bullets across 4 jobs

def test_parser_preserves_formatting():
    """Parser should capture bold/italic/font-size per paragraph."""
    from utils.resume_parser import parse_resume_structure
    if not TEST_RESUME.exists():
        pytest.skip("Test resume not available")
    sections = parse_resume_structure(str(TEST_RESUME))
    # Header should have formatting metadata
    header = [s for s in sections if s["type"] == "header"][0]
    assert "formatting" in header
    assert "font_size" in header["formatting"]

def test_parser_returns_ordered_sections():
    """Sections should be in document order."""
    from utils.resume_parser import parse_resume_structure
    if not TEST_RESUME.exists():
        pytest.skip("Test resume not available")
    sections = parse_resume_structure(str(TEST_RESUME))
    types_in_order = [s["type"] for s in sections]
    # Header should come before experience
    header_idx = types_in_order.index("header")
    exp_idx = types_in_order.index("experience")
    assert header_idx < exp_idx
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd code && python -m pytest tests/test_resume_parser.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'utils.resume_parser'`

- [ ] **Step 3: Implement resume_parser.py**

```python
# code/utils/resume_parser.py
"""General-purpose .docx resume parser.

Parses any .docx resume into ordered sections with type classification,
content extraction, and formatting metadata. No hardcoded layouts.
"""

import re
from pathlib import Path
from docx import Document
from docx.shared import Pt

# Section header keywords (case-insensitive)
SECTION_HEADERS = {
    "experience": ["experience", "professional experience", "work history", "employment"],
    "education": ["education", "academic", "degrees"],
    "certifications": ["certification", "certifications", "licenses", "credentials"],
    "skills": ["skills", "technical skills", "core competencies", "technologies"],
    "summary": ["summary", "professional summary", "executive summary", "profile", "objective"],
    "highlights": ["highlights", "key achievements", "selected achievements", "career highlights"],
    "keywords": ["keywords", "areas of expertise", "core strengths"],
    "additional": ["additional experience", "other experience", "volunteer", "publications",
                   "references", "awards", "honors", "affiliations", "memberships"],
}

# Patterns
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE = re.compile(r"[\(]?\d{3}[\)]?[\s.-]?\d{3}[\s.-]?\d{4}")
LINKEDIN_RE = re.compile(r"linkedin\.com/in/[\w-]+", re.IGNORECASE)
DATE_RE = re.compile(
    r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}"
    r"|(?:19|20)\d{2}\s*[-\u2013]\s*(?:(?:19|20)\d{2}|[Pp]resent|[Cc]urrent)"
    r"|\d{1,2}/\d{4}\s*[-\u2013]",
    re.IGNORECASE,
)
BULLET_CHARS = set("\u2022\u2023\u25aa\u25ab\u25cf\u25cb\u25e6\u2043\u2219-\u27a2")


def _get_formatting(paragraph):
    """Extract formatting metadata from a paragraph."""
    fmt = {
        "font_size": None,
        "bold": False,
        "italic": False,
        "alignment": str(paragraph.alignment) if paragraph.alignment else "LEFT",
        "font_name": None,
        "underline": False,
        "space_before": None,
        "space_after": None,
    }
    if paragraph.runs:
        run = paragraph.runs[0]
        if run.font.size:
            fmt["font_size"] = run.font.size.pt
        fmt["bold"] = bool(run.bold)
        fmt["italic"] = bool(run.italic)
        fmt["underline"] = bool(run.underline)
        if run.font.name:
            fmt["font_name"] = run.font.name
    pf = paragraph.paragraph_format
    if pf.space_before:
        fmt["space_before"] = pf.space_before.pt if hasattr(pf.space_before, "pt") else None
    if pf.space_after:
        fmt["space_after"] = pf.space_after.pt if hasattr(pf.space_after, "pt") else None
    return fmt


def _is_bullet_line(text):
    """Check if text starts with a bullet character."""
    stripped = text.strip()
    if not stripped:
        return False
    return stripped[0] in BULLET_CHARS


def _classify_header(text):
    """Check which section header category this text matches."""
    lower = text.strip().lower().rstrip(":")
    for section_type, keywords in SECTION_HEADERS.items():
        for kw in keywords:
            if lower == kw or lower.startswith(kw):
                return section_type
    return None


def _is_contact_info(text):
    """Check if text contains contact information patterns."""
    checks = [EMAIL_RE.search(text), PHONE_RE.search(text), LINKEDIN_RE.search(text)]
    return sum(bool(c) for c in checks) >= 1


def _is_job_header(text, formatting):
    """Detect job header lines: company + title + dates."""
    has_date = bool(DATE_RE.search(text))
    is_bold = formatting.get("bold", False)
    # Job headers typically have dates and are bold or have larger font
    return has_date and (is_bold or (formatting.get("font_size") and formatting["font_size"] >= 11))


def parse_resume_structure(file_path: str) -> list[dict]:
    """Parse a .docx resume into ordered sections.

    Returns a list of dicts, each with:
        - type: str (header, headline, summary, highlights, keywords, experience,
                     job_header, bullet, job_intro, education, certifications,
                     skills, additional, section_header, unknown)
        - text: str (the paragraph text)
        - formatting: dict (font_size, bold, italic, alignment, etc.)
        - paragraph_index: int (position in document)
        - parent_section: str | None (e.g., "experience" for bullets under a job)
    """
    doc = Document(file_path)
    sections = []
    current_section = None
    header_done = False
    para_count = len(doc.paragraphs)

    # First pass: collect all paragraphs with formatting
    raw = []
    for i, para in enumerate(doc.paragraphs):
        text = para.text.strip()
        if not text:
            continue
        fmt = _get_formatting(para)
        raw.append({"text": text, "formatting": fmt, "paragraph_index": i})

    if not raw:
        return sections

    # Detect header block: first few paragraphs until we hit a section header or job
    # Header is typically: name (large font), then contact line(s)
    for i, item in enumerate(raw):
        text = item["text"]
        fmt = item["formatting"]

        # Check if this is a known section header
        section_match = _classify_header(text)
        if section_match:
            header_done = True
            current_section = section_match
            sections.append({
                "type": "section_header",
                "text": text,
                "formatting": fmt,
                "paragraph_index": item["paragraph_index"],
                "parent_section": section_match,
            })
            continue

        # Header detection: first paragraphs with large font or contact info
        if not header_done:
            if i == 0 or (fmt.get("font_size") and fmt["font_size"] >= 14):
                sections.append({
                    "type": "header",
                    "text": text,
                    "formatting": fmt,
                    "paragraph_index": item["paragraph_index"],
                    "parent_section": None,
                })
                continue
            elif _is_contact_info(text):
                sections.append({
                    "type": "header",
                    "text": text,
                    "formatting": fmt,
                    "paragraph_index": item["paragraph_index"],
                    "parent_section": None,
                })
                continue
            elif i <= 3 and not _is_bullet_line(text) and not _is_job_header(text, fmt):
                # Could be headline or summary before any section headers
                if len(text) < 100 and (fmt.get("bold") or (fmt.get("font_size") and fmt["font_size"] >= 12)):
                    sections.append({
                        "type": "headline",
                        "text": text,
                        "formatting": fmt,
                        "paragraph_index": item["paragraph_index"],
                        "parent_section": None,
                    })
                    continue
                else:
                    header_done = True
                    # Fall through to classify below

        # Within a section: classify based on current_section context
        if current_section == "experience" or (not current_section and _is_job_header(text, fmt)):
            if not current_section:
                current_section = "experience"

            if _is_job_header(text, fmt):
                sections.append({
                    "type": "job_header",
                    "text": text,
                    "formatting": fmt,
                    "paragraph_index": item["paragraph_index"],
                    "parent_section": "experience",
                })
            elif _is_bullet_line(text):
                sections.append({
                    "type": "bullet",
                    "text": text.lstrip("".join(BULLET_CHARS) + " "),
                    "formatting": fmt,
                    "paragraph_index": item["paragraph_index"],
                    "parent_section": "experience",
                })
            elif len(text) > 80 and not fmt.get("bold"):
                # Long non-bold text under experience = job intro/synopsis
                sections.append({
                    "type": "job_intro",
                    "text": text,
                    "formatting": fmt,
                    "paragraph_index": item["paragraph_index"],
                    "parent_section": "experience",
                })
            else:
                sections.append({
                    "type": "experience",
                    "text": text,
                    "formatting": fmt,
                    "paragraph_index": item["paragraph_index"],
                    "parent_section": "experience",
                })

        elif current_section == "education":
            sections.append({
                "type": "education",
                "text": text,
                "formatting": fmt,
                "paragraph_index": item["paragraph_index"],
                "parent_section": "education",
            })

        elif current_section == "certifications":
            sections.append({
                "type": "certification",
                "text": text,
                "formatting": fmt,
                "paragraph_index": item["paragraph_index"],
                "parent_section": "certifications",
            })

        elif current_section == "skills":
            sections.append({
                "type": "skills",
                "text": text,
                "formatting": fmt,
                "paragraph_index": item["paragraph_index"],
                "parent_section": "skills",
            })

        elif current_section == "summary":
            sections.append({
                "type": "summary",
                "text": text,
                "formatting": fmt,
                "paragraph_index": item["paragraph_index"],
                "parent_section": "summary",
            })

        elif current_section == "highlights":
            if _is_bullet_line(text):
                sections.append({
                    "type": "highlight",
                    "text": text.lstrip("".join(BULLET_CHARS) + " "),
                    "formatting": fmt,
                    "paragraph_index": item["paragraph_index"],
                    "parent_section": "highlights",
                })
            else:
                sections.append({
                    "type": "highlights",
                    "text": text,
                    "formatting": fmt,
                    "paragraph_index": item["paragraph_index"],
                    "parent_section": "highlights",
                })

        elif current_section == "keywords":
            sections.append({
                "type": "keywords",
                "text": text,
                "formatting": fmt,
                "paragraph_index": item["paragraph_index"],
                "parent_section": "keywords",
            })

        elif current_section == "additional":
            sections.append({
                "type": "additional",
                "text": text,
                "formatting": fmt,
                "paragraph_index": item["paragraph_index"],
                "parent_section": "additional",
            })

        else:
            # Unknown section or pre-section content
            if _is_bullet_line(text):
                sections.append({
                    "type": "bullet",
                    "text": text.lstrip("".join(BULLET_CHARS) + " "),
                    "formatting": fmt,
                    "paragraph_index": item["paragraph_index"],
                    "parent_section": current_section,
                })
            elif len(text) > 150:
                sections.append({
                    "type": "summary",
                    "text": text,
                    "formatting": fmt,
                    "paragraph_index": item["paragraph_index"],
                    "parent_section": current_section,
                })
            else:
                sections.append({
                    "type": "unknown",
                    "text": text,
                    "formatting": fmt,
                    "paragraph_index": item["paragraph_index"],
                    "parent_section": current_section,
                })

    return sections
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd code && python -m pytest tests/test_resume_parser.py -v`
Expected: All 6 tests PASS (adjust assertions if V32 structure differs from expectations)

- [ ] **Step 5: Commit**

```bash
cd code && git add utils/resume_parser.py tests/test_resume_parser.py && git commit -m "feat: add general-purpose resume parser with section detection"
```

---

## Task 2: Template Builder

**Files:**
- Create: `code/utils/template_builder.py`
- Create: `code/tests/test_template_builder.py`

- [ ] **Step 1: Write failing test for template building**

```python
# code/tests/test_template_builder.py
import pytest
import json
import tempfile
from pathlib import Path

TEST_RESUME = Path("Archived/Originals/Stephen_Salaka_Resume_v32.docx")

def test_build_template_creates_docx():
    """Template builder should output a .docx with placeholders."""
    from utils.template_builder import build_template
    if not TEST_RESUME.exists():
        pytest.skip("Test resume not available")
    with tempfile.TemporaryDirectory() as tmpdir:
        out_docx = Path(tmpdir) / "template.docx"
        out_map = Path(tmpdir) / "template_map.json"
        result = build_template(str(TEST_RESUME), str(out_docx), str(out_map))
        assert out_docx.exists()
        assert out_map.exists()
        assert result["slot_count"] > 0

def test_template_map_has_slot_metadata():
    """Template map should have type, formatting, and original_text per slot."""
    from utils.template_builder import build_template
    if not TEST_RESUME.exists():
        pytest.skip("Test resume not available")
    with tempfile.TemporaryDirectory() as tmpdir:
        out_docx = Path(tmpdir) / "template.docx"
        out_map = Path(tmpdir) / "template_map.json"
        build_template(str(TEST_RESUME), str(out_docx), str(out_map))
        tmap = json.loads(out_map.read_text())
        # Should have at least header, job, bullet slots
        assert any("HEADER" in k for k in tmap)
        assert any("JOB" in k for k in tmap)
        assert any("BULLET" in k for k in tmap)
        # Each slot should have required fields
        first_key = list(tmap.keys())[0]
        assert "type" in tmap[first_key]
        assert "original_text" in tmap[first_key]

def test_template_docx_has_placeholders():
    """Output .docx should contain {{PLACEHOLDER}} markers."""
    from utils.template_builder import build_template
    from docx import Document
    if not TEST_RESUME.exists():
        pytest.skip("Test resume not available")
    with tempfile.TemporaryDirectory() as tmpdir:
        out_docx = Path(tmpdir) / "template.docx"
        out_map = Path(tmpdir) / "template_map.json"
        build_template(str(TEST_RESUME), str(out_docx), str(out_map))
        doc = Document(str(out_docx))
        full_text = " ".join(p.text for p in doc.paragraphs)
        assert "{{" in full_text
        assert "}}" in full_text

def test_template_preserves_formatting():
    """Placeholder paragraphs should retain original formatting (bold, font size)."""
    from utils.template_builder import build_template
    from docx import Document
    if not TEST_RESUME.exists():
        pytest.skip("Test resume not available")
    with tempfile.TemporaryDirectory() as tmpdir:
        out_docx = Path(tmpdir) / "template.docx"
        out_map = Path(tmpdir) / "template_map.json"
        build_template(str(TEST_RESUME), str(out_docx), str(out_map))
        doc = Document(str(out_docx))
        # At least some paragraphs should have formatting
        has_bold = any(
            any(r.bold for r in p.runs if r.bold is not None)
            for p in doc.paragraphs if p.text.strip()
        )
        assert has_bold, "Template should preserve bold formatting"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd code && python -m pytest tests/test_template_builder.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'utils.template_builder'`

- [ ] **Step 3: Implement template_builder.py**

```python
# code/utils/template_builder.py
"""Build placeholder templates from parsed resume structure.

Takes the output of resume_parser.parse_resume_structure() and produces:
1. A .docx template with {{SLOT}} placeholders preserving formatting
2. A template_map.json with slot metadata (type, formatting, original_text)
"""

import json
import re
from pathlib import Path
from copy import deepcopy
from docx import Document

from utils.resume_parser import parse_resume_structure


def _generate_slot_name(section_type: str, counters: dict, parent_section: str | None = None) -> str:
    """Generate unique slot names like HEADER_NAME, JOB_1_BULLET_1, etc."""
    if section_type == "header":
        counters["header"] = counters.get("header", 0) + 1
        idx = counters["header"]
        if idx == 1:
            return "HEADER_NAME"
        return f"HEADER_CONTACT_{idx - 1}"
    elif section_type == "headline":
        return "HEADLINE"
    elif section_type == "summary":
        counters["summary"] = counters.get("summary", 0) + 1
        idx = counters["summary"]
        return f"SUMMARY_{idx}" if idx > 1 else "SUMMARY"
    elif section_type == "highlight":
        counters["highlight"] = counters.get("highlight", 0) + 1
        return f"HIGHLIGHT_{counters['highlight']}"
    elif section_type == "job_header":
        counters["job"] = counters.get("job", 0) + 1
        counters["job_bullet"] = 0  # Reset bullet counter per job
        return f"JOB_{counters['job']}_HEADER"
    elif section_type == "job_intro":
        job_num = counters.get("job", 1)
        return f"JOB_{job_num}_INTRO"
    elif section_type == "bullet" and parent_section == "experience":
        job_num = counters.get("job", 1)
        counters["job_bullet"] = counters.get("job_bullet", 0) + 1
        return f"JOB_{job_num}_BULLET_{counters['job_bullet']}"
    elif section_type == "education":
        counters["edu"] = counters.get("edu", 0) + 1
        return f"EDUCATION_{counters['edu']}"
    elif section_type == "certification":
        counters["cert"] = counters.get("cert", 0) + 1
        return f"CERT_{counters['cert']}"
    elif section_type == "skills":
        counters["skills"] = counters.get("skills", 0) + 1
        return f"SKILLS_{counters['skills']}"
    elif section_type == "keywords":
        counters["keywords"] = counters.get("keywords", 0) + 1
        return f"KEYWORDS_{counters['keywords']}"
    elif section_type == "additional":
        counters["additional"] = counters.get("additional", 0) + 1
        return f"ADDL_EXP_{counters['additional']}"
    elif section_type == "bullet":
        counters["misc_bullet"] = counters.get("misc_bullet", 0) + 1
        return f"BULLET_{counters['misc_bullet']}"
    elif section_type == "section_header":
        return None  # Don't replace section headers with placeholders
    else:
        counters["unknown"] = counters.get("unknown", 0) + 1
        return f"SLOT_{counters['unknown']}"


def _set_placeholder_text(paragraph, placeholder: str):
    """Replace paragraph text with {{PLACEHOLDER}} while preserving formatting.

    Clears all runs except the first, sets first run text to the placeholder.
    """
    if not paragraph.runs:
        paragraph.text = f"{{{{{placeholder}}}}}"
        return

    # Keep first run's formatting, set its text
    paragraph.runs[0].text = f"{{{{{placeholder}}}}}"
    # Clear remaining runs
    for run in paragraph.runs[1:]:
        run.text = ""


def build_template(
    input_path: str,
    output_docx: str,
    output_map: str,
    layout: str = "auto",
) -> dict:
    """Build a placeholder template from any .docx resume.

    Args:
        input_path: Path to source .docx resume
        output_docx: Path to write placeholder template .docx
        output_map: Path to write template_map.json
        layout: Layout hint (currently unused, reserved for future)

    Returns:
        dict with slot_count, sections_detected, layout
    """
    # Step 1: Parse the resume structure
    sections = parse_resume_structure(input_path)

    # Step 2: Open the document for modification
    doc = Document(input_path)

    # Build paragraph index map (paragraph_index -> paragraph object)
    para_map = {}
    for i, para in enumerate(doc.paragraphs):
        para_map[i] = para

    # Step 3: Generate slot names and build template_map
    template_map = {}
    counters = {}
    slot_assignments = {}  # paragraph_index -> slot_name

    for section in sections:
        slot_name = _generate_slot_name(
            section["type"], counters, section.get("parent_section")
        )
        if slot_name is None:
            continue  # Skip section headers

        template_map[slot_name] = {
            "type": section["type"],
            "original_text": section["text"],
            "formatting": section["formatting"],
            "parent_section": section.get("parent_section"),
        }
        slot_assignments[section["paragraph_index"]] = slot_name

    # Step 4: Replace content with placeholders in the .docx
    for para_idx, slot_name in slot_assignments.items():
        if para_idx in para_map:
            _set_placeholder_text(para_map[para_idx], slot_name)

    # Step 5: Save outputs
    doc.save(output_docx)
    Path(output_map).write_text(json.dumps(template_map, indent=2, default=str))

    # Detect layout type from sections
    section_types = set(s["type"] for s in sections)
    detected_layout = "standard"
    if "highlight" in section_types:
        detected_layout = "highlights"
    if "keywords" in section_types:
        detected_layout = "keywords"

    return {
        "slot_count": len(template_map),
        "sections_detected": list(section_types),
        "layout": detected_layout,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd code && python -m pytest tests/test_template_builder.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
cd code && git add utils/template_builder.py tests/test_template_builder.py && git commit -m "feat: add template builder for general-purpose placeholder generation"
```

---

## Task 3: Migration 031 + Thumbnail Route

**Files:**
- Create: `code/db/migrations/031_template_parser_version.sql`
- Modify: `code/backend/routes/resume.py` (add thumbnail endpoint)

- [ ] **Step 0: Add Pillow to requirements.txt**

Add `Pillow>=10.0` to `code/backend/requirements.txt` for thumbnail generation.

- [ ] **Step 1: Write migration**

```sql
-- 031_template_parser_version.sql
-- Add parser_version to track which parser version created the template
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='resume_templates' AND column_name='parser_version') THEN
        ALTER TABLE resume_templates ADD COLUMN parser_version VARCHAR(10) DEFAULT '1.0';
    END IF;
END $$;
```

- [ ] **Step 2: Run migration**

Run: `PGPASSWORD=WUHD8fBisb57FS4Q3bdvfuvgnim9fL1c psql -h localhost -p 5555 -U supertroopers -d supertroopers -f code/db/migrations/031_template_parser_version.sql`
Expected: `DO` (success)

- [ ] **Step 3: Add thumbnail generation endpoint to resume.py**

Read `code/backend/routes/resume.py` lines 1-15 for imports, then add after the last endpoint:

```python
# Add to imports at top of resume.py:
from PIL import Image
import io

# Add new endpoint at end of file:
@bp.route("/api/resume/templates/<int:template_id>/thumbnail", methods=["GET"])
def get_template_thumbnail(template_id):
    """Return cached PNG thumbnail of a template, generating if needed."""
    row = db.query_one(
        "SELECT id, preview_blob, template_blob, name FROM resume_templates WHERE id = %s",
        (template_id,),
    )
    if not row:
        return jsonify({"error": "Template not found"}), 404

    # Return cached thumbnail if available
    if row["preview_blob"]:
        return Response(bytes(row["preview_blob"]), mimetype="image/png")

    # Generate thumbnail from template blob
    if not row["template_blob"]:
        return jsonify({"error": "No template blob available"}), 404

    try:
        thumbnail_bytes = _generate_thumbnail_html(row["template_blob"], row.get("name", "Template"))
        # Cache it
        db.execute(
            "UPDATE resume_templates SET preview_blob = %s WHERE id = %s",
            (thumbnail_bytes, template_id),
        )
        return Response(thumbnail_bytes, mimetype="image/png")
    except Exception as e:
        # Return a placeholder if generation fails
        return jsonify({"error": f"Thumbnail generation failed: {str(e)}"}), 500


def _generate_thumbnail_html(template_blob: bytes, name: str) -> bytes:
    """Generate a thumbnail preview from a template .docx blob.

    Uses python-docx to extract structure, renders as a simple HTML-to-image
    representation showing the layout structure with placeholder names.
    Falls back to a text-based layout diagram if image rendering unavailable.
    """
    import tempfile
    from docx import Document as DocxDocument

    # Write blob to temp file and parse
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        f.write(template_blob)
        f.flush()
        doc = DocxDocument(f.name)

    # Build a simple layout representation
    lines = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        if "{{" in text:
            # Placeholder line - show slot name
            lines.append(("slot", text))
        else:
            lines.append(("text", text[:60]))

    # Render as PNG using Pillow (pure Python, no external deps)
    width, height = 300, 400
    img = Image.new("RGB", (width, height), color=(255, 255, 255))

    try:
        from PIL import ImageDraw, ImageFont
        draw = ImageDraw.Draw(img)

        # Title
        draw.text((10, 5), name, fill=(0, 0, 0))
        draw.line([(10, 20), (width - 10, 20)], fill=(200, 200, 200))

        y = 28
        for line_type, text in lines[:30]:  # Max 30 lines for thumbnail
            if y > height - 15:
                break
            if line_type == "slot":
                # Draw placeholder as colored block
                slot_name = text.replace("{{", "").replace("}}", "").strip()
                color = (220, 235, 255)  # Light blue
                draw.rectangle([(10, y), (width - 10, y + 10)], fill=color, outline=(180, 200, 230))
                draw.text((14, y), slot_name[:35], fill=(60, 90, 140))
                y += 14
            else:
                draw.text((10, y), text[:40], fill=(100, 100, 100))
                y += 12
    except ImportError:
        pass  # Pillow ImageDraw not available, return blank

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
```

- [ ] **Step 4: Test thumbnail endpoint**

Run: `curl -s http://localhost:8055/api/resume/templates -o /dev/null -w "%{http_code}"`
Then test thumbnail for first template ID found.

- [ ] **Step 5: Commit**

```bash
cd code && git add db/migrations/031_template_parser_version.sql backend/routes/resume.py && git commit -m "feat: add migration 031 parser_version + template thumbnail endpoint"
```

---

## Task 4: ATS Score in Builder

**Files:**
- Modify: `code/backend/routes/resume.py` (add recipe-based ATS endpoint)
- Create: `code/frontend/src/pages/resume-builder/AtsScoreModal.tsx`
- Modify: `code/frontend/src/pages/resume-builder/ResumeEditor.tsx` (wire callback)
- Modify: `code/frontend/src/api/client.ts` (add API function)

- [ ] **Step 1: Add ATS score endpoint to resume.py**

Add after the thumbnail endpoint in `code/backend/routes/resume.py`:

```python
@bp.route("/api/resume/recipes/<int:recipe_id>/ats-score", methods=["POST"])
def recipe_ats_score(recipe_id):
    """Run ATS scoring on a resolved recipe."""
    from mcp_tools_resume_gen import _resolve_recipe_db

    recipe_row = db.query_one(
        "SELECT recipe, recipe_version FROM resume_recipes WHERE id = %s", (recipe_id,)
    )
    if not recipe_row:
        return jsonify({"error": "Recipe not found"}), 404

    data = request.get_json(silent=True) or {}
    jd_text = data.get("jd_text", "")
    application_id = data.get("application_id")

    # If application_id provided, fetch JD from application
    if application_id and not jd_text:
        app_row = db.query_one(
            "SELECT jd_text FROM applications WHERE id = %s", (application_id,)
        )
        if app_row and app_row.get("jd_text"):
            jd_text = app_row["jd_text"]

    if not jd_text:
        # Score against target roles from profile
        settings = db.query_one("SELECT preferences FROM settings WHERE id = 1")
        prefs = (settings or {}).get("preferences") or {}
        target_roles = prefs.get("target_roles", [])
        if not target_roles:
            return jsonify({"error": "No JD text or target roles provided"}), 400
        jd_text = " ".join(target_roles)

    # Resolve recipe to text
    recipe_json = recipe_row["recipe"]
    version = recipe_row.get("recipe_version", 1)
    resolved = _resolve_recipe_db(recipe_json, version)
    resume_text = _resolved_to_text(resolved)

    # Reuse existing ATS scoring logic
    from routes.resume_tailoring import _extract_keywords
    keywords = _extract_keywords(jd_text)
    matches = {}
    for kw in keywords:
        pattern = re.compile(r"\b" + re.escape(kw) + r"\b", re.IGNORECASE)
        matches[kw] = bool(pattern.search(resume_text))

    found = sum(1 for v in matches.values() if v)
    total = len(matches)
    match_pct = round(found / total * 100, 1) if total else 0
    format_score = 100  # No HTML in recipe-generated text
    ats_score = round(match_pct * 0.8 + format_score * 0.2)

    python_result = {
        "ats_score": ats_score,
        "keyword_matches": matches,
        "match_percentage": match_pct,
        "keywords_found": found,
        "keywords_checked": total,
        "formatting_flags": [],
    }

    def _python_fallback(ctx):
        return {**ctx["python_result"], "analysis_mode": "rule_based"}

    def _ai_handler(ctx):
        from ai_providers import get_provider
        provider = get_provider()
        prompt = f"""Analyze this resume against the job description for ATS compatibility.
Resume (first 3000 chars): {ctx['resume_text'][:3000]}
Job Description (first 3000 chars): {ctx['jd_text'][:3000]}
Python ATS score: {ctx['python_result']['ats_score']}
Return JSON: {{"ai_score": int, "suggestions": [str], "missing_keywords": [str]}}"""
        ai_result = provider.generate(prompt, response_format="json")
        merged = {**ctx["python_result"]}
        if isinstance(ai_result, dict):
            if ai_result.get("ai_score"):
                merged["ats_score"] = round((merged["ats_score"] + ai_result["ai_score"]) / 2)
            merged["suggestions"] = ai_result.get("suggestions", [])
            merged["missing_keywords"] = ai_result.get("missing_keywords", [])
        return {**merged, "analysis_mode": "ai"}

    result = route_inference(
        "recipe_ats_score",
        {"resume_text": resume_text, "jd_text": jd_text, "python_result": python_result},
        _python_fallback,
        _ai_handler,
    )
    return jsonify(result)


def _resolved_to_text(resolved: dict) -> str:
    """Convert a resolved recipe dict to plain text for scoring."""
    parts = []
    for key, val in resolved.items():
        if isinstance(val, str):
            parts.append(val)
        elif isinstance(val, list):
            for item in val:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    parts.append(item.get("text", item.get("name", str(item))))
    return "\n".join(parts)
```

- [ ] **Step 2: Add ATS score API function to client.ts**

Add to `code/frontend/src/api/client.ts`:

```typescript
export interface AtsScoreResult {
  ats_score: number;
  keyword_matches: Record<string, boolean>;
  match_percentage: number;
  keywords_found: number;
  keywords_checked: number;
  formatting_flags: string[];
  suggestions?: string[];
  missing_keywords?: string[];
  analysis_mode: string;
}

export async function recipeAtsScore(
  recipeId: number,
  jdText?: string,
  applicationId?: number
): Promise<AtsScoreResult> {
  const res = await fetch(`${API}/resume/recipes/${recipeId}/ats-score`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ jd_text: jdText, application_id: applicationId }),
  });
  if (!res.ok) throw new Error(`ATS score failed: ${res.status}`);
  return res.json();
}
```

- [ ] **Step 3: Create AtsScoreModal.tsx**

```tsx
// code/frontend/src/pages/resume-builder/AtsScoreModal.tsx
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { recipeAtsScore, AtsScoreResult } from "../../api/client";

interface Props {
  recipeId: number;
  applicationId?: number;
  onClose: () => void;
}

export default function AtsScoreModal({ recipeId, applicationId, onClose }: Props) {
  const [jdText, setJdText] = useState("");
  const [result, setResult] = useState<AtsScoreResult | null>(null);

  const scoreMut = useMutation({
    mutationFn: () => recipeAtsScore(recipeId, jdText || undefined, applicationId),
    onSuccess: (data) => setResult(data),
    onError: (err: Error) => alert(err.message),
  });

  const scoreColor = (score: number) =>
    score >= 80 ? "#22c55e" : score >= 60 ? "#eab308" : "#ef4444";

  return (
    <div
      style={{
        position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)",
        display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000,
      }}
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div style={{
        background: "var(--bg-primary, #fff)", borderRadius: 12, padding: 24,
        width: 560, maxHeight: "80vh", overflow: "auto",
        border: "1px solid var(--border-color, #e5e7eb)",
      }}>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16 }}>
          <h2 style={{ margin: 0 }}>ATS Score</h2>
          <button onClick={onClose} style={{ background: "none", border: "none", fontSize: 20, cursor: "pointer" }}>x</button>
        </div>

        {!result && (
          <>
            <textarea
              value={jdText}
              onChange={(e) => setJdText(e.target.value)}
              placeholder="Paste job description here (or leave blank to score against target roles)"
              rows={8}
              style={{
                width: "100%", padding: 8, borderRadius: 6,
                border: "1px solid var(--border-color, #d1d5db)",
                background: "var(--bg-secondary, #f9fafb)",
                fontFamily: "inherit", resize: "vertical",
              }}
            />
            <button
              onClick={() => scoreMut.mutate()}
              disabled={scoreMut.isPending}
              style={{
                marginTop: 12, padding: "8px 20px", borderRadius: 6,
                background: "#6366f1", color: "#fff", border: "none",
                cursor: scoreMut.isPending ? "wait" : "pointer",
              }}
            >
              {scoreMut.isPending ? "Scoring..." : "Run ATS Score"}
            </button>
          </>
        )}

        {result && (
          <div>
            {/* Score gauge */}
            <div style={{ textAlign: "center", marginBottom: 20 }}>
              <div style={{
                fontSize: 48, fontWeight: 700, color: scoreColor(result.ats_score),
              }}>
                {result.ats_score}
              </div>
              <div style={{ color: "var(--text-secondary, #6b7280)" }}>
                {result.keywords_found}/{result.keywords_checked} keywords matched
                ({result.match_percentage}%)
              </div>
              <div style={{ fontSize: 12, color: "var(--text-tertiary, #9ca3af)" }}>
                {result.analysis_mode === "ai" ? "AI-enhanced" : "Rule-based"} analysis
              </div>
            </div>

            {/* Keyword checklist */}
            <h3 style={{ marginBottom: 8 }}>Keywords</h3>
            <div style={{ maxHeight: 200, overflow: "auto", marginBottom: 16 }}>
              {Object.entries(result.keyword_matches).map(([kw, found]) => (
                <div key={kw} style={{
                  display: "flex", alignItems: "center", gap: 8, padding: "2px 0",
                }}>
                  <span style={{ color: found ? "#22c55e" : "#ef4444" }}>
                    {found ? "\u2713" : "\u2717"}
                  </span>
                  <span>{kw}</span>
                </div>
              ))}
            </div>

            {/* AI suggestions */}
            {result.suggestions && result.suggestions.length > 0 && (
              <>
                <h3 style={{ marginBottom: 8 }}>Suggestions</h3>
                <ul style={{ paddingLeft: 20 }}>
                  {result.suggestions.map((s, i) => <li key={i}>{s}</li>)}
                </ul>
              </>
            )}

            <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
              <button
                onClick={() => { setResult(null); }}
                style={{
                  padding: "8px 16px", borderRadius: 6, border: "1px solid var(--border-color, #d1d5db)",
                  background: "var(--bg-secondary, #f9fafb)", cursor: "pointer",
                }}
              >
                Re-score
              </button>
              <button onClick={onClose} style={{
                padding: "8px 16px", borderRadius: 6, background: "#6366f1",
                color: "#fff", border: "none", cursor: "pointer",
              }}>
                Close
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Wire ATS score into ResumeEditor.tsx**

In `code/frontend/src/pages/resume-builder/ResumeEditor.tsx`, replace the `onAtsScore={() => {/* Phase 4 */}}` stub:

```tsx
// Add state:
const [showAtsScore, setShowAtsScore] = useState(false);

// Replace stub:
onAtsScore={() => setShowAtsScore(true)}

// Add modal render (before closing div):
{showAtsScore && (
  <AtsScoreModal
    recipeId={recipeId}
    applicationId={recipe?.application_id}
    onClose={() => setShowAtsScore(false)}
  />
)}
```

- [ ] **Step 5: Test ATS endpoint manually**

Run: `cd code && docker compose up -d --build backend` then test via curl or frontend.

- [ ] **Step 6: Commit**

```bash
cd code && git add backend/routes/resume.py frontend/src/pages/resume-builder/AtsScoreModal.tsx frontend/src/pages/resume-builder/ResumeEditor.tsx frontend/src/api/client.ts && git commit -m "feat: add ATS score modal in resume builder"
```

---

## Task 5: AI Review Endpoint + Panel

**Files:**
- Modify: `code/backend/routes/resume.py` (add ai-review endpoint)
- Create: `code/frontend/src/pages/resume-builder/AiReviewPanel.tsx`
- Modify: `code/frontend/src/pages/resume-builder/ResumeEditor.tsx` (wire callback)
- Modify: `code/frontend/src/api/client.ts` (add API function)

- [ ] **Step 1: Add AI review endpoint to resume.py**

```python
@bp.route("/api/resume/recipes/<int:recipe_id>/ai-review", methods=["POST"])
def recipe_ai_review(recipe_id):
    """AI-powered resume review: generic quality + per-target-role scoring."""
    from mcp_tools_resume_gen import _resolve_recipe_db

    recipe_row = db.query_one(
        "SELECT recipe, recipe_version FROM resume_recipes WHERE id = %s", (recipe_id,)
    )
    if not recipe_row:
        return jsonify({"error": "Recipe not found"}), 404

    data = request.get_json(silent=True) or {}
    recipe_json = recipe_row["recipe"]
    version = recipe_row.get("recipe_version", 1)
    resolved = _resolve_recipe_db(recipe_json, version)
    resume_text = _resolved_to_text(resolved)

    # Get target roles from profile
    settings = db.query_one("SELECT preferences FROM settings WHERE id = 1")
    prefs = (settings or {}).get("preferences") or {}
    target_roles = prefs.get("target_roles", [])

    # Python fallback: rule-based checks
    def _python_review(resume_text, resolved, target_roles):
        feedback = []
        strengths = []

        # Check bullet counts per job
        for key, val in resolved.items():
            if key.startswith("experience") or "JOB" in key.upper():
                if isinstance(val, list):
                    bullet_count = len([b for b in val if isinstance(b, (str, dict))])
                    if bullet_count < 3:
                        feedback.append({
                            "section": key, "issue": f"Only {bullet_count} bullets, add more",
                            "severity": "medium",
                        })
                    elif bullet_count >= 5:
                        strengths.append(f"Good bullet coverage in {key}")

        # Metrics scan
        metrics_re = re.compile(r"\$[\d,.]+[MKBmkb]?|\d+%|\d+x|\d[\d,]*\+?\s*(?:users|employees|team|engineers|developers)")
        total_bullets = 0
        metrics_bullets = 0
        for key, val in resolved.items():
            items = val if isinstance(val, list) else [val]
            for item in items:
                text = item if isinstance(item, str) else (item.get("text", "") if isinstance(item, dict) else "")
                if text and len(text) > 30:  # Likely a bullet
                    total_bullets += 1
                    if metrics_re.search(text):
                        metrics_bullets += 1

        if total_bullets > 0:
            pct = round(metrics_bullets / total_bullets * 100)
            if pct < 50:
                feedback.append({
                    "section": "overall", "issue": f"Only {pct}% of bullets have metrics",
                    "severity": "high",
                })
            else:
                strengths.append(f"{pct}% of bullets include metrics")

        # Length check
        word_count = len(resume_text.split())
        if word_count > 800:
            feedback.append({
                "section": "overall", "issue": f"Resume is {word_count} words, consider trimming to under 700",
                "severity": "low",
            })

        # Score: start at 70, deduct for issues, add for strengths
        score = 70
        score -= sum(5 for f in feedback if f["severity"] == "high")
        score -= sum(3 for f in feedback if f["severity"] == "medium")
        score -= sum(1 for f in feedback if f["severity"] == "low")
        score += len(strengths) * 2
        score = max(0, min(100, score))

        # Target role scoring (keyword overlap)
        role_scores = []
        for role in target_roles:
            role_lower = role.lower()
            role_words = set(role_lower.split())
            resume_lower = resume_text.lower()
            overlap = sum(1 for w in role_words if w in resume_lower)
            role_score = min(100, 50 + overlap * 15)
            role_scores.append({
                "role": role, "score": role_score,
                "gaps": [], "suggestions": [],
            })

        return {
            "generic": {"score": score, "feedback": feedback, "strengths": strengths},
            "target_roles": role_scores,
        }

    python_result = _python_review(resume_text, resolved, target_roles)

    def _python_fallback(ctx):
        return {**ctx["python_result"], "analysis_mode": "rule_based"}

    def _ai_handler(ctx):
        from ai_providers import get_provider
        provider = get_provider()
        roles_str = ", ".join(ctx["target_roles"]) if ctx["target_roles"] else "general"
        prompt = f"""Review this resume for quality and fit.

Resume text (first 4000 chars):
{ctx['resume_text'][:4000]}

Target roles: {roles_str}

Return JSON with this exact structure:
{{
  "generic": {{
    "score": <0-100>,
    "feedback": [{{"section": "<section>", "issue": "<issue>", "severity": "<high|medium|low>"}}],
    "strengths": ["<strength>"]
  }},
  "target_roles": [
    {{"role": "<role>", "score": <0-100>, "gaps": ["<gap>"], "suggestions": ["<suggestion>"]}}
  ]
}}

Score criteria: metrics presence, bullet strength, formatting, readability, role alignment.
Be specific in feedback: name the section and the exact issue."""
        ai_result = provider.generate(prompt, response_format="json")
        if isinstance(ai_result, dict) and "generic" in ai_result:
            return {**ai_result, "analysis_mode": "ai"}
        return {**ctx["python_result"], "analysis_mode": "rule_based"}

    result = route_inference(
        "recipe_ai_review",
        {"resume_text": resume_text, "target_roles": target_roles, "python_result": python_result},
        _python_fallback,
        _ai_handler,
    )
    return jsonify(result)
```

- [ ] **Step 2: Add API function to client.ts**

```typescript
export interface AiReviewResult {
  generic: {
    score: number;
    feedback: Array<{ section: string; issue: string; severity: string }>;
    strengths: string[];
  };
  target_roles: Array<{
    role: string;
    score: number;
    gaps: string[];
    suggestions: string[];
  }>;
  analysis_mode: string;
}

export async function recipeAiReview(recipeId: number): Promise<AiReviewResult> {
  const res = await fetch(`${API}/resume/recipes/${recipeId}/ai-review`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: "{}",
  });
  if (!res.ok) throw new Error(`AI review failed: ${res.status}`);
  return res.json();
}
```

- [ ] **Step 3: Create AiReviewPanel.tsx**

```tsx
// code/frontend/src/pages/resume-builder/AiReviewPanel.tsx
import { useMutation } from "@tanstack/react-query";
import { recipeAiReview, AiReviewResult } from "../../api/client";
import { useState } from "react";

interface Props {
  recipeId: number;
  onClose: () => void;
}

export default function AiReviewPanel({ recipeId, onClose }: Props) {
  const [result, setResult] = useState<AiReviewResult | null>(null);

  const reviewMut = useMutation({
    mutationFn: () => recipeAiReview(recipeId),
    onSuccess: (data) => setResult(data),
    onError: (err: Error) => alert(err.message),
  });

  const sevColor = (s: string) =>
    s === "high" ? "#ef4444" : s === "medium" ? "#eab308" : "#6366f1";
  const scoreColor = (score: number) =>
    score >= 80 ? "#22c55e" : score >= 60 ? "#eab308" : "#ef4444";

  return (
    <div style={{
      position: "fixed", right: 0, top: 0, bottom: 0, width: 380,
      background: "var(--bg-primary, #fff)", borderLeft: "1px solid var(--border-color, #e5e7eb)",
      padding: 20, overflow: "auto", zIndex: 999, boxShadow: "-2px 0 8px rgba(0,0,0,0.1)",
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16 }}>
        <h2 style={{ margin: 0, fontSize: 18 }}>AI Review</h2>
        <button onClick={onClose} style={{ background: "none", border: "none", fontSize: 18, cursor: "pointer" }}>x</button>
      </div>

      {!result && (
        <button
          onClick={() => reviewMut.mutate()}
          disabled={reviewMut.isPending}
          style={{
            width: "100%", padding: "10px 20px", borderRadius: 6,
            background: "#6366f1", color: "#fff", border: "none",
            cursor: reviewMut.isPending ? "wait" : "pointer",
          }}
        >
          {reviewMut.isPending ? "Analyzing..." : "Run AI Review"}
        </button>
      )}

      {result && (
        <>
          {/* Overall score */}
          <div style={{ textAlign: "center", marginBottom: 20 }}>
            <div style={{ fontSize: 42, fontWeight: 700, color: scoreColor(result.generic.score) }}>
              {result.generic.score}
            </div>
            <div style={{ fontSize: 12, color: "var(--text-tertiary, #9ca3af)" }}>
              {result.analysis_mode === "ai" ? "AI-enhanced" : "Rule-based"}
            </div>
          </div>

          {/* Strengths */}
          {result.generic.strengths.length > 0 && (
            <div style={{ marginBottom: 16 }}>
              <h3 style={{ fontSize: 14, marginBottom: 8 }}>Strengths</h3>
              {result.generic.strengths.map((s, i) => (
                <div key={i} style={{ padding: "4px 0", color: "#22c55e", fontSize: 13 }}>
                  + {s}
                </div>
              ))}
            </div>
          )}

          {/* Feedback */}
          {result.generic.feedback.length > 0 && (
            <div style={{ marginBottom: 16 }}>
              <h3 style={{ fontSize: 14, marginBottom: 8 }}>Feedback</h3>
              {result.generic.feedback.map((f, i) => (
                <div key={i} style={{
                  padding: 8, marginBottom: 6, borderRadius: 6,
                  border: `1px solid ${sevColor(f.severity)}20`,
                  background: `${sevColor(f.severity)}08`,
                }}>
                  <div style={{ fontSize: 11, color: sevColor(f.severity), fontWeight: 600 }}>
                    {f.severity.toUpperCase()} - {f.section}
                  </div>
                  <div style={{ fontSize: 13 }}>{f.issue}</div>
                </div>
              ))}
            </div>
          )}

          {/* Target role scores */}
          {result.target_roles.length > 0 && (
            <div style={{ marginBottom: 16 }}>
              <h3 style={{ fontSize: 14, marginBottom: 8 }}>Target Role Fit</h3>
              {result.target_roles.map((r, i) => (
                <div key={i} style={{
                  padding: 10, marginBottom: 8, borderRadius: 6,
                  border: "1px solid var(--border-color, #e5e7eb)",
                }}>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span style={{ fontWeight: 600, fontSize: 13 }}>{r.role}</span>
                    <span style={{ fontWeight: 700, color: scoreColor(r.score) }}>{r.score}</span>
                  </div>
                  {r.gaps.map((g, j) => (
                    <div key={j} style={{ fontSize: 12, color: "#ef4444", marginTop: 4 }}>- {g}</div>
                  ))}
                  {r.suggestions.map((s, j) => (
                    <div key={j} style={{ fontSize: 12, color: "#6366f1", marginTop: 2 }}>+ {s}</div>
                  ))}
                </div>
              ))}
            </div>
          )}

          <button
            onClick={() => { setResult(null); reviewMut.mutate(); }}
            style={{
              width: "100%", padding: "8px 16px", borderRadius: 6,
              border: "1px solid var(--border-color, #d1d5db)",
              background: "var(--bg-secondary, #f9fafb)", cursor: "pointer",
            }}
          >
            Re-analyze
          </button>
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Wire AI Review into ResumeEditor.tsx**

Replace `onAiReview={() => {/* Phase 4 */}}` stub:

```tsx
// Add state:
const [showAiReview, setShowAiReview] = useState(false);

// Replace stub:
onAiReview={() => setShowAiReview(true)}

// Add panel render:
{showAiReview && (
  <AiReviewPanel recipeId={recipeId} onClose={() => setShowAiReview(false)} />
)}
```

Also in `EditorToolbar.tsx`, remove the `opacity: 0.5` and "Coming soon" from the AI Review button.

- [ ] **Step 5: Build frontend and test**

Run: `cd code && docker compose up -d --build frontend`

- [ ] **Step 6: Commit**

```bash
cd code && git add backend/routes/resume.py frontend/src/pages/resume-builder/AiReviewPanel.tsx frontend/src/pages/resume-builder/ResumeEditor.tsx frontend/src/pages/resume-builder/EditorToolbar.tsx frontend/src/api/client.ts && git commit -m "feat: add AI review panel with quality score + target role fit"
```

---

## Task 6: AI Generate-Slot Endpoint + Modal

**Files:**
- Modify: `code/backend/routes/resume.py` (add endpoint)
- Create: `code/frontend/src/pages/resume-builder/AiGenerateModal.tsx`
- Modify: `code/frontend/src/pages/resume-builder/ResumeEditor.tsx`
- Modify: `code/frontend/src/pages/resume-builder/EditorToolbar.tsx`
- Modify: `code/frontend/src/api/client.ts`

- [ ] **Step 1: Add generate-slot endpoint**

Add to `code/backend/routes/resume.py`:

```python
@bp.route("/api/resume/recipes/<int:recipe_id>/ai-generate-slot", methods=["POST"])
def recipe_ai_generate_slot(recipe_id):
    """Generate content for a specific recipe slot (bullet, summary, highlight, job_intro)."""
    data = request.get_json(silent=True) or {}
    slot_type = data.get("slot_type", "bullet")
    context = data.get("context", {})
    job_id = context.get("job_id")
    existing = context.get("existing_bullets", [])
    target_role = context.get("target_role", "")
    instructions = context.get("instructions", "")

    # Python fallback: surface unused content from DB
    def _python_fallback(ctx):
        suggestions = []
        st = ctx.get("slot_type", "bullet")
        jid = ctx.get("job_id")

        if st == "bullet" and jid:
            # Find bullets for this job not already in the recipe
            existing_texts = set(ctx.get("existing_bullets", []))
            rows = db.query_all(
                "SELECT id, text FROM bullets WHERE career_history_id = %s ORDER BY sort_order",
                (jid,),
            )
            for row in rows:
                if row["text"] not in existing_texts:
                    suggestions.append({
                        "text": row["text"], "confidence": 0.7,
                        "source": "existing_bullet", "bullet_id": row["id"],
                    })

        elif st == "summary":
            rows = db.query_all("SELECT id, text, variant FROM summary_variants ORDER BY id")
            for row in rows:
                suggestions.append({
                    "text": row["text"], "confidence": 0.7,
                    "source": "summary_variant", "variant": row.get("variant"),
                })

        elif st == "highlight":
            # Pull highest-metric bullets across all jobs
            rows = db.query_all(
                """SELECT b.id, b.text, ch.company_name
                   FROM bullets b JOIN career_history ch ON b.career_history_id = ch.id
                   WHERE b.text ~ '\\$[\\d,.]+|\\d+%|\\d+x'
                   ORDER BY b.id LIMIT 10"""
            )
            for row in rows:
                suggestions.append({
                    "text": row["text"], "confidence": 0.6,
                    "source": f"bullet from {row['company_name']}",
                })

        elif st == "job_intro" and jid:
            row = db.query_one(
                "SELECT intro_text FROM career_history WHERE id = %s", (jid,)
            )
            if row and row.get("intro_text"):
                intro = row["intro_text"]
                if isinstance(intro, dict):
                    intro = intro.get("text", str(intro))
                suggestions.append({
                    "text": intro, "confidence": 0.8, "source": "career_history",
                })

        return {"suggestions": suggestions[:5], "analysis_mode": "rule_based"}

    def _ai_handler(ctx):
        from ai_providers import get_provider
        provider = get_provider()

        # Build context for AI
        job_context = ""
        if ctx.get("job_id"):
            job_row = db.query_one(
                "SELECT company_name, title, start_date, end_date, intro_text FROM career_history WHERE id = %s",
                (ctx["job_id"],),
            )
            if job_row:
                job_context = f"Company: {job_row['company_name']}, Role: {job_row['title']}"

        # Get voice rules
        voice_rows = db.query_all(
            "SELECT rule_text FROM voice_rules WHERE is_active = true AND category = 'resume_rule' LIMIT 10"
        )
        voice_context = "\n".join(r["rule_text"] for r in voice_rows)

        prompt = f"""Generate {ctx['slot_type']} content for a resume.
Job context: {job_context}
Target role: {ctx.get('target_role', 'general')}
User instructions: {ctx.get('instructions', 'none')}
Existing content to avoid duplicating: {json.dumps(ctx.get('existing_bullets', [])[:5])}

Voice rules:
{voice_context}

Return JSON: {{"suggestions": [{{"text": "<content>", "confidence": <0-1>, "source": "generated"}}]}}
Generate 3-5 suggestions. Each bullet MUST include a concrete metric or measurable outcome.
Use active voice, start with strong action verbs."""

        ai_result = provider.generate(prompt, response_format="json")
        if isinstance(ai_result, dict) and "suggestions" in ai_result:
            # Voice check each suggestion
            checked = []
            for s in ai_result["suggestions"]:
                # Quick voice check (ban word scan)
                text = s.get("text", "")
                ban_rows = db.query_all(
                    "SELECT rule_text FROM voice_rules WHERE is_active = true AND category = 'banned_word' LIMIT 50"
                )
                banned = [r["rule_text"].lower() for r in ban_rows]
                clean = not any(b in text.lower() for b in banned)
                if clean:
                    checked.append(s)
            return {"suggestions": checked[:5], "analysis_mode": "ai"}
        return ctx.get("fallback_result", {"suggestions": [], "analysis_mode": "rule_based"})

    fallback_result = _python_fallback({
        "slot_type": slot_type, "job_id": job_id,
        "existing_bullets": existing,
    })

    result = route_inference(
        "recipe_generate_slot",
        {
            "slot_type": slot_type, "job_id": job_id,
            "existing_bullets": existing, "target_role": target_role,
            "instructions": instructions, "fallback_result": fallback_result,
        },
        lambda ctx: {**fallback_result, "analysis_mode": "rule_based"},
        _ai_handler,
    )
    return jsonify(result)
```

- [ ] **Step 2: Add API function to client.ts**

```typescript
export interface GenerateSlotResult {
  suggestions: Array<{
    text: string;
    confidence: number;
    source: string;
    bullet_id?: number;
  }>;
  analysis_mode: string;
}

export async function recipeGenerateSlot(
  recipeId: number,
  slotType: string,
  context: { job_id?: number; existing_bullets?: string[]; target_role?: string; instructions?: string }
): Promise<GenerateSlotResult> {
  const res = await fetch(`${API}/resume/recipes/${recipeId}/ai-generate-slot`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ slot_type: slotType, context }),
  });
  if (!res.ok) throw new Error(`Generate slot failed: ${res.status}`);
  return res.json();
}
```

- [ ] **Step 3: Create AiGenerateModal.tsx**

```tsx
// code/frontend/src/pages/resume-builder/AiGenerateModal.tsx
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { recipeGenerateSlot, GenerateSlotResult } from "../../api/client";

interface Props {
  recipeId: number;
  slotType: string;
  jobId?: number;
  existingBullets?: string[];
  onSelect: (text: string) => void;
  onClose: () => void;
}

export default function AiGenerateModal({
  recipeId, slotType, jobId, existingBullets, onSelect, onClose,
}: Props) {
  const [instructions, setInstructions] = useState("");
  const [result, setResult] = useState<GenerateSlotResult | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [editText, setEditText] = useState("");

  const genMut = useMutation({
    mutationFn: () => recipeGenerateSlot(recipeId, slotType, {
      job_id: jobId, existing_bullets: existingBullets, instructions,
    }),
    onSuccess: (data) => setResult(data),
    onError: (err: Error) => alert(err.message),
  });

  return (
    <div
      style={{
        position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)",
        display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000,
      }}
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div style={{
        background: "var(--bg-primary, #fff)", borderRadius: 12, padding: 24,
        width: 520, maxHeight: "80vh", overflow: "auto",
        border: "1px solid var(--border-color, #e5e7eb)",
      }}>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16 }}>
          <h2 style={{ margin: 0 }}>Generate {slotType}</h2>
          <button onClick={onClose} style={{ background: "none", border: "none", fontSize: 20, cursor: "pointer" }}>x</button>
        </div>

        {/* Instructions */}
        <textarea
          value={instructions}
          onChange={(e) => setInstructions(e.target.value)}
          placeholder="Optional: specific guidance (e.g., 'emphasize cost savings', 'focus on leadership')"
          rows={2}
          style={{
            width: "100%", padding: 8, borderRadius: 6, marginBottom: 12,
            border: "1px solid var(--border-color, #d1d5db)",
            background: "var(--bg-secondary, #f9fafb)", fontFamily: "inherit",
          }}
        />

        <button
          onClick={() => { setResult(null); setSelected(null); genMut.mutate(); }}
          disabled={genMut.isPending}
          style={{
            padding: "8px 20px", borderRadius: 6, background: "#6366f1",
            color: "#fff", border: "none", cursor: genMut.isPending ? "wait" : "pointer",
            marginBottom: 16,
          }}
        >
          {genMut.isPending ? "Generating..." : result ? "Regenerate" : "Generate"}
        </button>

        {/* Suggestions */}
        {result && result.suggestions.map((s, i) => (
          <div
            key={i}
            onClick={() => { setSelected(i); setEditText(s.text); }}
            style={{
              padding: 12, marginBottom: 8, borderRadius: 8, cursor: "pointer",
              border: `2px solid ${selected === i ? "#6366f1" : "var(--border-color, #e5e7eb)"}`,
              background: selected === i ? "#6366f110" : "var(--bg-secondary, #f9fafb)",
            }}
          >
            <div style={{ fontSize: 13, marginBottom: 4 }}>{s.text}</div>
            <div style={{ fontSize: 11, color: "var(--text-tertiary, #9ca3af)", display: "flex", gap: 12 }}>
              <span>Source: {s.source}</span>
              <span>Confidence: {Math.round(s.confidence * 100)}%</span>
            </div>
          </div>
        ))}

        {/* Edit selected */}
        {selected !== null && (
          <div style={{ marginTop: 12 }}>
            <textarea
              value={editText}
              onChange={(e) => setEditText(e.target.value)}
              rows={3}
              style={{
                width: "100%", padding: 8, borderRadius: 6,
                border: "1px solid #6366f1", fontFamily: "inherit",
              }}
            />
            <button
              onClick={() => { onSelect(editText); onClose(); }}
              style={{
                marginTop: 8, padding: "8px 20px", borderRadius: 6,
                background: "#22c55e", color: "#fff", border: "none", cursor: "pointer",
              }}
            >
              Insert
            </button>
          </div>
        )}

        {result && result.suggestions.length === 0 && (
          <div style={{ padding: 16, textAlign: "center", color: "var(--text-secondary, #6b7280)" }}>
            No suggestions available. Try different instructions or add more content to your knowledge base.
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Wire generate-slot into ResumeEditor.tsx and EditorToolbar.tsx**

Add "AI Generate" button to toolbar and state management for the modal. Wire `onSelect` to insert text into the appropriate recipe slot.

- [ ] **Step 5: Build and test**

Run: `cd code && docker compose up -d --build backend frontend`

- [ ] **Step 6: Commit**

```bash
cd code && git add backend/routes/resume.py frontend/src/pages/resume-builder/AiGenerateModal.tsx frontend/src/pages/resume-builder/ResumeEditor.tsx frontend/src/pages/resume-builder/EditorToolbar.tsx frontend/src/api/client.ts && git commit -m "feat: add AI generate-slot modal for bullet/summary generation"
```

---

## Task 7: Best-Picks Endpoint + Panel

**Files:**
- Modify: `code/backend/routes/resume.py`
- Create: `code/frontend/src/pages/resume-builder/BestPicksPanel.tsx`
- Modify: `code/frontend/src/api/client.ts`

- [ ] **Step 1: Add best-picks endpoint**

Add to `code/backend/routes/resume.py`:

```python
@bp.route("/api/resume/recipes/<int:recipe_id>/best-picks", methods=["POST"])
def recipe_best_picks(recipe_id):
    """Rank bullets and jobs by relevance to a JD."""
    data = request.get_json(silent=True) or {}
    jd_text = data.get("jd_text", "")
    application_id = data.get("application_id")
    limit = data.get("limit", 10)

    if application_id and not jd_text:
        app_row = db.query_one("SELECT jd_text FROM applications WHERE id = %s", (application_id,))
        if app_row and app_row.get("jd_text"):
            jd_text = app_row["jd_text"]

    if not jd_text:
        return jsonify({"error": "No JD text or application_id provided"}), 400

    # Get all bullets with their job info
    all_bullets = db.query_all(
        """SELECT b.id, b.text, b.career_history_id, ch.company_name, ch.title
           FROM bullets b
           JOIN career_history ch ON b.career_history_id = ch.id
           ORDER BY ch.start_date DESC, b.sort_order"""
    )

    # Get all jobs
    all_jobs = db.query_all(
        "SELECT id, company_name, title, start_date, end_date FROM career_history ORDER BY start_date DESC"
    )

    # Python fallback: keyword overlap scoring
    from routes.resume_tailoring import _extract_keywords
    jd_keywords = _extract_keywords(jd_text)
    jd_kw_set = set(k.lower() for k in jd_keywords)

    def _score_text(text):
        words = set(text.lower().split())
        overlap = words & jd_kw_set
        return len(overlap) / max(len(jd_kw_set), 1)

    ranked_bullets = []
    for b in all_bullets:
        score = _score_text(b["text"])
        matched = [kw for kw in jd_keywords if kw.lower() in b["text"].lower()]
        ranked_bullets.append({
            "bullet_id": b["id"], "text": b["text"], "relevance": round(score, 3),
            "job": b["company_name"], "career_history_id": b["career_history_id"],
            "matched_keywords": matched,
        })
    ranked_bullets.sort(key=lambda x: x["relevance"], reverse=True)

    ranked_jobs = []
    for j in all_jobs:
        job_bullets = [b for b in all_bullets if b["career_history_id"] == j["id"]]
        avg_score = (sum(_score_text(b["text"]) for b in job_bullets) / max(len(job_bullets), 1))
        ranked_jobs.append({
            "career_history_id": j["id"], "company": j["company_name"],
            "title": j["title"], "relevance": round(avg_score, 3), "reason": "",
        })
    ranked_jobs.sort(key=lambda x: x["relevance"], reverse=True)

    # Suggest missing skills
    all_skills = db.query_all("SELECT name FROM skills")
    skill_names = set(s["name"].lower() for s in all_skills)
    suggested_skills = [kw for kw in jd_keywords if kw.lower() not in skill_names][:10]

    python_result = {
        "ranked_bullets": ranked_bullets[:limit],
        "ranked_jobs": ranked_jobs[:5],
        "suggested_skills": suggested_skills,
    }

    def _python_fallback(ctx):
        return {**ctx["python_result"], "analysis_mode": "rule_based"}

    def _ai_handler(ctx):
        from ai_providers import get_provider
        provider = get_provider()
        # Send top bullets + JD for semantic ranking
        top_bullets = [{"id": b["bullet_id"], "text": b["text"], "job": b["job"]}
                       for b in ctx["python_result"]["ranked_bullets"][:20]]
        prompt = f"""Rank these resume bullets by relevance to the job description.

JD (first 2000 chars): {ctx['jd_text'][:2000]}

Bullets: {json.dumps(top_bullets)}

Return JSON: {{
  "ranked_bullet_ids": [<ids in order of relevance>],
  "job_reasons": {{<career_history_id>: "<reason for relevance>"}},
  "suggested_skills": ["<skill not in resume but in JD>"]
}}"""
        ai_result = provider.generate(prompt, response_format="json")
        if isinstance(ai_result, dict) and "ranked_bullet_ids" in ai_result:
            # Reorder bullets by AI ranking
            id_order = {bid: i for i, bid in enumerate(ai_result["ranked_bullet_ids"])}
            reranked = sorted(
                ctx["python_result"]["ranked_bullets"],
                key=lambda b: id_order.get(b["bullet_id"], 999),
            )
            # Add reasons to jobs
            reasons = ai_result.get("job_reasons", {})
            jobs = ctx["python_result"]["ranked_jobs"]
            for j in jobs:
                j["reason"] = reasons.get(str(j["career_history_id"]), "")
            return {
                "ranked_bullets": reranked[:ctx.get("limit", 10)],
                "ranked_jobs": jobs,
                "suggested_skills": ai_result.get("suggested_skills", ctx["python_result"]["suggested_skills"]),
                "analysis_mode": "ai",
            }
        return {**ctx["python_result"], "analysis_mode": "rule_based"}

    result = route_inference(
        "recipe_best_picks",
        {"jd_text": jd_text, "python_result": python_result, "limit": limit},
        _python_fallback,
        _ai_handler,
    )
    return jsonify(result)
```

- [ ] **Step 2: Add API function + BestPicksPanel.tsx frontend**

Similar pattern to AiReviewPanel: JD input area, ranked bullet list with relevance bars, drag/click to insert into recipe.

- [ ] **Step 3: Wire into ContentPickerModal or toolbar**

Add "Best Picks" tab/button in the content picker modal that shows JD-ranked results.

- [ ] **Step 4: Build and test**

Run: `cd code && docker compose up -d --build backend frontend`

- [ ] **Step 5: Commit**

```bash
cd code && git add backend/routes/resume.py frontend/src/pages/resume-builder/BestPicksPanel.tsx frontend/src/api/client.ts frontend/src/pages/resume-builder/ContentPickerModal.tsx && git commit -m "feat: add best-picks endpoint for JD-based bullet ranking"
```

---

## Task 8: Template Browser

**Files:**
- Create: `code/frontend/src/pages/resumes/TemplatesBrowser.tsx`
- Create: `code/frontend/src/pages/resumes/TemplateDetail.tsx`
- Modify: `code/frontend/src/pages/resumes/Resumes.tsx` (add Templates tab)
- Modify: `code/frontend/src/api/client.ts`

- [ ] **Step 1: Add API functions for templates**

```typescript
export interface TemplateListItem {
  id: number;
  name: string;
  template_type: string;
  slot_count: number;
  parser_version: string;
  created_at: string;
  recipe_count: number;
  has_thumbnail: boolean;
}

export async function listTemplates(): Promise<TemplateListItem[]> {
  const res = await fetch(`${API}/resume/templates`);
  if (!res.ok) throw new Error(`List templates failed: ${res.status}`);
  const data = await res.json();
  return data.templates || data;
}

export function templateThumbnailUrl(templateId: number): string {
  return `${API}/resume/templates/${templateId}/thumbnail`;
}
```

- [ ] **Step 2: Create TemplatesBrowser.tsx**

Card grid with thumbnail images, template name, slot count, recipe count. Upload button triggers file input + `POST /api/resume/templates/upload`. Delete button with confirmation.

- [ ] **Step 3: Create TemplateDetail.tsx**

Click-through from card showing full slot map, formatting metadata, linked recipes. Read-only.

- [ ] **Step 4: Add Templates tab to Resumes.tsx**

Add a tab bar at the top of the Resumes page: "Recipes" | "Templates". Toggle between existing recipe list and new TemplatesBrowser.

- [ ] **Step 5: Build and test**

Run: `cd code && docker compose up -d --build frontend`

- [ ] **Step 6: Commit**

```bash
cd code && git add frontend/src/pages/resumes/TemplatesBrowser.tsx frontend/src/pages/resumes/TemplateDetail.tsx frontend/src/pages/resumes/Resumes.tsx frontend/src/api/client.ts && git commit -m "feat: add template browser with thumbnails on Resumes page"
```

---

## Task 9: Wire Parser into Onboard Pipeline

**Files:**
- Modify: `code/backend/routes/onboard.py` (use new parser)
- Modify: `code/utils/templatize_resume.py` (delegate to new modules)

- [ ] **Step 1: Update templatize_resume.py to use new parser**

Refactor `templatize()` function to delegate to `resume_parser.parse_resume_structure()` + `template_builder.build_template()` while keeping the old V31/V32 path as fallback:

```python
def templatize(input_path, output_docx, output_map, layout_name="auto"):
    """Templatize a resume. Uses general-purpose parser for 'auto' layout,
    falls back to legacy V31/V32 for explicitly named layouts."""
    if layout_name in ("v31", "v32"):
        return _legacy_templatize(input_path, output_docx, output_map, layout_name)

    # Use new general-purpose parser
    from utils.template_builder import build_template
    return build_template(input_path, output_docx, output_map, layout=layout_name)
```

Move the existing templatize logic into `_legacy_templatize()`.

- [ ] **Step 2: Update onboard.py _build_recipe_slots**

Update `_build_recipe_slots()` at line 153 to work with the new template_map format from `template_builder.py`. The new format stores `type`, `original_text`, and `formatting` per slot instead of the old flat format.

- [ ] **Step 3: Test with a known resume upload**

Run the upload flow with `Archived/Originals/Stephen_Salaka_Resume_v32.docx` via the frontend or API.

- [ ] **Step 4: Commit**

```bash
cd code && git add utils/templatize_resume.py backend/routes/onboard.py && git commit -m "feat: wire general-purpose parser into onboard pipeline"
```

---

## Task 10: Fix Synopsis Dict Extraction Bug

**Files:**
- Modify: `code/utils/generate_resume.py`

- [ ] **Step 1: Find and fix the synopsis resolution**

In `code/utils/generate_resume.py`, the `resolve_recipe()` function (line 261) resolves career_history refs. When intro_text is stored as a dict (from v1 import), it returns the dict instead of the string. Fix:

```python
# In the resolution loop, after fetching career_history:
if isinstance(value, dict):
    value = value.get("text", str(value))
```

- [ ] **Step 2: Test with a recipe that has synopsis refs**

- [ ] **Step 3: Commit**

```bash
cd code && git add utils/generate_resume.py && git commit -m "fix: handle dict-typed synopsis in recipe resolution"
```

---

## Task 11: E2E Resume Test Script

**Files:**
- Create: `local_code/e2e_resume_test.py`

- [ ] **Step 1: Create the E2E test script**

```python
# local_code/e2e_resume_test.py
"""End-to-end resume pipeline validation.

For each .docx resume:
1. Upload via API (parse -> templatize -> recipe)
2. Generate .docx from recipe
3. Gate 1: Content fidelity (>95% text match)
4. Gate 2: Layout fidelity (structural + formatting comparison)
"""

import sys
import json
import requests
import tempfile
from pathlib import Path
from difflib import SequenceMatcher
from docx import Document

API = "http://localhost:8055/api"

# Directories to scan for resumes
RESUME_DIRS = [
    Path("Archived/Originals"),
    Path("Imports/Resumes"),
]

# Files to skip (not resumes)
SKIP_PATTERNS = [
    "Knowledge_Base", "Work_History", "Cover_Letter", "Campaign",
    "Alternative Job", "Successful ways", "Follow Up", "Posting Strategy",
    "Prompt for", "Overview", "Recommended steps", "Example Follow",
    "Sample Client", "Rationale", "Requirements", "Stuff",
]


def is_resume(path: Path) -> bool:
    """Filter to only actual resume .docx files."""
    name = path.stem
    return not any(skip in name for skip in SKIP_PATTERNS)


def extract_text(docx_path: str) -> str:
    """Extract normalized text from a .docx."""
    doc = Document(docx_path)
    text = "\n".join(p.text.strip() for p in doc.paragraphs if p.text.strip())
    # Normalize quotes
    text = text.replace("\u2018", "'").replace("\u2019", "'")
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    return text


def extract_structure(docx_path: str) -> list:
    """Extract structural info (paragraph count, bold runs, font sizes)."""
    doc = Document(docx_path)
    structure = []
    for p in doc.paragraphs:
        if not p.text.strip():
            continue
        runs_info = []
        for r in p.runs:
            runs_info.append({
                "bold": bool(r.bold),
                "italic": bool(r.italic),
                "font_size": r.font.size.pt if r.font.size else None,
            })
        structure.append({
            "text_len": len(p.text),
            "alignment": str(p.alignment) if p.alignment else "LEFT",
            "runs": runs_info,
        })
    return structure


def content_match(original_text: str, generated_text: str) -> float:
    """Return content similarity ratio (0-1)."""
    return SequenceMatcher(None, original_text, generated_text).ratio()


def layout_match(original_struct: list, generated_struct: list) -> dict:
    """Compare structural layout between two documents."""
    para_count_match = len(original_struct) == len(generated_struct)
    min_len = min(len(original_struct), len(generated_struct))

    bold_matches = 0
    font_matches = 0
    alignment_matches = 0
    total = max(min_len, 1)

    for i in range(min_len):
        orig = original_struct[i]
        gen = generated_struct[i]

        if orig["alignment"] == gen["alignment"]:
            alignment_matches += 1

        # Compare bold runs
        orig_bold = [r["bold"] for r in orig["runs"]]
        gen_bold = [r["bold"] for r in gen["runs"]]
        if orig_bold == gen_bold:
            bold_matches += 1

        # Compare font sizes (first run)
        orig_size = orig["runs"][0]["font_size"] if orig["runs"] else None
        gen_size = gen["runs"][0]["font_size"] if gen["runs"] else None
        if orig_size == gen_size or (orig_size and gen_size and abs(orig_size - gen_size) <= 0.5):
            font_matches += 1

    return {
        "paragraph_count_match": para_count_match,
        "original_paras": len(original_struct),
        "generated_paras": len(generated_struct),
        "bold_match_pct": round(bold_matches / total * 100, 1),
        "font_match_pct": round(font_matches / total * 100, 1),
        "alignment_match_pct": round(alignment_matches / total * 100, 1),
        "layout_score": round(
            (bold_matches + font_matches + alignment_matches) / (total * 3) * 100, 1
        ),
    }


def run_e2e(resume_path: Path) -> dict:
    """Run full E2E test on a single resume."""
    result = {
        "file": str(resume_path),
        "status": "UNKNOWN",
        "recipe_id": None,
        "template_id": None,
        "content_match": 0,
        "layout_score": 0,
        "issues": [],
    }

    try:
        # Step 1: Upload
        with open(resume_path, "rb") as f:
            resp = requests.post(
                f"{API}/onboard/upload",
                files={"file": (resume_path.name, f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
            )
        if resp.status_code != 200:
            result["status"] = "UPLOAD_FAILED"
            result["issues"].append(f"Upload returned {resp.status_code}: {resp.text[:200]}")
            return result

        upload_data = resp.json()
        recipe_id = upload_data.get("recipe_id")
        template_id = upload_data.get("template_id")
        result["recipe_id"] = recipe_id
        result["template_id"] = template_id

        if not recipe_id:
            result["status"] = "NO_RECIPE"
            result["issues"].append("Upload succeeded but no recipe_id returned")
            return result

        # Step 2: Generate
        gen_resp = requests.post(
            f"{API}/resume/recipes/{recipe_id}/generate",
            json={"format": "json"},
        )
        if gen_resp.status_code != 200:
            result["status"] = "GENERATE_FAILED"
            result["issues"].append(f"Generate returned {gen_resp.status_code}")
            return result

        # Get generated file path
        gen_data = gen_resp.json()
        gen_path = gen_data.get("output_path", gen_data.get("path", ""))

        if not gen_path or not Path(gen_path).exists():
            # Try binary download
            gen_resp2 = requests.post(f"{API}/resume/recipes/{recipe_id}/generate")
            if gen_resp2.status_code == 200:
                with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
                    tmp.write(gen_resp2.content)
                    gen_path = tmp.name

        if not gen_path or not Path(gen_path).exists():
            result["status"] = "NO_OUTPUT"
            result["issues"].append("Generate succeeded but no output file")
            return result

        # Step 3: Gate 1 - Content fidelity
        orig_text = extract_text(str(resume_path))
        gen_text = extract_text(gen_path)
        match_ratio = content_match(orig_text, gen_text)
        result["content_match"] = round(match_ratio * 100, 1)

        # Step 4: Gate 2 - Layout fidelity
        orig_struct = extract_structure(str(resume_path))
        gen_struct = extract_structure(gen_path)
        layout = layout_match(orig_struct, gen_struct)
        result["layout_score"] = layout["layout_score"]
        result["layout_detail"] = layout

        # Determine pass/fail
        if match_ratio >= 0.95 and layout["layout_score"] >= 80:
            result["status"] = "PASS"
        elif match_ratio >= 0.90 and layout["layout_score"] >= 70:
            result["status"] = "WARN"
            result["issues"].append(f"Content {result['content_match']}%, Layout {result['layout_score']}%")
        else:
            result["status"] = "FAIL"
            result["issues"].append(f"Content {result['content_match']}%, Layout {result['layout_score']}%")

    except Exception as e:
        result["status"] = "ERROR"
        result["issues"].append(str(e))

    return result


def main():
    print("=" * 80)
    print("E2E Resume Pipeline Test")
    print("=" * 80)

    # Discover resumes
    resumes = []
    for d in RESUME_DIRS:
        if d.exists():
            for f in d.rglob("*.docx"):
                if is_resume(f):
                    resumes.append(f)

    print(f"\nFound {len(resumes)} resume files to test\n")

    results = []
    for i, resume in enumerate(resumes):
        print(f"[{i+1}/{len(resumes)}] {resume.name}...", end=" ", flush=True)
        result = run_e2e(resume)
        results.append(result)
        print(result["status"])

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"{'File':<45} {'Recipe':>6} {'Content':>8} {'Layout':>7} {'Status':<6}")
    print("-" * 80)
    for r in results:
        name = Path(r["file"]).name[:44]
        rid = r.get("recipe_id") or "-"
        print(f"{name:<45} {rid:>6} {r['content_match']:>7.1f}% {r['layout_score']:>6.1f}% {r['status']:<6}")

    passed = sum(1 for r in results if r["status"] == "PASS")
    warned = sum(1 for r in results if r["status"] == "WARN")
    failed = sum(1 for r in results if r["status"] in ("FAIL", "ERROR", "UPLOAD_FAILED", "NO_RECIPE", "GENERATE_FAILED", "NO_OUTPUT"))
    print(f"\nPASS: {passed}  WARN: {warned}  FAIL: {failed}  Total: {len(results)}")

    # Write detailed results
    output_path = Path("Output/e2e_results.json")
    output_path.parent.mkdir(exist_ok=True)
    output_path.write_text(json.dumps(results, indent=2, default=str))
    print(f"\nDetailed results: {output_path}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Test with a single resume first**

Run: `cd /c/Users/ssala/OneDrive/Desktop/Resumes && python local_code/e2e_resume_test.py`

Debug any issues with the upload → generate → compare pipeline before running against all files.

- [ ] **Step 3: Run full E2E suite**

Fix any parser/templatizer issues discovered. Iterate until core resumes (V32, V31, BEST variants) pass both gates.

- [ ] **Step 4: Commit**

```bash
git add local_code/e2e_resume_test.py && git commit -m "feat: add E2E resume pipeline validation script"
```

---

## Task 12: Run E2E Against All Originals

This is the final validation gate. No new code... just running the script and fixing issues.

- [ ] **Step 1: Clear test data from previous runs**

```sql
DELETE FROM resume_recipes WHERE name LIKE 'E2E_TEST_%';
```

- [ ] **Step 2: Run full E2E suite**

Run: `cd /c/Users/ssala/OneDrive/Desktop/Resumes && python local_code/e2e_resume_test.py`

- [ ] **Step 3: Triage failures**

For each FAIL/WARN result:
- Content <95%: Check if parser missed sections or templatizer dropped content
- Layout <80%: Check if formatting extraction missed bold/font/alignment
- Upload errors: Check parser can handle that resume's structure

- [ ] **Step 4: Fix and re-run until core resumes pass**

Priority: V32 Base, V31 Base, BEST variants, Applied Resumes. Lower priority: old archive formats, one-off variants.

- [ ] **Step 5: Final commit with any parser/builder fixes**

```bash
cd code && git add -A && git commit -m "fix: parser and template builder fixes from E2E validation"
```
