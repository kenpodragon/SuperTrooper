"""Tests for build_section_map() in template_builder."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.template_builder import build_section_map


def test_build_section_map_groups_slots():
    """Numbered slots get grouped into sections."""
    parsed = [
        {"type": "header", "text": "Stephen Salaka", "para_index": 0},
        {"type": "headline", "text": "AI Architect", "para_index": 1},
        {"type": "section_header", "text": "Certifications", "para_index": 5},
        {"type": "certification", "text": "CSM | Scrum Alliance", "para_index": 6},
        {"type": "certification", "text": "PMP | PMI", "para_index": 7},
    ]
    result = build_section_map(parsed)

    assert "HEADER" in result
    assert result["HEADER"]["repeating"] is False
    assert result["HEADER"]["para_index"] == 0

    assert "HEADLINE" in result
    assert result["HEADLINE"]["repeating"] is False
    assert result["HEADLINE"]["para_index"] == 1

    assert "CERTIFICATIONS" in result
    assert result["CERTIFICATIONS"]["repeating"] is True
    assert result["CERTIFICATIONS"]["para_index"] == 6
    assert result["CERTIFICATIONS"]["section_header_para"] == 5


def test_build_section_map_experience_compound():
    """Experience sections group into compound structure with sub_sections."""
    parsed = [
        {"type": "section_header", "text": "Professional Experience", "para_index": 2},
        {"type": "job_header", "text": "Acme Corp | 2022-Present", "para_index": 3},
        {"type": "job_title", "text": "Senior Engineer", "para_index": 4},
        {"type": "job_bullet", "text": "Led team of 5", "para_index": 5},
        {"type": "job_bullet", "text": "Increased throughput 30%", "para_index": 6},
    ]
    result = build_section_map(parsed)

    assert "EXPERIENCE" in result
    assert result["EXPERIENCE"]["repeating"] is True
    assert result["EXPERIENCE"]["section_header_para"] == 2
    assert "sub_sections" in result["EXPERIENCE"]


def test_build_section_map_empty_section():
    """Section header with no content items doesn't create a section entry."""
    parsed = [
        {"type": "section_header", "text": "Education", "para_index": 10},
    ]
    result = build_section_map(parsed)

    assert "EDUCATION" not in result


def test_build_section_map_singular_sections_not_repeating():
    """HEADER, HEADLINE, and SUMMARY are marked as non-repeating."""
    parsed = [
        {"type": "header", "text": "Stephen Salaka", "para_index": 0},
        {"type": "headline", "text": "AI Architect", "para_index": 1},
        {"type": "summary", "text": "Experienced leader...", "para_index": 2},
    ]
    result = build_section_map(parsed)

    assert result["HEADER"]["repeating"] is False
    assert result["HEADLINE"]["repeating"] is False
    assert result["SUMMARY"]["repeating"] is False


def test_build_section_map_only_first_occurrence():
    """Only the first occurrence of each section type defines the prototype."""
    parsed = [
        {"type": "certification", "text": "CSM | Scrum Alliance", "para_index": 6},
        {"type": "certification", "text": "PMP | PMI", "para_index": 7},
        {"type": "certification", "text": "AWS | Amazon", "para_index": 8},
    ]
    result = build_section_map(parsed)

    assert "CERTIFICATIONS" in result
    # para_index should be from first occurrence
    assert result["CERTIFICATIONS"]["para_index"] == 6


def test_build_section_map_empty_input():
    """Empty input returns empty map."""
    result = build_section_map([])
    assert result == {}


def test_build_section_map_unknown_types_skipped():
    """Unknown section types are silently skipped."""
    parsed = [
        {"type": "totally_unknown_type", "text": "foo", "para_index": 0},
        {"type": "header", "text": "Stephen Salaka", "para_index": 1},
    ]
    result = build_section_map(parsed)

    assert "HEADER" in result
    assert len(result) == 1
