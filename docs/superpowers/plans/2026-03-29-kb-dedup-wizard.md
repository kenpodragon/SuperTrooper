# KB Cleanup Wizard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an AI-assisted KB cleanup wizard that deduplicates all entity types (career history, bullets, skills, education, certifications, summaries, languages, references) through a sequential, three-stage confirmation workflow.

**Architecture:** New backend route module (`routes/kb_dedup.py`) with scan and apply endpoints that use the existing AI provider infrastructure (`ai_providers/router.py`) for intelligent grouping. New frontend wizard component (`KbDedupWizard.tsx`) launched from the Knowledge Base page via an AI toggle. Each entity type goes through three stages: auto-merge, needs-review, and junk/delete.

**Tech Stack:** Flask (backend routes), psycopg2 (DB), Claude CLI via `ai_providers` (AI analysis), React + TypeScript + React Query (frontend), Tailwind CSS (styling)

**Spec:** `code/docs/superpowers/specs/2026-03-29-kb-dedup-wizard-design.md`

---

## File Structure

### Backend (new files)
- `backend/routes/kb_dedup.py` — All dedup scan/apply/summary-specific endpoints. Single blueprint.
- `backend/kb_dedup_engine.py` — Core dedup logic: grouping algorithms, AI prompt builders, merge execution. Kept separate from routes for testability.

### Backend (modified files)
- `backend/routes/__init__.py` — Register new blueprint

### Frontend (new files)
- `frontend/src/pages/knowledge-base/KbDedupWizard.tsx` — Wizard shell: full-screen modal, step navigation, progress bar
- `frontend/src/pages/knowledge-base/DedupStepAutoMerge.tsx` — Stage 1: green auto-merge confirmation
- `frontend/src/pages/knowledge-base/DedupStepReview.tsx` — Stage 2: yellow side-by-side review
- `frontend/src/pages/knowledge-base/DedupStepJunk.tsx` — Stage 3: red junk/delete/reclassify
- `frontend/src/pages/knowledge-base/SummaryRoleTypeEditor.tsx` — Summary role_type reassignment
- `frontend/src/pages/knowledge-base/SummarySplitReview.tsx` — Summary content splitting review
- `frontend/src/pages/knowledge-base/AiToggle.tsx` — Reusable AI on/off toggle

### Frontend (modified files)
- `frontend/src/pages/knowledge-base/KnowledgeBase.tsx` — Add AI toggle + cleanup button to header

### Tests
- `tests/test_kb_dedup_engine.py` — Unit tests for grouping logic, merge execution, AI prompt parsing
- `tests/test_kb_dedup_routes.py` — Integration tests for scan/apply endpoints

---

## Task 1: Backend Dedup Engine — Grouping Logic (No AI)

The core engine that groups entities by similarity without AI. This is the Python-fallback path and the foundation for AI-enhanced grouping.

**Files:**
- Create: `backend/kb_dedup_engine.py`
- Test: `tests/test_kb_dedup_engine.py`

- [ ] **Step 1: Write failing tests for skill grouping**

```python
# tests/test_kb_dedup_engine.py
import pytest
from kb_dedup_engine import group_skills


def test_exact_name_match():
    skills = [
        {"id": 1, "name": "JavaScript", "category": "language", "proficiency": "expert", "last_used_year": 2026},
        {"id": 2, "name": "javascript", "category": None, "proficiency": None, "last_used_year": None},
        {"id": 3, "name": "Python", "category": "language", "proficiency": "expert", "last_used_year": 2026},
    ]
    result = group_skills(skills)
    assert len(result["auto_merge"]) == 1
    group = result["auto_merge"][0]
    assert group["winner_id"] == 1  # more complete record
    assert set(m["id"] for m in group["members"]) == {1, 2}
    assert result["needs_review"] == []
    assert result["junk"] == []


def test_abbreviation_match():
    skills = [
        {"id": 1, "name": "JavaScript", "category": "language", "proficiency": "expert", "last_used_year": 2026},
        {"id": 2, "name": "JS", "category": None, "proficiency": None, "last_used_year": None},
    ]
    result = group_skills(skills)
    # Abbreviation match goes to needs_review (not confident enough for auto)
    assert len(result["needs_review"]) == 1
    assert len(result["auto_merge"]) == 0


def test_no_duplicates():
    skills = [
        {"id": 1, "name": "JavaScript", "category": "language", "proficiency": "expert", "last_used_year": 2026},
        {"id": 2, "name": "Python", "category": "language", "proficiency": "expert", "last_used_year": 2026},
    ]
    result = group_skills(skills)
    assert result["auto_merge"] == []
    assert result["needs_review"] == []
    assert result["junk"] == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd code && python -m pytest tests/test_kb_dedup_engine.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'kb_dedup_engine'`

- [ ] **Step 3: Implement skill grouping**

```python
# backend/kb_dedup_engine.py
"""KB dedup engine — grouping, scoring, merge execution for all entity types."""

from difflib import SequenceMatcher

# Common abbreviation/synonym map for skills
SKILL_SYNONYMS = {
    "js": "javascript",
    "ts": "typescript",
    "py": "python",
    "react.js": "react",
    "reactjs": "react",
    "node.js": "nodejs",
    "node": "nodejs",
    "vue.js": "vue",
    "vuejs": "vue",
    "angular.js": "angular",
    "angularjs": "angular",
    "c#": "csharp",
    "c++": "cpp",
    "pm": "project management",
    "pmp": "project management professional",
    "csm": "certified scrummaster",
    "k8s": "kubernetes",
    "aws": "amazon web services",
    "gcp": "google cloud platform",
    "ml": "machine learning",
    "ai": "artificial intelligence",
    "ci/cd": "continuous integration continuous deployment",
    "devops": "development operations",
}


def _normalize_name(name):
    """Lowercase, strip whitespace, resolve known synonyms."""
    n = name.strip().lower()
    return SKILL_SYNONYMS.get(n, n)


def _completeness_score(record, fields):
    """Score how many fields are non-null/non-empty."""
    return sum(1 for f in fields if record.get(f))


def _pick_winner(members, fields):
    """Pick the most complete record as winner."""
    return max(members, key=lambda m: _completeness_score(m, fields))


def group_skills(skills):
    """Group skills by name similarity. Returns {auto_merge, needs_review, junk}."""
    fields = ["category", "proficiency", "last_used_year"]
    buckets = {}  # normalized_name -> [skill_dicts]

    for s in skills:
        key = _normalize_name(s["name"])
        buckets.setdefault(key, []).append(s)

    auto_merge = []
    needs_review = []
    junk = []

    for key, members in buckets.items():
        if len(members) < 2:
            continue

        # Check if all original names are very similar (exact or case-only)
        names_lower = [m["name"].strip().lower() for m in members]
        all_exact = len(set(names_lower)) == 1

        if all_exact:
            winner = _pick_winner(members, fields)
            auto_merge.append({
                "group_id": f"skill-{key}",
                "winner_id": winner["id"],
                "members": members,
                "reason": f"Exact name match (case-insensitive): '{members[0]['name']}'",
            })
        else:
            # Names differ but resolved to same synonym — needs review
            winner = _pick_winner(members, fields)
            needs_review.append({
                "group_id": f"skill-{key}",
                "winner_id": winner["id"],
                "members": members,
                "similarity_score": 0.7,
                "reason": f"Possible synonym/abbreviation: {[m['name'] for m in members]}",
            })

    return {"auto_merge": auto_merge, "needs_review": needs_review, "junk": junk}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd code && python -m pytest tests/test_kb_dedup_engine.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Add education and certification grouping with tests**

```python
# Add to tests/test_kb_dedup_engine.py
from kb_dedup_engine import group_education, group_certifications


def test_education_same_institution():
    entries = [
        {"id": 1, "degree": "MBA", "field": "Business Administration", "institution": "University of Phoenix", "location": "Phoenix, AZ", "type": "Masters"},
        {"id": 2, "degree": "MBA", "field": "Business", "institution": "Univ. of Phoenix", "location": None, "type": None},
    ]
    result = group_education(entries)
    assert len(result["auto_merge"]) == 1
    assert result["auto_merge"][0]["winner_id"] == 1


def test_education_different_degrees():
    entries = [
        {"id": 1, "degree": "MBA", "field": "Business", "institution": "University of Phoenix", "location": "Phoenix, AZ", "type": "Masters"},
        {"id": 2, "degree": "BS", "field": "Computer Science", "institution": "University of Phoenix", "location": "Phoenix, AZ", "type": "Bachelors"},
    ]
    result = group_education(entries)
    assert result["auto_merge"] == []


def test_cert_synonym():
    certs = [
        {"id": 1, "name": "PMP", "issuer": "PMI", "is_active": True},
        {"id": 2, "name": "Project Management Professional", "issuer": "PMI", "is_active": False},
    ]
    result = group_certifications(certs)
    assert len(result["needs_review"]) == 1
    assert result["needs_review"][0]["members"][0]["id"] in [1, 2]


def test_cert_exact():
    certs = [
        {"id": 1, "name": "CSM", "issuer": "Scrum Alliance", "is_active": True},
        {"id": 2, "name": "CSM", "issuer": None, "is_active": False},
    ]
    result = group_certifications(certs)
    assert len(result["auto_merge"]) == 1
    assert result["auto_merge"][0]["winner_id"] == 1  # has is_active=True
```

```python
# Add to backend/kb_dedup_engine.py

CERT_SYNONYMS = {
    "pmp": "project management professional",
    "csm": "certified scrummaster",
    "aws saa": "aws solutions architect associate",
    "aws sap": "aws solutions architect professional",
    "cka": "certified kubernetes administrator",
    "ccna": "cisco certified network associate",
    "cissp": "certified information systems security professional",
    "itil": "information technology infrastructure library",
}


def _institution_normalize(name):
    """Normalize institution names for comparison."""
    n = name.strip().lower()
    for prefix in ["university of", "univ. of", "u of", "univ of"]:
        if n.startswith(prefix):
            return "university of" + n[len(prefix):]
    return n


def group_education(entries):
    """Group education by institution + degree similarity."""
    fields = ["degree", "field", "institution", "location", "type"]
    buckets = {}

    for e in entries:
        inst = _institution_normalize(e.get("institution", "") or "")
        degree = (e.get("degree", "") or "").strip().lower()
        key = f"{inst}|{degree}"
        buckets.setdefault(key, []).append(e)

    auto_merge = []
    needs_review = []

    for key, members in buckets.items():
        if len(members) < 2:
            continue
        winner = _pick_winner(members, fields)
        auto_merge.append({
            "group_id": f"edu-{key}",
            "winner_id": winner["id"],
            "members": members,
            "reason": f"Same institution + degree: {members[0].get('institution')} / {members[0].get('degree')}",
        })

    return {"auto_merge": auto_merge, "needs_review": needs_review, "junk": []}


