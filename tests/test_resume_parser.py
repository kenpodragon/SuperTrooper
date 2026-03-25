"""Tests for general-purpose resume parser."""
import os
import pytest

# Absolute path to test resume
TEST_RESUME = r"c:\Users\ssala\OneDrive\Desktop\Resumes\Archived\Originals\Stephen_Salaka_Resume_v32.docx"


@pytest.fixture
def parsed_resume():
    """Parse the V32 resume once for all tests."""
    from utils.resume_parser import parse_resume_structure
    assert os.path.exists(TEST_RESUME), f"Test resume not found: {TEST_RESUME}"
    return parse_resume_structure(TEST_RESUME)


def test_returns_list_of_dicts(parsed_resume):
    """Parser returns a non-empty list of dicts."""
    assert isinstance(parsed_resume, list)
    assert len(parsed_resume) > 0
    for item in parsed_resume:
        assert isinstance(item, dict)


def test_required_keys(parsed_resume):
    """Each entry has required keys."""
    required = {"type", "text", "formatting", "paragraph_index", "parent_section"}
    for item in parsed_resume:
        assert required.issubset(item.keys()), f"Missing keys in {item}"


def test_detects_header_with_name(parsed_resume):
    """Parser detects header section containing 'Stephen'."""
    headers = [p for p in parsed_resume if p["type"] == "header"]
    assert len(headers) > 0, "No header paragraphs detected"
    header_text = " ".join(h["text"] for h in headers)
    assert "Stephen" in header_text or "STEPHEN" in header_text, (
        f"Header text does not contain 'Stephen': {header_text[:200]}"
    )


def test_detects_experience_sections(parsed_resume):
    """Parser detects at least 3 experience/job sections."""
    job_headers = [p for p in parsed_resume if p["type"] == "job_header"]
    assert len(job_headers) >= 3, (
        f"Expected >=3 job_header entries, found {len(job_headers)}"
    )


def test_detects_education(parsed_resume):
    """Parser detects education entries."""
    edu = [p for p in parsed_resume if p["type"] == "education"]
    assert len(edu) > 0, "No education entries detected"


def test_detects_bullets(parsed_resume):
    """Parser detects at least 15 bullet items."""
    bullets = [p for p in parsed_resume if p["type"] == "bullet"]
    assert len(bullets) >= 15, (
        f"Expected >=15 bullets, found {len(bullets)}"
    )


def test_formatting_metadata(parsed_resume):
    """Formatting metadata includes font_size."""
    for item in parsed_resume:
        assert "font_size" in item["formatting"], (
            f"Missing font_size in formatting for paragraph {item['paragraph_index']}"
        )


def test_document_order(parsed_resume):
    """Sections are in document order: header before experience."""
    header_indices = [p["paragraph_index"] for p in parsed_resume if p["type"] == "header"]
    exp_indices = [p["paragraph_index"] for p in parsed_resume
                   if p["type"] in ("job_header", "experience")]
    if header_indices and exp_indices:
        assert max(header_indices) < min(exp_indices), (
            "Header paragraphs should come before experience paragraphs"
        )


def test_section_headers_detected(parsed_resume):
    """Parser detects section headers like PROFESSIONAL EXPERIENCE, EDUCATION."""
    section_headers = [p for p in parsed_resume if p["type"] == "section_header"]
    header_texts = [h["text"].upper() for h in section_headers]
    # Should find at least experience and education section headers
    assert any("EXPERIENCE" in t for t in header_texts), (
        f"No EXPERIENCE section header found. Headers: {header_texts}"
    )
    assert any("EDUCATION" in t for t in header_texts), (
        f"No EDUCATION section header found. Headers: {header_texts}"
    )


def test_paragraph_indices_sequential(parsed_resume):
    """Paragraph indices should be sequential."""
    indices = [p["paragraph_index"] for p in parsed_resume]
    assert indices == sorted(indices), "Paragraph indices are not in order"
