"""Tests for kb_dedup_engine — grouping logic (no AI, no DB)."""

import pytest
from kb_dedup_engine import (
    group_skills,
    group_education,
    group_certifications,
    group_career_history,
    group_bullets,
    group_summaries,
    group_languages,
    group_references,
    _normalize_name,
    _employer_normalize,
    _title_normalize,
    _dates_overlap,
    _institution_normalize,
    _looks_like_bullet,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def test_normalize_name_synonym():
    assert _normalize_name("JS") == "javascript"
    assert _normalize_name("k8s") == "kubernetes"
    assert _normalize_name("react.js") == "react"


def test_normalize_name_passthrough():
    assert _normalize_name("python") == "python"
    assert _normalize_name("  Python  ") == "python"


def test_employer_normalize():
    assert _employer_normalize("Acme Corp.") == "acme"
    assert _employer_normalize("Big Co, Inc.") == "big"
    assert _employer_normalize("example.com") == "example"


def test_title_normalize():
    assert "senior" in _title_normalize("Sr. Engineer")
    assert "director" in _title_normalize("Dir. of Engineering")
    assert "vice president" in _title_normalize("VP of Sales")


def test_institution_normalize():
    assert _institution_normalize("Univ. of Michigan") == "university of michigan"
    assert _institution_normalize("MIT") == "mit"


def test_dates_overlap_true():
    a = {"start_date": "2018", "end_date": "2020"}
    b = {"start_date": "2019", "end_date": "2021"}
    assert _dates_overlap(a, b) is True


def test_dates_overlap_false():
    a = {"start_date": "2015", "end_date": "2017"}
    b = {"start_date": "2018", "end_date": "2020"}
    assert _dates_overlap(a, b) is False


def test_looks_like_bullet_true():
    # Action verb + metric
    assert _looks_like_bullet("Led migration that reduced costs by 30%") is True
    # Action verb alone (no metric) — Fix 3: OR logic
    assert _looks_like_bullet("Led the engineering team to redesign the onboarding flow") is True
    # Metric alone (no action verb) — Fix 3: OR logic
    assert _looks_like_bullet("Saved the company $2M in annual infrastructure spend") is True


def test_looks_like_bullet_false():
    # Long paragraph — not a bullet
    long_text = "I am an experienced software engineer with over 10 years building scalable systems across cloud and on-premise environments, working closely with cross-functional teams."
    assert _looks_like_bullet(long_text) is False


# ---------------------------------------------------------------------------
# group_skills
# ---------------------------------------------------------------------------

def test_group_skills_exact_match():
    skills = [
        {"name": "Python", "category": "language"},
        {"name": "python", "category": "language", "proficiency": "expert"},
    ]
    result = group_skills(skills)
    assert len(result["auto_merge"]) == 1
    group = result["auto_merge"][0]
    assert len(group["members"]) == 2
    # Winner should be the one with more fields populated
    assert group["winner"]["proficiency"] == "expert"


def test_group_skills_synonym_match():
    # "JS" and "JavaScript" both normalize to "javascript" via synonym map
    # but have different raw names — should go to needs_review, not auto_merge
    skills = [
        {"name": "JS", "category": "language"},
        {"name": "JavaScript", "category": "language"},
    ]
    result = group_skills(skills)
    assert result["auto_merge"] == [], "synonym match should not auto_merge"
    assert len(result["needs_review"]) >= 1, "synonym match should go to needs_review"
    group = result["needs_review"][0]
    member_names = {m["name"] for m in group["members"]}
    assert "JS" in member_names and "JavaScript" in member_names


def test_group_skills_abbreviation_single_no_flag():
    # Fix 4: a single abbreviated skill with no duplicate is NOT a dedup finding
    # and should not appear in needs_review.
    skills = [{"name": "k8s", "category": "devops"}]
    result = group_skills(skills)
    assert result["needs_review"] == [], "single abbreviation with no duplicate must not be flagged"
    assert result["auto_merge"] == []


def test_group_skills_no_duplicates():
    skills = [
        {"name": "React", "category": "frontend"},
        {"name": "Django", "category": "backend"},
    ]
    result = group_skills(skills)
    assert result["auto_merge"] == []
    # Neither is an abbreviation pointing elsewhere
    # react.js → react but "React" on its own is fine
    assert result["junk"] == []


# ---------------------------------------------------------------------------
# group_education
# ---------------------------------------------------------------------------

def test_group_education_exact_match():
    entries = [
        {"institution": "University of Michigan", "degree": "BS Computer Science", "gpa": "3.8"},
        {"institution": "Univ. of Michigan", "degree": "BS Computer Science"},
    ]
    result = group_education(entries)
    assert len(result["auto_merge"]) == 1
    group = result["auto_merge"][0]
    assert len(group["members"]) == 2
    # Winner has gpa set
    assert group["winner"].get("gpa") == "3.8"


def test_group_education_no_duplicates():
    entries = [
        {"institution": "MIT", "degree": "PhD Physics"},
        {"institution": "Harvard", "degree": "MBA"},
    ]
    result = group_education(entries)
    assert result["auto_merge"] == []


def test_group_education_same_school_different_degree():
    entries = [
        {"institution": "Stanford", "degree": "BS", "field_of_study": "CS"},
        {"institution": "Stanford", "degree": "MS", "field_of_study": "CS"},
    ]
    result = group_education(entries)
    assert result["auto_merge"] == []


# ---------------------------------------------------------------------------
# group_certifications
# ---------------------------------------------------------------------------

def test_group_certifications_exact_match():
    certs = [
        {"name": "PMP", "issuer": "PMI", "is_active": False},
        {"name": "pmp", "issuer": "PMI", "is_active": True},
    ]
    result = group_certifications(certs)
    assert len(result["auto_merge"]) == 1
    assert result["auto_merge"][0]["winner"]["is_active"] is True


def test_group_certifications_synonym_needs_review():
    certs = [
        {"name": "PMP", "issuer": "PMI"},
        {"name": "Project Management Professional", "issuer": "PMI"},
    ]
    result = group_certifications(certs)
    # PMP and Project Management Professional share same synonym canonical
    assert len(result["needs_review"]) == 1


def test_group_certifications_no_duplicates():
    certs = [
        {"name": "AWS Solutions Architect", "issuer": "Amazon"},
        {"name": "PMP", "issuer": "PMI"},
    ]
    result = group_certifications(certs)
    assert result["auto_merge"] == []


# ---------------------------------------------------------------------------
# group_career_history
# ---------------------------------------------------------------------------

def test_group_career_history_employer_merge():
    jobs = [
        {"company": "Acme Corp", "title": "Engineer", "start_date": "2018", "end_date": "2020"},
        {"company": "Acme Inc.", "title": "Senior Engineer", "start_date": "2020", "end_date": "2022"},
        {"company": "Other LLC", "title": "Manager", "start_date": "2022", "end_date": None},
    ]
    result = group_career_history(jobs)
    assert len(result["employer_merge"]) == 1
    group = result["employer_merge"][0]
    assert len(group["members"]) == 2
    assert "acme" in group["canonical_name"].lower() or "Acme" in group["canonical_name"]


def test_group_career_history_role_merge():
    jobs = [
        {"company": "TechCo", "title": "Senior Software Engineer", "start_date": "2018", "end_date": "2019"},
        {"company": "TechCo", "title": "Sr. Software Engineer", "start_date": "2018", "end_date": "2019"},
    ]
    result = group_career_history(jobs)
    assert len(result["role_merge"]) == 1


def test_group_career_history_junk():
    jobs = [
        {"company": "", "title": "", "start_date": "2020"},
        {"company": "Valid Corp", "title": "Developer", "start_date": "2021"},
    ]
    result = group_career_history(jobs)
    assert len(result["junk"]) == 1


def test_group_career_history_no_false_merge():
    jobs = [
        {"company": "Google", "title": "Engineer", "start_date": "2018", "end_date": "2020"},
        {"company": "Amazon", "title": "Engineer", "start_date": "2020", "end_date": "2022"},
    ]
    result = group_career_history(jobs)
    assert result["employer_merge"] == []
    assert result["role_merge"] == []


# ---------------------------------------------------------------------------
# group_bullets
# ---------------------------------------------------------------------------

def test_group_bullets_auto_merge():
    bullets = [
        {"career_history_id": 1, "content": "Led the migration of legacy systems to AWS, reducing costs by 40%"},
        {"career_history_id": 1, "content": "Led the migration of legacy systems to AWS, reducing costs by 40%."},
    ]
    result = group_bullets(bullets)
    assert len(result["auto_merge"]) == 1
    # Winner = longest
    assert result["auto_merge"][0]["winner"] == bullets[1]


def test_group_bullets_needs_review():
    bullets = [
        {"career_history_id": 2, "content": "Managed cross-functional team of 8 engineers delivering product roadmap"},
        {"career_history_id": 2, "content": "Managed cross-functional team of 10 engineers delivering product roadmap on time"},
    ]
    result = group_bullets(bullets)
    assert len(result["needs_review"]) == 1


def test_group_bullets_junk():
    bullets = [
        {"career_history_id": 3, "content": "ok"},           # too short
        {"career_history_id": 3, "content": "12345"},         # no alpha
        {"career_history_id": 3, "content": "Led a team of engineers that shipped 3 major features this quarter"},
    ]
    result = group_bullets(bullets)
    assert len(result["junk"]) == 2
    assert len(result["auto_merge"]) + len(result["needs_review"]) == 0


def test_group_bullets_cross_job_duplicates_in_needs_review():
    # Fix 1: identical bullet copied across two different jobs must appear in needs_review
    # (not auto_merge — user decides which job to keep it under).
    bullets = [
        {"career_history_id": 10, "content": "Led migration to cloud saving 30% in costs annually"},
        {"career_history_id": 11, "content": "Led migration to cloud saving 30% in costs annually"},
    ]
    result = group_bullets(bullets)
    assert result["auto_merge"] == [], "cross-job exact dup must NOT go to auto_merge"
    assert len(result["needs_review"]) >= 1, "cross-job exact dup must appear in needs_review"
    group = result["needs_review"][0]
    job_ids = {m.get("career_history_id") for m in group["members"]}
    assert job_ids == {10, 11}, "needs_review group should span both career_history_ids"


# ---------------------------------------------------------------------------
# group_summaries
# ---------------------------------------------------------------------------

def test_group_summaries_auto_merge():
    summaries = [
        {"content": "Experienced product leader with 10 years driving cross-functional roadmaps and shipping enterprise software at scale."},
        {"content": "Experienced product leader with 10 years driving cross-functional roadmaps and shipping enterprise software at scale!"},
    ]
    result = group_summaries(summaries)
    assert len(result["auto_merge"]) == 1


def test_group_summaries_mixed_content():
    summaries = [
        {"content": "Led migration that reduced infrastructure costs by 35%", "role_type": "engineering"},
        {"content": "Senior engineering leader with 12 years building distributed systems across fintech.", "role_type": "engineering"},
    ]
    result = group_summaries(summaries)
    assert len(result["mixed_content"]) == 1
    assert result["mixed_content"][0]["content"].startswith("Led")


def test_group_summaries_role_type_suggestions():
    summaries = [
        {"content": "Senior PM with 8 years experience building B2B SaaS.", "role_type": "auto_product_manager"},
        {"content": "Engineering leader with strong delivery track record.", "role_type": "engineering"},
    ]
    result = group_summaries(summaries)
    assert len(result["role_type_suggestions"]) == 1
    assert result["role_type_suggestions"][0]["role_type"].startswith("auto_")


def test_group_summaries_junk():
    summaries = [
        {"content": "ok"},
        {"content": ""},
        {"content": "Experienced leader specializing in enterprise software delivery and team development."},
    ]
    result = group_summaries(summaries)
    assert len(result["junk"]) == 2


# ---------------------------------------------------------------------------
# group_languages
# ---------------------------------------------------------------------------

def test_group_languages_exact_match():
    languages = [
        {"language": "Spanish", "proficiency": "fluent"},
        {"language": "spanish"},
    ]
    result = group_languages(languages)
    assert len(result["auto_merge"]) == 1
    # Winner = one with proficiency
    assert result["auto_merge"][0]["winner"]["proficiency"] == "fluent"


def test_group_languages_no_duplicates():
    languages = [
        {"language": "French", "proficiency": "conversational"},
        {"language": "German", "proficiency": "basic"},
    ]
    result = group_languages(languages)
    assert result["auto_merge"] == []


# ---------------------------------------------------------------------------
# group_references
# ---------------------------------------------------------------------------

def test_group_references_exact_match():
    refs = [
        {"name": "Jane Smith", "company": "Acme Corp", "email": "jane@acme.com", "title": "VP"},
        {"name": "Jane Smith", "company": "Acme Inc.", "phone": "555-1234"},
    ]
    result = group_references(refs)
    assert len(result["auto_merge"]) == 1
    assert len(result["auto_merge"][0]["members"]) == 2
    # Winner has more fields (email + title)
    assert result["auto_merge"][0]["winner"].get("email") == "jane@acme.com"


def test_group_references_no_duplicates():
    refs = [
        {"name": "Alice Johnson", "company": "TechCo"},
        {"name": "Bob Williams", "company": "FinCo"},
    ]
    result = group_references(refs)
    assert result["auto_merge"] == []