def group_certifications(certs):
    """Group certifications by name similarity."""
    fields = ["name", "issuer", "is_active"]
    buckets = {}

    for c in certs:
        key = CERT_SYNONYMS.get((c["name"] or "").strip().lower(), (c["name"] or "").strip().lower())
        buckets.setdefault(key, []).append(c)

    auto_merge = []
    needs_review = []

    for key, members in buckets.items():
        if len(members) < 2:
            continue

        names_lower = [(m["name"] or "").strip().lower() for m in members]
        all_exact = len(set(names_lower)) == 1

        # Prefer record with is_active=True
        winner = next((m for m in members if m.get("is_active")), _pick_winner(members, fields))

        if all_exact:
            auto_merge.append({
                "group_id": f"cert-{key}",
                "winner_id": winner["id"],
                "members": members,
                "reason": f"Exact name match: '{members[0]['name']}'",
            })
        else:
            needs_review.append({
                "group_id": f"cert-{key}",
                "winner_id": winner["id"],
                "members": members,
                "similarity_score": 0.7,
                "reason": f"Possible synonym: {[m['name'] for m in members]}",
            })

    return {"auto_merge": auto_merge, "needs_review": needs_review, "junk": []}
```

- [ ] **Step 6: Run all tests**

Run: `cd code && python -m pytest tests/test_kb_dedup_engine.py -v`
Expected: PASS (7 tests)

- [ ] **Step 7: Add career history grouping (employer + role)**

```python
# Add to tests/test_kb_dedup_engine.py
from kb_dedup_engine import group_career_history


def test_employer_merge():
    jobs = [
        {"id": 1, "employer": "Microsoft Corporation", "title": "Sr. Director", "start_date": "2020-01", "end_date": "2023-06", "intro_text": "Led engineering org"},
        {"id": 2, "employer": "Microsoft Corp", "title": "Director of Engineering", "start_date": "2018-03", "end_date": "2020-01", "intro_text": None},
        {"id": 3, "employer": "Amazon", "title": "VP Engineering", "start_date": "2023-07", "end_date": None, "intro_text": "Current role"},
    ]
    result = group_career_history(jobs)
    # Employer grouping: Microsoft Corporation / Microsoft Corp are same employer
    employer_groups = result["employer_merge"]
    assert len(employer_groups) == 1
    assert set(m["id"] for m in employer_groups[0]["members"]) == {1, 2}


def test_role_merge_same_employer():
    jobs = [
        {"id": 1, "employer": "Microsoft", "title": "Sr. Director, Engineering", "start_date": "2020-01", "end_date": "2023-06", "intro_text": "Led engineering org"},
        {"id": 2, "employer": "Microsoft", "title": "Senior Director of Engineering", "start_date": "2020-01", "end_date": "2023-06", "intro_text": None},
    ]
    result = group_career_history(jobs)
    role_groups = result["role_merge"]
    assert len(role_groups) == 1
    assert role_groups[0]["winner_id"] == 1  # has intro_text


def test_different_roles_same_employer():
    jobs = [
        {"id": 1, "employer": "Microsoft", "title": "Sr. Director", "start_date": "2020-01", "end_date": "2023-06", "intro_text": None},
        {"id": 2, "employer": "Microsoft", "title": "VP Engineering", "start_date": "2023-07", "end_date": None, "intro_text": None},
    ]
    result = group_career_history(jobs)
    assert result["role_merge"] == []
```

```python
# Add to backend/kb_dedup_engine.py

def _employer_normalize(name):
    """Normalize employer names for grouping."""
    n = (name or "").strip().lower()
    # Strip common suffixes
    for suffix in [", inc.", ", inc", " inc.", " inc", ", llc", " llc",
                   ", ltd", " ltd", ", corp.", " corp.", ", corp", " corp",
                   " corporation", " company", " co.", " co",
                   ".com", ", l.p.", " l.p."]:
        if n.endswith(suffix):
            n = n[:-len(suffix)].strip()
    return n


def _title_normalize(title):
    """Normalize job titles for comparison."""
    t = (title or "").strip().lower()
    # Normalize common prefixes
    t = t.replace("sr.", "senior").replace("jr.", "junior")
    t = t.replace("dir.", "director").replace("mgr.", "manager")
    t = t.replace("vp", "vice president").replace("v.p.", "vice president")
    # Remove connectors
    for word in [" of ", " for ", ", "]:
        t = t.replace(word, " ")
    return " ".join(t.split())  # collapse whitespace


def _dates_overlap(a, b):
    """Check if two date ranges overlap or are adjacent."""
    a_start = a.get("start_date") or ""
    a_end = a.get("end_date") or "9999-12"
    b_start = b.get("start_date") or ""
    b_end = b.get("end_date") or "9999-12"
    return a_start <= b_end and b_start <= a_end


def group_career_history(jobs):
    """Group career history by employer similarity, then role similarity.

    Returns {employer_merge, role_merge, junk} where:
    - employer_merge: groups of jobs with same employer (different name variants)
    - role_merge: groups of jobs at same employer with same/similar title + overlapping dates
    """
    fields = ["employer", "title", "start_date", "end_date", "intro_text", "notes"]

    # Phase A: Employer grouping
    employer_buckets = {}
    for j in jobs:
        key = _employer_normalize(j["employer"])
        employer_buckets.setdefault(key, []).append(j)

    employer_merge = []
    for key, members in employer_buckets.items():
        names = set(m["employer"].strip() for m in members)
        if len(names) > 1:
            # Different name variants for same employer
            # Winner is the longest/most formal name
            winner_name = max(names, key=len)
            employer_merge.append({
                "group_id": f"employer-{key}",
                "canonical_name": winner_name,
                "members": members,
                "reason": f"Same employer, different names: {sorted(names)}",
            })

    # Phase B: Role merge (within same normalized employer)
    role_merge = []
    for key, members in employer_buckets.items():
        if len(members) < 2:
            continue
        # Group by similar title + overlapping dates
        title_buckets = {}
        for m in members:
            tkey = _title_normalize(m["title"])
            title_buckets.setdefault(tkey, []).append(m)

        for tkey, role_members in title_buckets.items():
            if len(role_members) < 2:
                continue
            # Check date overlap between members
            overlapping = []
            for i, a in enumerate(role_members):
                for b in role_members[i+1:]:
                    if _dates_overlap(a, b):
                        overlapping.extend([a, b])

            if overlapping:
                unique = {m["id"]: m for m in overlapping}
                members_list = list(unique.values())
                winner = _pick_winner(members_list, fields)
                role_merge.append({
                    "group_id": f"role-{key}-{tkey}",
                    "winner_id": winner["id"],
                    "members": members_list,
                    "reason": f"Same title + overlapping dates at '{members_list[0]['employer']}'",
                })

    return {"employer_merge": employer_merge, "role_merge": role_merge, "junk": []}
```

- [ ] **Step 8: Run all tests**

Run: `cd code && python -m pytest tests/test_kb_dedup_engine.py -v`
Expected: PASS (10 tests)

- [ ] **Step 9: Add bullet grouping and summary grouping**

```python
# Add to tests/test_kb_dedup_engine.py
from kb_dedup_engine import group_bullets, group_summaries


def test_bullet_exact_duplicate():
    bullets = [
        {"id": 1, "career_history_id": 10, "text": "Led team of 12 engineers to deliver cloud migration on time and under budget", "type": "achievement"},
        {"id": 2, "career_history_id": 10, "text": "Led team of 12 engineers to deliver cloud migration on time and under budget", "type": "achievement"},
    ]
    result = group_bullets(bullets)
    assert len(result["auto_merge"]) == 1


def test_bullet_near_duplicate():
    bullets = [
        {"id": 1, "career_history_id": 10, "text": "Led team of 12 engineers to deliver cloud migration on time and under budget", "type": "achievement"},
        {"id": 2, "career_history_id": 10, "text": "Led a team of 12 engineers delivering cloud migration on time, under budget", "type": "achievement"},
    ]
    result = group_bullets(bullets)
    assert len(result["needs_review"]) == 1


def test_summary_with_bullet_content():
    summaries = [
        {"id": 1, "role_type": "auto_1", "text": "Seasoned technology executive with 20+ years leading engineering teams. Reduced infrastructure costs by 40% through cloud migration. Built and scaled teams from 5 to 50 engineers."},
    ]
    result = group_summaries(summaries)
    # Should detect mixed content (summary + bullet-like sentences)
    assert len(result["mixed_content"]) == 1
    mixed = result["mixed_content"][0]
    assert "summary_portion" in mixed
    assert "bullet_portions" in mixed


def test_summary_role_type_cleanup():
    summaries = [
        {"id": 1, "role_type": "auto_1", "text": "Seasoned CTO with 20+ years..."},
        {"id": 2, "role_type": "auto_2", "text": "VP Engineering leader..."},
        {"id": 3, "role_type": "auto_1", "text": "Duplicate of first..."},
    ]
    result = group_summaries(summaries)
    assert len(result["role_type_suggestions"]) > 0
```

```python
# Add to backend/kb_dedup_engine.py

def group_bullets(bullets):
    """Group bullets by text similarity within the same career_history_id."""
    auto_merge = []
    needs_review = []
    junk = []
    seen = set()

    # Group by career_history_id first
    by_job = {}
    for b in bullets:
        by_job.setdefault(b.get("career_history_id"), []).append(b)

    for ch_id, job_bullets in by_job.items():
        n = len(job_bullets)
        for i in range(n):
            if job_bullets[i]["id"] in seen:
                continue
            group = [job_bullets[i]]
            for j in range(i + 1, n):
                if job_bullets[j]["id"] in seen:
                    continue
                ratio = SequenceMatcher(
                    None,
                    job_bullets[i]["text"].strip().lower(),
                    job_bullets[j]["text"].strip().lower(),
                ).ratio()
                if ratio >= 0.95:
                    group.append(job_bullets[j])
                    seen.add(job_bullets[j]["id"])
                elif ratio >= 0.75:
                    needs_review.append({
                        "group_id": f"bullet-{job_bullets[i]['id']}-{job_bullets[j]['id']}",
                        "winner_id": job_bullets[i]["id"],
                        "members": [job_bullets[i], job_bullets[j]],
                        "similarity_score": round(ratio, 3),
                        "reason": f"Similar text ({ratio:.0%} match)",
                    })
                    seen.add(job_bullets[j]["id"])

            if len(group) > 1:
                # Pick the longer/more detailed bullet as winner
                winner = max(group, key=lambda b: len(b["text"]))
                auto_merge.append({
                    "group_id": f"bullet-exact-{group[0]['id']}",
                    "winner_id": winner["id"],
                    "members": group,
                    "reason": "Near-identical text",
                })
                seen.add(job_bullets[i]["id"])

        # Junk detection: very short bullets, fragments
        for b in job_bullets:
            text = (b["text"] or "").strip()
            if len(text) < 15 or not any(c.isalpha() for c in text):
                junk.append({
                    "id": b["id"],
                    "content_preview": text[:100],
                    "reason": "Too short or non-text content",
                })

    return {"auto_merge": auto_merge, "needs_review": needs_review, "junk": junk}


def _looks_like_bullet(text):
    """Heuristic: does this text look like a resume bullet?"""
    bullet_verbs = ["led", "managed", "built", "reduced", "increased", "delivered",
                    "developed", "implemented", "created", "launched", "drove",
                    "achieved", "improved", "established", "designed", "orchestrated",
                    "spearheaded", "streamlined", "transformed", "negotiated"]
    words = text.strip().lower().split()
    if not words:
        return False
    # Starts with action verb
    if words[0] in bullet_verbs:
        return True
    # Contains metrics (numbers with % or $)
    if any(c in text for c in ['%', '$', 'million', 'billion']):
        if len(text) < 200:  # bullets are usually short
            return True
    return False


def group_summaries(summaries):
    """Group summaries: detect mixed content, suggest role_types, find duplicates."""
    auto_merge = []
    needs_review = []
    junk = []
    mixed_content = []
    role_type_suggestions = []

    # Role type analysis
    role_types_seen = set()
    for s in summaries:
        rt = (s.get("role_type") or "").strip()
        if rt:
            role_types_seen.add(rt)

    # Flag auto-generated role types
    for rt in role_types_seen:
        if rt.startswith("auto_") or rt.startswith("type_") or not any(c.isalpha() for c in rt):
            role_type_suggestions.append({
                "current": rt,
                "suggested": None,  # AI will fill this
                "reason": "Auto-generated role type, needs meaningful label",
            })

    # Content splitting: detect mixed summary+bullet content
    for s in summaries:
        text = (s.get("text") or "").strip()
        sentences = [sent.strip() for sent in text.replace(". ", ".\n").split("\n") if sent.strip()]

        summary_parts = []
        bullet_parts = []
        for sent in sentences:
            if _looks_like_bullet(sent):
                bullet_parts.append(sent)
            else:
                summary_parts.append(sent)

        if bullet_parts and summary_parts:
            mixed_content.append({
                "id": s["id"],
                "original_text": text,
                "summary_portion": ". ".join(summary_parts),
                "bullet_portions": bullet_parts,
                "reason": f"Contains {len(bullet_parts)} bullet-like sentence(s) mixed with summary",
            })
        elif bullet_parts and not summary_parts:
            junk.append({
                "id": s["id"],
                "content_preview": text[:100],
                "reason": "Entirely bullet content, not a summary",
                "suggested_reclassify": {"target_table": "bullets"},
            })

    # Dedup: exact and near-match among summaries
    seen = set()
    for i, a in enumerate(summaries):
        if a["id"] in seen:
            continue
        group = [a]
        for b in summaries[i+1:]:
            if b["id"] in seen:
                continue
            ratio = SequenceMatcher(None, (a["text"] or "").lower(), (b["text"] or "").lower()).ratio()
            if ratio >= 0.90:
                group.append(b)
                seen.add(b["id"])
            elif ratio >= 0.70:
                needs_review.append({
                    "group_id": f"summary-{a['id']}-{b['id']}",
                    "winner_id": a["id"],
                    "members": [a, b],
                    "similarity_score": round(ratio, 3),
                    "reason": f"Similar summary text ({ratio:.0%} match)",
                })
                seen.add(b["id"])

        if len(group) > 1:
            winner = max(group, key=lambda s: len(s.get("text") or ""))
            auto_merge.append({
                "group_id": f"summary-exact-{group[0]['id']}",
                "winner_id": winner["id"],
                "members": group,
                "reason": "Near-identical summary text",
            })
            seen.add(a["id"])

    return {
        "auto_merge": auto_merge,
        "needs_review": needs_review,
        "junk": junk,
        "mixed_content": mixed_content,
        "role_type_suggestions": role_type_suggestions,
    }
```

- [ ] **Step 10: Run all tests**

Run: `cd code && python -m pytest tests/test_kb_dedup_engine.py -v`
Expected: PASS (14 tests)

- [ ] **Step 11: Add language and reference grouping**

```python
# Add to tests/test_kb_dedup_engine.py
from kb_dedup_engine import group_languages, group_references


def test_language_exact():
    langs = [
        {"id": 1, "name": "English", "proficiency": "native"},
        {"id": 2, "name": "english", "proficiency": None},
    ]
    result = group_languages(langs)
    assert len(result["auto_merge"]) == 1


def test_reference_same_person():
    refs = [
        {"id": 1, "name": "John Smith", "title": "CTO", "company": "Acme Corp", "email": "john@acme.com"},
        {"id": 2, "name": "John Smith", "title": "CTO", "company": "Acme", "email": None},
    ]
    result = group_references(refs)
    assert len(result["auto_merge"]) == 1
```

```python
# Add to backend/kb_dedup_engine.py

def group_languages(languages):
    """Group languages by name similarity."""
    buckets = {}
    for lang in languages:
        key = (lang["name"] or "").strip().lower()
        buckets.setdefault(key, []).append(lang)

    auto_merge = []
    for key, members in buckets.items():
        if len(members) < 2:
            continue
        winner = next((m for m in members if m.get("proficiency")), members[0])
        auto_merge.append({
            "group_id": f"lang-{key}",
            "winner_id": winner["id"],
            "members": members,
            "reason": f"Same language: '{members[0]['name']}'",
        })

    return {"auto_merge": auto_merge, "needs_review": [], "junk": []}


def group_references(references):
    """Group references by name + company similarity."""
    fields = ["name", "title", "company", "email", "phone", "linkedin_url", "notes"]
    buckets = {}
    for r in references:
        name = (r.get("name") or "").strip().lower()
        company = _employer_normalize(r.get("company") or "")
        key = f"{name}|{company}"
        buckets.setdefault(key, []).append(r)

    auto_merge = []
    for key, members in buckets.items():
        if len(members) < 2:
            continue
        winner = _pick_winner(members, fields)
        auto_merge.append({
            "group_id": f"ref-{key}",
            "winner_id": winner["id"],
            "members": members,
            "reason": f"Same person: '{members[0].get('name')}' at '{members[0].get('company')}'",
        })

    return {"auto_merge": auto_merge, "needs_review": [], "junk": []}
```

- [ ] **Step 12: Run all tests**

Run: `cd code && python -m pytest tests/test_kb_dedup_engine.py -v`
Expected: PASS (16 tests)

- [ ] **Step 13: Commit**

```bash
git add backend/kb_dedup_engine.py tests/test_kb_dedup_engine.py
git commit -m "feat: KB dedup engine — grouping logic for all entity types (no AI)"
```

---

## Task 2: Backend Dedup Engine — AI-Enhanced Grouping

Adds AI-powered grouping that runs through `ai_providers/router.py` for smarter duplicate detection.

**Files:**
- Modify: `backend/kb_dedup_engine.py`
- Test: `tests/test_kb_dedup_engine.py`

- [ ] **Step 1: Write failing test for AI-enhanced skill grouping**

```python
# Add to tests/test_kb_dedup_engine.py
from unittest.mock import patch, MagicMock
from kb_dedup_engine import ai_enhanced_group


def test_ai_enhanced_skills():
    skills = [
        {"id": 1, "name": "React", "category": "framework"},
        {"id": 2, "name": "React.js", "category": None},
        {"id": 3, "name": "Vue", "category": "framework"},
        {"id": 4, "name": "VueJS", "category": None},
        {"id": 5, "name": "Project Management", "category": "methodology"},
    ]

    mock_ai_response = {
        "groups": [
            {"ids": [1, 2], "canonical": "React", "confidence": 0.95, "reason": "Same framework, different naming"},
            {"ids": [3, 4], "canonical": "Vue.js", "confidence": 0.92, "reason": "Same framework, different naming"},
        ],
        "junk": [],
    }

    with patch("kb_dedup_engine.route_inference") as mock_route:
        mock_route.return_value = mock_ai_response
        result = ai_enhanced_group("skills", skills)

    assert len(result["auto_merge"]) == 2
    assert result["auto_merge"][0]["winner_id"] == 1  # most complete
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd code && python -m pytest tests/test_kb_dedup_engine.py::test_ai_enhanced_skills -v`
Expected: FAIL

- [ ] **Step 3: Implement AI-enhanced grouping**

```python
# Add to backend/kb_dedup_engine.py
import json
from ai_providers.router import route_inference


DEDUP_PROMPT_TEMPLATE = """You are analyzing a list of {entity_type} entries for duplicates.

For each group of duplicates, provide:
- ids: list of entry IDs that are duplicates of each other
- canonical: the best/canonical name to keep
- confidence: 0.0-1.0 how confident you are these are duplicates
- reason: brief explanation

Also flag junk entries (garbled text, parsing artifacts, misclassified content):
- id: the entry ID
- reason: why it's junk
- suggested_reclassify: (optional) where this content should go instead

Return JSON:
{{"groups": [...], "junk": [...]}}

Entries:
{entries_json}"""


SUMMARY_SPLIT_PROMPT = """Analyze this summary text. Separate the professional summary portion from any resume bullet content that got mixed in.

A professional summary is a paragraph describing someone's overall career narrative, expertise areas, and value proposition.
Resume bullets are specific achievement statements, usually starting with action verbs and containing metrics.

Text:
{text}

Return JSON:
{{"summary_portion": "the actual summary text", "bullet_portions": ["bullet 1", "bullet 2", ...], "is_mixed": true/false}}"""


ROLE_TYPE_PROMPT = """These are professional summary texts with auto-generated role_type labels. Suggest a meaningful role_type for each based on the content.

Role types should be job titles like: CTO, VP Engineering, Director of Engineering, Engineering Manager, Program Manager, Product Manager, etc.

Summaries:
{entries_json}

Return JSON:
{{"suggestions": [{{"id": N, "current_role_type": "...", "suggested_role_type": "..."}}]}}"""


def _build_entries_json(entity_type, entries):
    """Build a compact JSON representation of entries for AI prompts."""
    if entity_type == "skills":
        return json.dumps([{"id": e["id"], "name": e["name"], "category": e.get("category")} for e in entries])
    elif entity_type == "education":
        return json.dumps([{"id": e["id"], "degree": e.get("degree"), "field": e.get("field"), "institution": e.get("institution")} for e in entries])
    elif entity_type == "certifications":
        return json.dumps([{"id": e["id"], "name": e["name"], "issuer": e.get("issuer")} for e in entries])
    elif entity_type == "career_history":
        return json.dumps([{"id": e["id"], "employer": e["employer"], "title": e["title"], "start_date": e.get("start_date"), "end_date": e.get("end_date")} for e in entries])
    elif entity_type == "bullets":
        return json.dumps([{"id": e["id"], "career_history_id": e.get("career_history_id"), "text": e["text"][:200]} for e in entries])
    elif entity_type == "summaries":
        return json.dumps([{"id": e["id"], "role_type": e.get("role_type"), "text": e["text"][:300]} for e in entries])
    elif entity_type == "languages":
        return json.dumps([{"id": e["id"], "name": e["name"], "proficiency": e.get("proficiency")} for e in entries])
    elif entity_type == "references":
        return json.dumps([{"id": e["id"], "name": e.get("name"), "company": e.get("company"), "title": e.get("title")} for e in entries])
    return json.dumps(entries)


def _ai_group(entity_type, entries):
    """Call AI to group entries. Returns parsed JSON response."""
    entries_json = _build_entries_json(entity_type, entries)
    prompt = DEDUP_PROMPT_TEMPLATE.format(entity_type=entity_type, entries_json=entries_json)

    def python_fallback():
        # Fall back to the non-AI grouping functions
        fn_map = {
            "skills": group_skills,
            "education": group_education,
            "certifications": group_certifications,
            "bullets": group_bullets,
            "summaries": group_summaries,
            "languages": group_languages,
            "references": group_references,
        }
        return fn_map[entity_type](entries)

    def ai_handler(provider):
        return provider.run_prompt(prompt, expect_json=True)

    return route_inference(
        task=f"dedup_{entity_type}",
        context={"entries": entries, "entity_type": entity_type},
        python_fallback=python_fallback,
        ai_handler=ai_handler,
    )


def _entries_by_id(entries):
    """Build id->entry lookup dict."""
    return {e["id"]: e for e in entries}


def ai_enhanced_group(entity_type, entries):
    """AI-enhanced grouping for any entity type. Falls back to Python grouping if AI unavailable."""
    ai_result = _ai_group(entity_type, entries)

    # If we got the Python fallback result, return it directly
    if isinstance(ai_result, dict) and "auto_merge" in ai_result:
        return ai_result

    # Parse AI response into our standard format
    lookup = _entries_by_id(entries)
    fields_map = {
        "skills": ["category", "proficiency", "last_used_year"],
        "education": ["degree", "field", "institution", "location", "type"],
        "certifications": ["name", "issuer", "is_active"],
        "bullets": ["text", "type", "tags"],
        "summaries": ["role_type", "text"],
        "languages": ["name", "proficiency"],
        "references": ["name", "title", "company", "email", "phone"],
    }
    fields = fields_map.get(entity_type, [])

    auto_merge = []
    needs_review = []
    junk = []

    groups = ai_result.get("groups", []) if isinstance(ai_result, dict) else []
    for g in groups:
        members = [lookup[id_] for id_ in g["ids"] if id_ in lookup]
        if len(members) < 2:
            continue
        winner = _pick_winner(members, fields)
        confidence = g.get("confidence", 0.5)

        entry = {
            "group_id": f"ai-{entity_type}-{'-'.join(str(i) for i in g['ids'])}",
            "winner_id": winner["id"],
            "members": members,
            "reason": g.get("reason", "AI-detected duplicate"),
        }

        if confidence >= 0.85:
            auto_merge.append(entry)
        else:
            entry["similarity_score"] = confidence
            needs_review.append(entry)

    ai_junk = ai_result.get("junk", []) if isinstance(ai_result, dict) else []
    for j in ai_junk:
        if j.get("id") in lookup:
            junk.append({
                "id": j["id"],
                "content_preview": str(lookup[j["id"]].get("text", lookup[j["id"]].get("name", "")))[:100],
                "reason": j.get("reason", "AI flagged as junk"),
                "suggested_reclassify": j.get("suggested_reclassify"),
            })

    return {"auto_merge": auto_merge, "needs_review": needs_review, "junk": junk}


def ai_split_summary(summary_text):
    """AI-powered summary content splitting."""
    prompt = SUMMARY_SPLIT_PROMPT.format(text=summary_text)

    def python_fallback():
        # Use heuristic splitting
        sentences = [s.strip() for s in summary_text.replace(". ", ".\n").split("\n") if s.strip()]
        summary_parts = [s for s in sentences if not _looks_like_bullet(s)]
        bullet_parts = [s for s in sentences if _looks_like_bullet(s)]
        return {
            "summary_portion": ". ".join(summary_parts) if summary_parts else "",
            "bullet_portions": bullet_parts,
            "is_mixed": bool(bullet_parts and summary_parts),
        }

    def ai_handler(provider):
        return provider.run_prompt(prompt, expect_json=True)

    return route_inference(
        task="split_summary",
        context={"text": summary_text},
        python_fallback=python_fallback,
        ai_handler=ai_handler,
    )


def ai_suggest_role_types(summaries):
    """AI-powered role type suggestion for summaries."""
    entries_json = json.dumps([{"id": s["id"], "role_type": s.get("role_type"), "text": (s.get("text") or "")[:300]} for s in summaries])
    prompt = ROLE_TYPE_PROMPT.format(entries_json=entries_json)

    def python_fallback():
        return {"suggestions": [{"id": s["id"], "current_role_type": s.get("role_type"), "suggested_role_type": None} for s in summaries]}

    def ai_handler(provider):
        return provider.run_prompt(prompt, expect_json=True)

    return route_inference(
        task="suggest_role_types",
        context={"summaries": summaries},
        python_fallback=python_fallback,
        ai_handler=ai_handler,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd code && python -m pytest tests/test_kb_dedup_engine.py::test_ai_enhanced_skills -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/kb_dedup_engine.py tests/test_kb_dedup_engine.py
git commit -m "feat: AI-enhanced grouping for KB dedup — prompts, routing, fallback"
```

---

## Task 3: Backend Dedup Engine — Merge Execution

Database operations to execute confirmed merges, deletes, and reclassifications.

**Files:**
- Modify: `backend/kb_dedup_engine.py`
- Test: `tests/test_kb_dedup_engine.py`

- [ ] **Step 1: Write failing test for skill merge execution**

```python
# Add to tests/test_kb_dedup_engine.py
import db as test_db
from kb_dedup_engine import execute_merge


def test_execute_skill_merge(test_conn):
    """Integration test: merge two skill records, loser is deleted."""
    with test_conn.cursor() as cur:
        cur.execute("INSERT INTO skills (name, category, proficiency) VALUES ('JavaScript', 'language', 'expert') RETURNING id")
        winner_id = cur.fetchone()[0]
        cur.execute("INSERT INTO skills (name, category) VALUES ('javascript', 'language') RETURNING id")
        loser_id = cur.fetchone()[0]
    test_conn.commit()

    result = execute_merge("skills", winner_id, [loser_id])
    assert result["merged"] == 1
    assert result["errors"] == []

    # Verify loser is gone
    row = test_db.query_one("SELECT id FROM skills WHERE id = %s", [loser_id])
    assert row is None
    # Verify winner still exists
    row = test_db.query_one("SELECT id FROM skills WHERE id = %s", [winner_id])
    assert row is not None
```

Note: This test requires a real DB connection. The test fixture `test_conn` should connect to the test database. If the project doesn't have this fixture yet, create a `tests/conftest.py`:

```python
# tests/conftest.py
import sys
import os
import pytest
import psycopg2

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

@pytest.fixture
def test_conn():
    """Provide a DB connection that rolls back after each test."""
    conn = psycopg2.connect(
        host="localhost", port=5555,
        dbname="supertroopers", user="supertroopers",
        password=os.environ.get("PGPASSWORD", "WUHD8fBisb57FS4Q3bdvfuvgnim9fL1c")
    )
    yield conn
    conn.rollback()
    conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd code && python -m pytest tests/test_kb_dedup_engine.py::test_execute_skill_merge -v`
Expected: FAIL with `ImportError: cannot import name 'execute_merge'`

- [ ] **Step 3: Implement merge execution**

```python
# Add to backend/kb_dedup_engine.py
import db


def execute_merge(entity_type, winner_id, loser_ids):
    """Execute a merge: repoint foreign keys, then delete losers.

    Returns {"merged": N, "errors": []}
    """
    errors = []
    merged = 0

    with db.get_conn() as conn:
        with conn.cursor() as cur:
            for loser_id in loser_ids:
                try:
                    if entity_type == "career_history":
                        # Repoint bullets and references to winner
                        cur.execute("UPDATE bullets SET career_history_id = %s WHERE career_history_id = %s", [winner_id, loser_id])
                        cur.execute("UPDATE references SET career_history_id = %s WHERE career_history_id = %s", [winner_id, loser_id])
                        cur.execute("DELETE FROM career_history WHERE id = %s", [loser_id])
                    elif entity_type == "bullets":
                        cur.execute("DELETE FROM bullets WHERE id = %s", [loser_id])
                    elif entity_type == "skills":
                        cur.execute("DELETE FROM skills WHERE id = %s", [loser_id])
                    elif entity_type == "education":
                        cur.execute("DELETE FROM education WHERE id = %s", [loser_id])
                    elif entity_type == "certifications":
                        cur.execute("DELETE FROM certifications WHERE id = %s", [loser_id])
                    elif entity_type == "summary_variants":
                        cur.execute("DELETE FROM summary_variants WHERE id = %s", [loser_id])
                    elif entity_type == "languages":
                        cur.execute("DELETE FROM languages WHERE id = %s", [loser_id])
                    elif entity_type == "references":
                        cur.execute("DELETE FROM references WHERE id = %s", [loser_id])
                    merged += 1
                except Exception as e:
                    errors.append({"loser_id": loser_id, "error": str(e)})

    return {"merged": merged, "errors": errors}


def execute_delete(entity_type, ids):
    """Delete entities by ID. Returns {"deleted": N, "errors": []}."""
    table_map = {
        "skills": "skills", "education": "education", "certifications": "certifications",
        "bullets": "bullets", "career_history": "career_history",
        "summary_variants": "summary_variants", "languages": "languages", "references": "references",
    }
    table = table_map.get(entity_type)
    if not table:
        return {"deleted": 0, "errors": [{"error": f"Unknown entity type: {entity_type}"}]}

    deleted = 0
    errors = []
    with db.get_conn() as conn:
        with conn.cursor() as cur:
            for id_ in ids:
                try:
                    if entity_type == "career_history":
                        # Cascade: delete bullets and unlink references first
                        cur.execute("DELETE FROM bullets WHERE career_history_id = %s", [id_])
                        cur.execute("UPDATE references SET career_history_id = NULL WHERE career_history_id = %s", [id_])
                    cur.execute(f"DELETE FROM {table} WHERE id = %s", [id_])
                    deleted += 1
                except Exception as e:
                    errors.append({"id": id_, "error": str(e)})

    return {"deleted": deleted, "errors": errors}


def execute_reclassify(source_type, target_type, items):
    """Move items from one entity table to another.

    items: [{"id": N, "career_history_id": optional}]
    Returns {"reclassified": N, "errors": []}
    """
    reclassified = 0
    errors = []

    source_table_map = {
        "summary_variants": "summary_variants", "bullets": "bullets",
        "skills": "skills", "education": "education", "certifications": "certifications",
    }
    source_table = source_table_map.get(source_type)

    with db.get_conn() as conn:
        with conn.cursor() as cur:
            for item in items:
                try:
                    # Read source content
                    cur.execute(f"SELECT * FROM {source_table} WHERE id = %s", [item["id"]])
                    row = cur.fetchone()
                    if not row:
                        errors.append({"id": item["id"], "error": "Source record not found"})
                        continue

                    if source_type == "summary_variants" and target_type == "bullets":
                        # Move summary text to bullets table
                        ch_id = item.get("career_history_id")
                        cur.execute(
                            "INSERT INTO bullets (career_history_id, text, type, source_file) VALUES (%s, %s, 'achievement', 'reclassified_from_summary')",
                            [ch_id, row[2]]  # row[2] is text column in summary_variants
                        )
                        cur.execute("DELETE FROM summary_variants WHERE id = %s", [item["id"]])
                        reclassified += 1
                    else:
                        errors.append({"id": item["id"], "error": f"Reclassify {source_type}->{target_type} not implemented"})
                except Exception as e:
                    errors.append({"id": item["id"], "error": str(e)})

    return {"reclassified": reclassified, "errors": errors}


def execute_employer_rename(career_history_ids, canonical_name):
    """Rename employer for a set of career_history records."""
    with db.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE career_history SET employer = %s WHERE id = ANY(%s)",
                [canonical_name, career_history_ids]
            )
            return {"updated": cur.rowcount}


def execute_summary_role_type_rename(reassignments):
    """Rename role_types: {old_role_type: new_role_type}."""
    updated = 0
    with db.get_conn() as conn:
        with conn.cursor() as cur:
            for old_rt, new_rt in reassignments.items():
                cur.execute(
                    "UPDATE summary_variants SET role_type = %s WHERE role_type = %s",
                    [new_rt, old_rt]
                )
                updated += cur.rowcount
    return {"updated": updated}


def execute_summary_split(split_id, keep_summary_text, extract_bullets, career_history_id=None):
    """Split a summary: update summary text, create new bullet records."""
    with db.get_conn() as conn:
        with conn.cursor() as cur:
            # Update the summary with just the summary portion
            cur.execute(
                "UPDATE summary_variants SET text = %s WHERE id = %s",
                [keep_summary_text, split_id]
            )
            # Insert extracted bullets
            created = 0
            for bullet_text in extract_bullets:
                cur.execute(
                    "INSERT INTO bullets (career_history_id, text, type, source_file) VALUES (%s, %s, 'achievement', 'split_from_summary')",
                    [career_history_id, bullet_text]
                )
                created += 1
            return {"summary_updated": True, "bullets_created": created}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd code && python -m pytest tests/test_kb_dedup_engine.py::test_execute_skill_merge -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/kb_dedup_engine.py tests/test_kb_dedup_engine.py tests/conftest.py
git commit -m "feat: merge execution — delete, reclassify, employer rename, summary split"
```

---

## Task 4: Backend Routes — Scan and Apply Endpoints

Flask routes that wire the dedup engine to HTTP endpoints.

**Files:**
- Create: `backend/routes/kb_dedup.py`
- Modify: `backend/routes/__init__.py`
- Test: `tests/test_kb_dedup_routes.py`

- [ ] **Step 1: Write failing test for scan endpoint**

```python
# tests/test_kb_dedup_routes.py
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app import create_app


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_scan_skills(client):
    resp = client.post("/api/kb/dedup/scan", json={"entity_type": "skills"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert "auto_merge" in data
    assert "needs_review" in data
    assert "junk" in data


def test_scan_invalid_entity(client):
    resp = client.post("/api/kb/dedup/scan", json={"entity_type": "invalid"})
    assert resp.status_code == 400
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd code && python -m pytest tests/test_kb_dedup_routes.py -v`
Expected: FAIL

- [ ] **Step 3: Create the routes**

```python
# backend/routes/kb_dedup.py
"""KB Dedup Wizard — scan and apply endpoints."""

from flask import Blueprint, request, jsonify
import db
import kb_dedup_engine

bp = Blueprint("kb_dedup", __name__)

ENTITY_TABLES = {
    "career_history": "career_history",
    "bullets": "bullets",
    "skills": "skills",
    "education": "education",
    "certifications": "certifications",
    "summaries": "summary_variants",
    "languages": "languages",
    "references": "references",
}

ENTITY_COLUMNS = {
    "career_history": "id, employer, title, start_date, end_date, location, industry, intro_text, notes",
    "bullets": "id, career_history_id, text, type, tags, source_file",
    "skills": "id, name, category, proficiency, last_used_year",
    "education": "id, degree, field, institution, location, type, sort_order",
    "certifications": "id, name, issuer, is_active, sort_order",
    "summaries": "id, role_type, text",
    "languages": "id, name, proficiency",
    "references": "id, name, title, company, relationship, email, phone, linkedin_url, notes, career_history_id",
}

GROUP_FUNCTIONS = {
    "career_history": kb_dedup_engine.group_career_history,
    "bullets": kb_dedup_engine.group_bullets,
    "skills": kb_dedup_engine.group_skills,
    "education": kb_dedup_engine.group_education,
    "certifications": kb_dedup_engine.group_certifications,
    "summaries": kb_dedup_engine.group_summaries,
    "languages": kb_dedup_engine.group_languages,
    "references": kb_dedup_engine.group_references,
}


def _fetch_all(entity_type):
    """Fetch all records for an entity type."""
    table = ENTITY_TABLES.get(entity_type)
    cols = ENTITY_COLUMNS.get(entity_type)
    if not table or not cols:
        return []
    return db.query(f"SELECT {cols} FROM {table} ORDER BY id")


@bp.route("/api/kb/dedup/scan", methods=["POST"])
def scan():
    """Scan an entity type for duplicates. Optionally AI-enhanced."""
    body = request.get_json(force=True)
    entity_type = body.get("entity_type")
    use_ai = body.get("use_ai", False)

    if entity_type not in ENTITY_TABLES:
        return jsonify({"error": f"Invalid entity type: {entity_type}"}), 400

    entries = _fetch_all(entity_type)

    if not entries:
        return jsonify({"auto_merge": [], "needs_review": [], "junk": [], "count": 0})

    if use_ai:
        result = kb_dedup_engine.ai_enhanced_group(entity_type, entries)
    else:
        fn = GROUP_FUNCTIONS[entity_type]
        result = fn(entries)

    result["count"] = len(entries)
    return jsonify(result)


@bp.route("/api/kb/dedup/apply", methods=["POST"])
def apply_changes():
    """Apply confirmed merges, deletes, and reclassifications."""
    body = request.get_json(force=True)
    entity_type = body.get("entity_type")

    if entity_type not in ENTITY_TABLES:
        return jsonify({"error": f"Invalid entity type: {entity_type}"}), 400

    results = {"merged": 0, "deleted": 0, "reclassified": 0, "errors": []}

    # Process merges
    for merge in body.get("merges", []):
        r = kb_dedup_engine.execute_merge(
            entity_type if entity_type != "summaries" else "summary_variants",
            merge["winner_id"],
            merge["loser_ids"],
        )
        results["merged"] += r["merged"]
        results["errors"].extend(r["errors"])

    # Process deletes
    delete_ids = body.get("deletes", [])
    if delete_ids:
        r = kb_dedup_engine.execute_delete(
            entity_type if entity_type != "summaries" else "summary_variants",
            delete_ids,
        )
        results["deleted"] += r["deleted"]
        results["errors"].extend(r["errors"])

    # Process reclassifications
    for reclass in body.get("reclassifications", []):
        r = kb_dedup_engine.execute_reclassify(
            ENTITY_TABLES[entity_type],
            reclass["target_table"],
            [{"id": reclass["id"], "career_history_id": reclass.get("career_history_id")}],
        )
        results["reclassified"] += r["reclassified"]
        results["errors"].extend(r["errors"])

    return jsonify(results)


@bp.route("/api/kb/dedup/employer-rename", methods=["POST"])
def employer_rename():
    """Rename employer across career_history records."""
    body = request.get_json(force=True)
    ids = body.get("career_history_ids", [])
    canonical_name = body.get("canonical_name")

    if not ids or not canonical_name:
        return jsonify({"error": "career_history_ids and canonical_name required"}), 400

    result = kb_dedup_engine.execute_employer_rename(ids, canonical_name)
    return jsonify(result)


@bp.route("/api/kb/dedup/summaries/role-types", methods=["POST"])
def summary_role_types():
    """Rename role_types for summary_variants."""
    body = request.get_json(force=True)
    reassignments = body.get("reassignments", {})

    if not reassignments:
        return jsonify({"error": "reassignments dict required"}), 400

    result = kb_dedup_engine.execute_summary_role_type_rename(reassignments)
    return jsonify(result)


@bp.route("/api/kb/dedup/summaries/suggest-role-types", methods=["POST"])
def suggest_role_types():
    """AI-suggest meaningful role_types for summaries."""
    entries = _fetch_all("summaries")
    result = kb_dedup_engine.ai_suggest_role_types(entries)
    return jsonify(result)


@bp.route("/api/kb/dedup/summaries/split", methods=["POST"])
def summary_split():
    """Split mixed summary content into summary + bullets."""
    body = request.get_json(force=True)
    splits = body.get("splits", [])

    results = {"splits_applied": 0, "bullets_created": 0, "errors": []}
    for s in splits:
        try:
            r = kb_dedup_engine.execute_summary_split(
                s["id"], s["keep_summary_text"], s["extract_bullets"],
                s.get("career_history_id"),
            )
            results["splits_applied"] += 1
            results["bullets_created"] += r["bullets_created"]
        except Exception as e:
            results["errors"].append({"id": s["id"], "error": str(e)})

    return jsonify(results)
```

- [ ] **Step 4: Register the blueprint**

Add to `backend/routes/__init__.py`:

```python
from routes.kb_dedup import bp as kb_dedup_bp
```

And add `kb_dedup_bp` to the `ALL_BLUEPRINTS` list.

- [ ] **Step 5: Run tests**

Run: `cd code && python -m pytest tests/test_kb_dedup_routes.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/routes/kb_dedup.py backend/routes/__init__.py tests/test_kb_dedup_routes.py
git commit -m "feat: KB dedup API routes — scan, apply, employer-rename, summary-split"
```

---

## Task 5: Frontend — AI Toggle Component

Reusable toggle switch for enabling AI features on KB pages.

**Files:**
- Create: `frontend/src/pages/knowledge-base/AiToggle.tsx`
- Test: manual visual verification

- [ ] **Step 1: Create the AiToggle component**

```tsx
// frontend/src/pages/knowledge-base/AiToggle.tsx
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../../api/client';

interface SettingsData {
  ai_enabled: boolean;
  ai_provider: string;
}

export default function AiToggle() {
  const queryClient = useQueryClient();

  const { data: settings } = useQuery<SettingsData>({
    queryKey: ['settings'],
    queryFn: () => api.get<SettingsData>('/settings'),
  });

  const mutation = useMutation({
    mutationFn: (enabled: boolean) => api.patch('/settings', { ai_enabled: enabled }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['settings'] }),
  });

  const isOn = settings?.ai_enabled ?? false;

  return (
    <div className="flex items-center gap-2">
      <span className="text-sm text-gray-400">AI Assist</span>
      <button
        onClick={() => mutation.mutate(!isOn)}
        disabled={mutation.isPending}
        className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
          isOn ? 'bg-purple-600' : 'bg-gray-600'
        }`}
        title={isOn ? 'Disable AI features' : 'Enable AI features'}
      >
        <span
          className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
            isOn ? 'translate-x-6' : 'translate-x-1'
          }`}
        />
      </button>
    </div>
  );
}
```

- [ ] **Step 2: Verify it renders**

Start the frontend dev server and navigate to KB page (after integrating in Task 8). For now, visually confirm in isolation or via Storybook if available.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/knowledge-base/AiToggle.tsx
git commit -m "feat: AiToggle component — reusable AI on/off switch"
```

---

## Task 6: Frontend — Wizard Shell and Progress Bar

The main wizard modal with step navigation.

**Files:**
- Create: `frontend/src/pages/knowledge-base/KbDedupWizard.tsx`

- [ ] **Step 1: Create the wizard shell**

```tsx
// frontend/src/pages/knowledge-base/KbDedupWizard.tsx
import { useState, useCallback } from 'react';
import { useMutation } from '@tanstack/react-query';
import { api } from '../../api/client';
import DedupStepAutoMerge from './DedupStepAutoMerge';
import DedupStepReview from './DedupStepReview';
import DedupStepJunk from './DedupStepJunk';
import SummaryRoleTypeEditor from './SummaryRoleTypeEditor';
import SummarySplitReview from './SummarySplitReview';

const ENTITY_STEPS = [
  { key: 'career_history', label: 'Career History' },
  { key: 'bullets', label: 'Bullets' },
  { key: 'skills', label: 'Skills' },
  { key: 'education', label: 'Education' },
  { key: 'certifications', label: 'Certifications' },
  { key: 'summaries', label: 'Summaries' },
  { key: 'languages', label: 'Languages' },
  { key: 'references', label: 'References' },
] as const;

type EntityKey = (typeof ENTITY_STEPS)[number]['key'];
type SubStage = 'scanning' | 'auto_merge' | 'review' | 'junk' | 'summary_role_types' | 'summary_split' | 'skipped' | 'done';

interface ScanResult {
  auto_merge: any[];
  needs_review: any[];
  junk: any[];
  count: number;
  employer_merge?: any[];
  role_merge?: any[];
  mixed_content?: any[];
  role_type_suggestions?: any[];
}

interface Props {
  isOpen: boolean;
  onClose: () => void;
}

export default function KbDedupWizard({ isOpen, onClose }: Props) {
  const [entityIdx, setEntityIdx] = useState(0);
  const [subStage, setSubStage] = useState<SubStage>('scanning');
  const [scanResult, setScanResult] = useState<ScanResult | null>(null);
  const [completedSteps, setCompletedSteps] = useState<Set<number>>(new Set());

  const currentEntity = ENTITY_STEPS[entityIdx];

  const scanMutation = useMutation({
    mutationFn: (entityType: string) =>
      api.post<ScanResult>('/kb/dedup/scan', { entity_type: entityType, use_ai: true }),
    onSuccess: (data) => {
      setScanResult(data);
      const hasWork =
        data.auto_merge.length > 0 ||
        data.needs_review.length > 0 ||
        data.junk.length > 0 ||
        (data.employer_merge && data.employer_merge.length > 0) ||
        (data.role_merge && data.role_merge.length > 0) ||
        (data.mixed_content && data.mixed_content.length > 0);

      if (!hasWork) {
        setSubStage('skipped');
      } else if (currentEntity.key === 'summaries') {
        setSubStage('summary_role_types');
      } else {
        setSubStage(data.auto_merge.length > 0 || (data.employer_merge && data.employer_merge.length > 0) ? 'auto_merge' : data.needs_review.length > 0 ? 'review' : 'junk');
      }
    },
  });

  const startScan = useCallback(() => {
    setSubStage('scanning');
    setScanResult(null);
    scanMutation.mutate(currentEntity.key);
  }, [currentEntity.key]);

  // Auto-scan on mount and entity change
  useState(() => { startScan(); });

  const advanceSubStage = useCallback(() => {
    if (!scanResult) return;
    if (subStage === 'summary_role_types') {
      setSubStage(scanResult.mixed_content && scanResult.mixed_content.length > 0 ? 'summary_split' : 'auto_merge');
    } else if (subStage === 'summary_split') {
      setSubStage(scanResult.auto_merge.length > 0 ? 'auto_merge' : scanResult.needs_review.length > 0 ? 'review' : scanResult.junk.length > 0 ? 'junk' : 'done');
    } else if (subStage === 'auto_merge') {
      setSubStage(scanResult.needs_review.length > 0 ? 'review' : scanResult.junk.length > 0 ? 'junk' : 'done');
    } else if (subStage === 'review') {
      setSubStage(scanResult.junk.length > 0 ? 'junk' : 'done');
    } else if (subStage === 'junk' || subStage === 'skipped') {
      setSubStage('done');
    }
  }, [subStage, scanResult]);

  const advanceEntity = useCallback(() => {
    setCompletedSteps((prev) => new Set([...prev, entityIdx]));
    if (entityIdx < ENTITY_STEPS.length - 1) {
      setEntityIdx((i) => i + 1);
      setSubStage('scanning');
      setScanResult(null);
      // Next entity scan will trigger via useEffect
    } else {
      onClose();
    }
  }, [entityIdx, onClose]);

  // Trigger scan when entity changes
  // (handled by re-render with scanning state)

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black/80 flex flex-col">
      {/* Header */}
      <div className="bg-gray-900 border-b border-gray-700 px-6 py-4 flex items-center justify-between">
        <h2 className="text-xl font-semibold text-white">Clean Up Knowledge Base</h2>
        <button onClick={onClose} className="text-gray-400 hover:text-white text-2xl">&times;</button>
      </div>

      {/* Progress bar */}
      <div className="bg-gray-900 px-6 py-3 border-b border-gray-800">
        <div className="flex gap-1">
          {ENTITY_STEPS.map((step, idx) => (
            <div key={step.key} className="flex-1 flex flex-col items-center gap-1">
              <div
                className={`w-full h-2 rounded-full ${
                  completedSteps.has(idx)
                    ? 'bg-green-500'
                    : idx === entityIdx
                    ? 'bg-purple-500'
                    : 'bg-gray-700'
                }`}
              />
              <span className={`text-xs ${idx === entityIdx ? 'text-purple-400' : 'text-gray-500'}`}>
                {step.label}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Content area */}
      <div className="flex-1 overflow-y-auto p-6">
        {subStage === 'scanning' && (
          <div className="flex flex-col items-center justify-center h-full gap-4">
            <div className="animate-spin w-8 h-8 border-2 border-purple-500 border-t-transparent rounded-full" />
            <p className="text-gray-400">Scanning {currentEntity.label} for duplicates...</p>
          </div>
        )}

        {subStage === 'skipped' && (
          <div className="flex flex-col items-center justify-center h-full gap-4">
            <span className="text-4xl">✓</span>
            <p className="text-gray-300">{currentEntity.label}: No duplicates found</p>
            <button onClick={advanceEntity} className="px-6 py-2 bg-purple-600 hover:bg-purple-500 text-white rounded-lg">
              Next →
            </button>
          </div>
        )}

        {subStage === 'done' && (
          <div className="flex flex-col items-center justify-center h-full gap-4">
            <span className="text-4xl">✓</span>
            <p className="text-gray-300">{currentEntity.label}: Cleanup complete</p>
            <button onClick={advanceEntity} className="px-6 py-2 bg-purple-600 hover:bg-purple-500 text-white rounded-lg">
              {entityIdx < ENTITY_STEPS.length - 1 ? 'Next →' : 'Finish'}
            </button>
          </div>
        )}

        {subStage === 'summary_role_types' && scanResult && (
          <SummaryRoleTypeEditor
            suggestions={scanResult.role_type_suggestions || []}
            onComplete={advanceSubStage}
          />
        )}

        {subStage === 'summary_split' && scanResult && (
          <SummarySplitReview
            mixedContent={scanResult.mixed_content || []}
            onComplete={advanceSubStage}
          />
        )}

        {subStage === 'auto_merge' && scanResult && (
          <DedupStepAutoMerge
            entityType={currentEntity.key}
            groups={currentEntity.key === 'career_history' ? [...(scanResult.employer_merge || []), ...(scanResult.role_merge || [])] : scanResult.auto_merge}
            onComplete={advanceSubStage}
          />
        )}

        {subStage === 'review' && scanResult && (
          <DedupStepReview
            entityType={currentEntity.key}
            groups={scanResult.needs_review}
            onComplete={advanceSubStage}
          />
        )}

        {subStage === 'junk' && scanResult && (
          <DedupStepJunk
            entityType={currentEntity.key}
            items={scanResult.junk}
            onComplete={advanceSubStage}
          />
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/knowledge-base/KbDedupWizard.tsx
git commit -m "feat: KB dedup wizard shell — step navigation, progress bar, scan trigger"
```

---

## Task 7: Frontend — Three Sub-Stage Components

The auto-merge, review, and junk/delete stage components.

**Files:**
- Create: `frontend/src/pages/knowledge-base/DedupStepAutoMerge.tsx`
- Create: `frontend/src/pages/knowledge-base/DedupStepReview.tsx`
- Create: `frontend/src/pages/knowledge-base/DedupStepJunk.tsx`

- [ ] **Step 1: Create DedupStepAutoMerge**

```tsx
// frontend/src/pages/knowledge-base/DedupStepAutoMerge.tsx
import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { api } from '../../api/client';

interface MergeGroup {
  group_id: string;
  winner_id?: number;
  canonical_name?: string;
  members: any[];
  reason: string;
}

interface Props {
  entityType: string;
  groups: MergeGroup[];
  onComplete: () => void;
}

export default function DedupStepAutoMerge({ entityType, groups, onComplete }: Props) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [overrides, setOverrides] = useState<Record<string, number>>({});
  const [demoted, setDemoted] = useState<Set<string>>(new Set());

  const applyMutation = useMutation({
    mutationFn: (merges: { winner_id: number; loser_ids: number[] }[]) =>
      api.post('/kb/dedup/apply', { entity_type: entityType, merges }),
    onSuccess: () => onComplete(),
  });

  const activeGroups = groups.filter((g) => !demoted.has(g.group_id));

  const handleConfirmAll = () => {
    const merges = activeGroups
      .filter((g) => g.winner_id || overrides[g.group_id])
      .map((g) => {
        const winnerId = overrides[g.group_id] || g.winner_id!;
        return {
          winner_id: winnerId,
          loser_ids: g.members.filter((m) => m.id !== winnerId).map((m) => m.id),
        };
      });

    // Handle employer renames separately
    const employerRenames = activeGroups
      .filter((g) => g.canonical_name)
      .map((g) => ({
        career_history_ids: g.members.map((m) => m.id),
        canonical_name: g.canonical_name!,
      }));

    if (employerRenames.length > 0) {
      Promise.all(
        employerRenames.map((r) => api.post('/kb/dedup/employer-rename', r))
      ).then(() => {
        if (merges.length > 0) {
          applyMutation.mutate(merges);
        } else {
          onComplete();
        }
      });
    } else if (merges.length > 0) {
      applyMutation.mutate(merges);
    } else {
      onComplete();
    }
  };

  if (activeGroups.length === 0) {
    onComplete();
    return null;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-green-400">Auto-Merge</h3>
          <p className="text-sm text-gray-400">{activeGroups.length} group(s) — obvious duplicates</p>
        </div>
        <button
          onClick={handleConfirmAll}
          disabled={applyMutation.isPending}
          className="px-6 py-2 bg-green-600 hover:bg-green-500 text-white rounded-lg disabled:opacity-50"
        >
          {applyMutation.isPending ? 'Merging...' : 'Confirm All'}
        </button>
      </div>

      <div className="space-y-3">
        {activeGroups.map((group) => (
          <div key={group.group_id} className="bg-gray-800 rounded-lg border border-gray-700 p-4">
            <div className="flex items-center justify-between">
              <div className="flex-1">
                <p className="text-sm text-gray-400">{group.reason}</p>
                <div className="flex flex-wrap gap-2 mt-2">
                  {group.members.map((m) => {
                    const isWinner = m.id === (overrides[group.group_id] || group.winner_id);
                    return (
                      <span
                        key={m.id}
                        className={`px-3 py-1 rounded text-sm ${
                          isWinner ? 'bg-green-700 text-green-100 font-semibold' : 'bg-gray-700 text-gray-300'
                        }`}
                      >
                        {m.name || m.employer || m.title || m.text?.slice(0, 60) || `#${m.id}`}
                      </span>
                    );
                  })}
                </div>
              </div>
              <div className="flex gap-2 ml-4">
                <button
                  onClick={() => setExpanded((prev) => {
                    const next = new Set(prev);
                    next.has(group.group_id) ? next.delete(group.group_id) : next.add(group.group_id);
                    return next;
                  })}
                  className="text-sm text-gray-400 hover:text-white"
                >
                  {expanded.has(group.group_id) ? 'Collapse' : 'Expand'}
                </button>
                <button
                  onClick={() => setDemoted((prev) => new Set([...prev, group.group_id]))}
                  className="text-sm text-yellow-400 hover:text-yellow-300"
                >
                  Move to Review
                </button>
              </div>
            </div>

            {expanded.has(group.group_id) && (
              <div className="mt-3 pt-3 border-t border-gray-700 space-y-2">
                <p className="text-xs text-gray-500">Click to change winner:</p>
                {group.members.map((m) => (
                  <button
                    key={m.id}
                    onClick={() => setOverrides((prev) => ({ ...prev, [group.group_id]: m.id }))}
                    className={`block w-full text-left p-2 rounded text-sm ${
                      m.id === (overrides[group.group_id] || group.winner_id)
                        ? 'bg-green-800 border border-green-600'
                        : 'bg-gray-750 hover:bg-gray-700'
                    }`}
                  >
                    <pre className="whitespace-pre-wrap text-gray-200">{JSON.stringify(m, null, 2)}</pre>
                  </button>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create DedupStepReview**

```tsx
// frontend/src/pages/knowledge-base/DedupStepReview.tsx
import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { api } from '../../api/client';

interface ReviewGroup {
  group_id: string;
  winner_id: number;
  members: any[];
  similarity_score: number;
  reason: string;
}

type Decision = 'merge' | 'not_duplicate' | 'delete';

interface Props {
  entityType: string;
  groups: ReviewGroup[];
  onComplete: () => void;
}

export default function DedupStepReview({ entityType, groups, onComplete }: Props) {
  const [decisions, setDecisions] = useState<Record<string, { action: Decision; winner_id?: number }>>({});

  const applyMutation = useMutation({
    mutationFn: async () => {
      const merges: { winner_id: number; loser_ids: number[] }[] = [];
      const deletes: number[] = [];

      for (const group of groups) {
        const d = decisions[group.group_id];
        if (!d || d.action === 'not_duplicate') continue;
        if (d.action === 'merge') {
          const winnerId = d.winner_id || group.winner_id;
          merges.push({
            winner_id: winnerId,
            loser_ids: group.members.filter((m) => m.id !== winnerId).map((m) => m.id),
          });
        } else if (d.action === 'delete') {
          deletes.push(...group.members.map((m) => m.id));
        }
      }

      if (merges.length > 0 || deletes.length > 0) {
        await api.post('/kb/dedup/apply', { entity_type: entityType, merges, deletes });
      }
    },
    onSuccess: () => onComplete(),
  });

  const allDecided = groups.every((g) => decisions[g.group_id]);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-yellow-400">Needs Review</h3>
          <p className="text-sm text-gray-400">{groups.length} group(s) — AI is unsure</p>
        </div>
        <button
          onClick={() => applyMutation.mutate()}
          disabled={!allDecided || applyMutation.isPending}
          className="px-6 py-2 bg-yellow-600 hover:bg-yellow-500 text-white rounded-lg disabled:opacity-50"
        >
          {applyMutation.isPending ? 'Applying...' : 'Apply Decisions'}
        </button>
      </div>

      <div className="space-y-4">
        {groups.map((group) => {
          const decision = decisions[group.group_id];
          return (
            <div key={group.group_id} className="bg-gray-800 rounded-lg border border-yellow-700/30 p-4">
              <div className="flex items-center justify-between mb-3">
                <p className="text-sm text-gray-400">
                  {group.reason} — {Math.round(group.similarity_score * 100)}% similar
                </p>
              </div>

              {/* Side-by-side comparison */}
              <div className="grid grid-cols-2 gap-3 mb-4">
                {group.members.map((m) => (
                  <div
                    key={m.id}
                    onClick={() =>
                      setDecisions((prev) => ({
                        ...prev,
                        [group.group_id]: { action: 'merge', winner_id: m.id },
                      }))
                    }
                    className={`p-3 rounded border cursor-pointer ${
                      decision?.action === 'merge' && decision.winner_id === m.id
                        ? 'border-green-500 bg-green-900/20'
                        : 'border-gray-700 hover:border-gray-500'
                    }`}
                  >
                    <pre className="text-sm text-gray-200 whitespace-pre-wrap">
                      {m.text || m.name || m.employer || JSON.stringify(m, null, 2)}
                    </pre>
                  </div>
                ))}
              </div>

              {/* Action buttons */}
              <div className="flex gap-2">
                <button
                  onClick={() => setDecisions((prev) => ({ ...prev, [group.group_id]: { action: 'not_duplicate' } }))}
                  className={`px-3 py-1 rounded text-sm ${
                    decision?.action === 'not_duplicate'
                      ? 'bg-blue-700 text-blue-100'
                      : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                  }`}
                >
                  Not Duplicates
                </button>
                <button
                  onClick={() => setDecisions((prev) => ({ ...prev, [group.group_id]: { action: 'delete' } }))}
                  className={`px-3 py-1 rounded text-sm ${
                    decision?.action === 'delete'
                      ? 'bg-red-700 text-red-100'
                      : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                  }`}
                >
                  Delete Both
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Create DedupStepJunk**

```tsx
// frontend/src/pages/knowledge-base/DedupStepJunk.tsx
import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { api } from '../../api/client';

interface JunkItem {
  id: number;
  content_preview: string;
  reason: string;
  suggested_reclassify?: { target_table: string; career_history_id?: number };
}

type Decision = 'delete' | 'reclassify' | 'keep';

interface Props {
  entityType: string;
  items: JunkItem[];
  onComplete: () => void;
}

export default function DedupStepJunk({ entityType, items, onComplete }: Props) {
  const [decisions, setDecisions] = useState<Record<number, Decision>>({});

  const applyMutation = useMutation({
    mutationFn: async () => {
      const deletes: number[] = [];
      const reclassifications: any[] = [];

      for (const item of items) {
        const d = decisions[item.id] || 'delete'; // default to delete for junk
        if (d === 'delete') {
          deletes.push(item.id);
        } else if (d === 'reclassify' && item.suggested_reclassify) {
          reclassifications.push({
            id: item.id,
            target_table: item.suggested_reclassify.target_table,
            career_history_id: item.suggested_reclassify.career_history_id,
          });
        }
        // 'keep' = do nothing
      }

      if (deletes.length > 0 || reclassifications.length > 0) {
        await api.post('/kb/dedup/apply', {
          entity_type: entityType,
          deletes,
          reclassifications,
        });
      }
    },
    onSuccess: () => onComplete(),
  });

  if (items.length === 0) {
    onComplete();
    return null;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-red-400">Junk / Delete</h3>
          <p className="text-sm text-gray-400">{items.length} item(s) flagged</p>
        </div>
        <button
          onClick={() => applyMutation.mutate()}
          disabled={applyMutation.isPending}
          className="px-6 py-2 bg-red-600 hover:bg-red-500 text-white rounded-lg disabled:opacity-50"
        >
          {applyMutation.isPending ? 'Applying...' : 'Confirm'}
        </button>
      </div>

      <div className="space-y-3">
        {items.map((item) => {
          const decision = decisions[item.id] || 'delete';
          return (
            <div key={item.id} className="bg-gray-800 rounded-lg border border-red-700/30 p-4">
              <p className="text-sm text-gray-200 mb-2">{item.content_preview}</p>
              <p className="text-xs text-gray-500 mb-3">Reason: {item.reason}</p>

              <div className="flex gap-2">
                <button
                  onClick={() => setDecisions((prev) => ({ ...prev, [item.id]: 'delete' }))}
                  className={`px-3 py-1 rounded text-sm ${
                    decision === 'delete' ? 'bg-red-700 text-red-100' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                  }`}
                >
                  Delete
                </button>
                {item.suggested_reclassify && (
                  <button
                    onClick={() => setDecisions((prev) => ({ ...prev, [item.id]: 'reclassify' }))}
                    className={`px-3 py-1 rounded text-sm ${
                      decision === 'reclassify'
                        ? 'bg-blue-700 text-blue-100'
                        : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                    }`}
                  >
                    Move to {item.suggested_reclassify.target_table}
                  </button>
                )}
                <button
                  onClick={() => setDecisions((prev) => ({ ...prev, [item.id]: 'keep' }))}
                  className={`px-3 py-1 rounded text-sm ${
                    decision === 'keep' ? 'bg-gray-600 text-gray-100' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                  }`}
                >
                  Keep
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/knowledge-base/DedupStepAutoMerge.tsx frontend/src/pages/knowledge-base/DedupStepReview.tsx frontend/src/pages/knowledge-base/DedupStepJunk.tsx
git commit -m "feat: dedup wizard sub-stages — auto-merge, review, junk components"
```

---

## Task 8: Frontend — Summary-Specific Components

Role type editor and content split review for the Summaries step.

**Files:**
- Create: `frontend/src/pages/knowledge-base/SummaryRoleTypeEditor.tsx`
- Create: `frontend/src/pages/knowledge-base/SummarySplitReview.tsx`

- [ ] **Step 1: Create SummaryRoleTypeEditor**

```tsx
// frontend/src/pages/knowledge-base/SummaryRoleTypeEditor.tsx
import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { api } from '../../api/client';

interface RoleTypeSuggestion {
  current: string;
  suggested: string | null;
  reason: string;
}

interface Props {
  suggestions: RoleTypeSuggestion[];
  onComplete: () => void;
}

export default function SummaryRoleTypeEditor({ suggestions, onComplete }: Props) {
  const [assignments, setAssignments] = useState<Record<string, string>>(() => {
    const initial: Record<string, string> = {};
    for (const s of suggestions) {
      initial[s.current] = s.suggested || s.current;
    }
    return initial;
  });

  const mutation = useMutation({
    mutationFn: () => api.post('/kb/dedup/summaries/role-types', { reassignments: assignments }),
    onSuccess: () => onComplete(),
  });

  if (suggestions.length === 0) {
    onComplete();
    return null;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-purple-400">Summary Role Types</h3>
          <p className="text-sm text-gray-400">Assign meaningful labels to auto-generated role types</p>
        </div>
        <button
          onClick={() => mutation.mutate()}
          disabled={mutation.isPending}
          className="px-6 py-2 bg-purple-600 hover:bg-purple-500 text-white rounded-lg disabled:opacity-50"
        >
          {mutation.isPending ? 'Saving...' : 'Save & Continue'}
        </button>
      </div>

      <div className="space-y-3">
        {suggestions.map((s) => (
          <div key={s.current} className="bg-gray-800 rounded-lg border border-gray-700 p-4 flex items-center gap-4">
            <div className="flex-shrink-0">
              <span className="text-sm text-gray-500">Current:</span>
              <span className="ml-2 px-2 py-1 bg-gray-700 rounded text-sm text-gray-300">{s.current}</span>
            </div>
            <span className="text-gray-600">→</span>
            <div className="flex-1">
              <input
                type="text"
                value={assignments[s.current] || ''}
                onChange={(e) => setAssignments((prev) => ({ ...prev, [s.current]: e.target.value }))}
                placeholder="e.g., CTO, VP Engineering"
                className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-sm text-white placeholder-gray-500 focus:border-purple-500 focus:outline-none"
              />
            </div>
            <span className="text-xs text-gray-500 max-w-xs">{s.reason}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create SummarySplitReview**

```tsx
// frontend/src/pages/knowledge-base/SummarySplitReview.tsx
import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { api } from '../../api/client';

interface MixedContent {
  id: number;
  original_text: string;
  summary_portion: string;
  bullet_portions: string[];
  reason: string;
}

interface Props {
  mixedContent: MixedContent[];
  onComplete: () => void;
}

export default function SummarySplitReview({ mixedContent, onComplete }: Props) {
  const [excluded, setExcluded] = useState<Set<number>>(new Set());

  const mutation = useMutation({
    mutationFn: async () => {
      const splits = mixedContent
        .filter((mc) => !excluded.has(mc.id))
        .map((mc) => ({
          id: mc.id,
          keep_summary_text: mc.summary_portion,
          extract_bullets: mc.bullet_portions,
          career_history_id: null,
        }));

      if (splits.length > 0) {
        await api.post('/kb/dedup/summaries/split', { splits });
      }
    },
    onSuccess: () => onComplete(),
  });

  if (mixedContent.length === 0) {
    onComplete();
    return null;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-orange-400">Summary Content Splitting</h3>
          <p className="text-sm text-gray-400">
            {mixedContent.length} summary(ies) contain mixed content — bullet text will be extracted
          </p>
        </div>
        <button
          onClick={() => mutation.mutate()}
          disabled={mutation.isPending}
          className="px-6 py-2 bg-orange-600 hover:bg-orange-500 text-white rounded-lg disabled:opacity-50"
        >
          {mutation.isPending ? 'Splitting...' : 'Confirm Splits'}
        </button>
      </div>

      <div className="space-y-4">
        {mixedContent.map((mc) => {
          const isExcluded = excluded.has(mc.id);
          return (
            <div key={mc.id} className={`bg-gray-800 rounded-lg border p-4 ${isExcluded ? 'border-gray-700 opacity-50' : 'border-orange-700/30'}`}>
              <div className="flex items-center justify-between mb-3">
                <p className="text-xs text-gray-500">{mc.reason}</p>
                <button
                  onClick={() => setExcluded((prev) => {
                    const next = new Set(prev);
                    next.has(mc.id) ? next.delete(mc.id) : next.add(mc.id);
                    return next;
                  })}
                  className="text-sm text-gray-400 hover:text-white"
                >
                  {isExcluded ? 'Include' : 'Skip'}
                </button>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-xs text-green-400 mb-1 font-semibold">Keep as Summary:</p>
                  <div className="bg-green-900/20 border border-green-800/30 rounded p-3 text-sm text-gray-200">
                    {mc.summary_portion || <span className="italic text-gray-500">Nothing to keep</span>}
                  </div>
                </div>
                <div>
                  <p className="text-xs text-blue-400 mb-1 font-semibold">Extract as Bullets:</p>
                  <div className="bg-blue-900/20 border border-blue-800/30 rounded p-3 space-y-1">
                    {mc.bullet_portions.map((bp, i) => (
                      <p key={i} className="text-sm text-gray-200">• {bp}</p>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/knowledge-base/SummaryRoleTypeEditor.tsx frontend/src/pages/knowledge-base/SummarySplitReview.tsx
git commit -m "feat: summary-specific wizard components — role type editor, content split review"
```

---

## Task 9: Frontend — Wire Into KnowledgeBase Page

Connect the AI toggle and wizard button to the existing KB page.

**Files:**
- Modify: `frontend/src/pages/knowledge-base/KnowledgeBase.tsx`

- [ ] **Step 1: Read the current KnowledgeBase.tsx header section**

Read lines 1-80 of `frontend/src/pages/knowledge-base/KnowledgeBase.tsx` to see the exact header structure and imports.

- [ ] **Step 2: Add imports and wizard state**

Add to the imports section of `KnowledgeBase.tsx`:

```tsx
import AiToggle from './AiToggle';
import KbDedupWizard from './KbDedupWizard';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../api/client';
```

Add state inside the component:

```tsx
const [wizardOpen, setWizardOpen] = useState(false);
const { data: settings } = useQuery<{ ai_enabled: boolean }>({
  queryKey: ['settings'],
  queryFn: () => api.get('/settings'),
});
```

- [ ] **Step 3: Add AI toggle and cleanup button to header**

Find the header `<div>` (the one with the page title) and add after the title:

```tsx
<div className="flex items-center gap-4">
  <AiToggle />
  {settings?.ai_enabled && (
    <button
      onClick={() => setWizardOpen(true)}
      className="px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white text-sm rounded-lg"
    >
      Clean Up Knowledge Base
    </button>
  )}
</div>
```

- [ ] **Step 4: Add wizard modal at the end of the component return**

Before the closing `</div>` of the component's return:

```tsx
<KbDedupWizard isOpen={wizardOpen} onClose={() => setWizardOpen(false)} />
```

- [ ] **Step 5: Verify the page renders**

Run: `cd code/frontend && npm run dev`
Navigate to the KB page. Toggle AI on, verify the cleanup button appears.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/knowledge-base/KnowledgeBase.tsx
git commit -m "feat: wire AI toggle + dedup wizard into Knowledge Base page"
```

---

## Task 10: Integration Testing — Full Wizard Flow

End-to-end test of the scan → apply cycle through the API.

**Files:**
- Modify: `tests/test_kb_dedup_routes.py`

- [ ] **Step 1: Write integration test for full scan + apply flow**

```python
# Add to tests/test_kb_dedup_routes.py

def test_full_skill_dedup_flow(client):
    """Scan skills, then apply auto-merge results."""
    # Step 1: Scan
    resp = client.post("/api/kb/dedup/scan", json={"entity_type": "skills", "use_ai": False})
    assert resp.status_code == 200
    data = resp.get_json()

    # Step 2: If there are auto_merge groups, apply them
    if data["auto_merge"]:
        merges = []
        for group in data["auto_merge"]:
            winner_id = group["winner_id"]
            loser_ids = [m["id"] for m in group["members"] if m["id"] != winner_id]
            merges.append({"winner_id": winner_id, "loser_ids": loser_ids})

        resp2 = client.post("/api/kb/dedup/apply", json={
            "entity_type": "skills",
            "merges": merges,
        })
        assert resp2.status_code == 200
        result = resp2.get_json()
        assert result["errors"] == []


def test_career_history_scan(client):
    """Scan career history returns employer_merge and role_merge."""
    resp = client.post("/api/kb/dedup/scan", json={"entity_type": "career_history"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert "employer_merge" in data or "auto_merge" in data


def test_summary_role_type_suggest(client):
    """AI suggests meaningful role types for summaries."""
    resp = client.post("/api/kb/dedup/summaries/suggest-role-types")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "suggestions" in data
```

- [ ] **Step 2: Run integration tests**

Run: `cd code && python -m pytest tests/test_kb_dedup_routes.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_kb_dedup_routes.py
git commit -m "test: integration tests for KB dedup wizard API flow"
```

---

## Task 11: Frontend Manual Testing & Polish

Verify the full wizard flow in the browser.

- [ ] **Step 1: Rebuild and start frontend**

```bash
cd code/frontend && npm run build
cd code && docker compose restart web
```

- [ ] **Step 2: Test the full wizard flow**

1. Navigate to Knowledge Base page
2. Toggle AI Assist ON
3. Click "Clean Up Knowledge Base"
4. Walk through each entity step
5. Verify: scanning spinner, auto-merge groups display, review cards display, junk items display
6. Verify: confirm actions execute (records merge/delete in DB)
7. Verify: skip logic works for entities with no duplicates
8. Verify: progress bar updates correctly
9. Verify: cancel exits cleanly

- [ ] **Step 3: Fix any issues found during testing**

- [ ] **Step 4: Commit any fixes**

```bash
git add -A
git commit -m "fix: polish KB dedup wizard after manual testing"
```
