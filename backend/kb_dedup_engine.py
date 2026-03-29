"""KB dedup engine — pure-Python grouping logic for all knowledge-base entity types.

Each public function returns one of:
  - Standard: {"auto_merge": [...], "needs_review": [...], "junk": [...]}
  - Career history: {"employer_merge": [...], "role_merge": [...], "junk": [...]}
  - Summaries: {"auto_merge": [...], "needs_review": [...], "junk": [...],
                "mixed_content": [...], "role_type_suggestions": [...]}

Groups are lists of dicts, each with:
  {"winner": <record>, "members": [<record>, ...]}
  (single-record groups have winner == members[0] and len(members) == 1)
"""

import json
import logging
import re
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Synonym / abbreviation maps
# ---------------------------------------------------------------------------

SKILL_SYNONYMS = {
    "js": "javascript",
    "javascript": "javascript",
    "ts": "typescript",
    "typescript": "typescript",
    "py": "python",
    "python": "python",
    "react.js": "react",
    "react": "react",
    "vue.js": "vue",
    "node.js": "node",
    "nodejs": "node",
    "pm": "project management",
    "k8s": "kubernetes",
    "kubernetes": "kubernetes",
    "aws": "amazon web services",
    "amazon web services": "amazon web services",
    "gcp": "google cloud platform",
    "google cloud": "google cloud platform",
    "azure": "microsoft azure",
    "ms azure": "microsoft azure",
    "ml": "machine learning",
    "ai": "artificial intelligence",
    "ci/cd": "ci/cd",
    "cicd": "ci/cd",
    "c#": "c#",
    "csharp": "c#",
    "cpp": "c++",
    "c++": "c++",
    "sql": "sql",
    "postgres": "postgresql",
    "postgresql": "postgresql",
    "mongo": "mongodb",
    "mongodb": "mongodb",
    "tf": "terraform",
    "terraform": "terraform",
}

CERT_SYNONYMS = {
    "pmp": "project management professional",
    "project management professional": "project management professional",
    "csm": "certified scrummaster",
    "certified scrummaster": "certified scrummaster",
    "csa": "certified scrum advanced",
    "aws-saa": "aws solutions architect associate",
    "aws solutions architect": "aws solutions architect associate",
    "cka": "certified kubernetes administrator",
    "ckad": "certified kubernetes application developer",
    "cissp": "certified information systems security professional",
    "cpa": "certified public accountant",
    "shrm-cp": "shrm certified professional",
    "shrm-scp": "shrm senior certified professional",
    "itil": "itil foundation",
    "six sigma green belt": "six sigma green belt",
    "six sigma black belt": "six sigma black belt",
}

# Suffixes/tokens to strip when normalising employer names
_EMPLOYER_STRIP = re.compile(
    r"\b(corp|corporation|inc|incorporated|llc|ltd|limited|co|company|"
    r"group|holdings|international|intl|solutions|services|technologies|"
    r"technology|systems|associates|partners|global|worldwide|enterprises|"
    r"ventures|consulting|consultants)\.?\b",
    re.IGNORECASE,
)

# Title abbreviation expansions
_TITLE_ABBREVS = {
    r"\bsr\.?\b": "senior",
    r"\bjr\.?\b": "junior",
    r"\bdir\.?\b": "director",
    r"\bvp\b": "vice president",
    r"\bevp\b": "executive vice president",
    r"\bsvp\b": "senior vice president",
    r"\bmgr\.?\b": "manager",
    r"\beng\.?\b": "engineer",
    r"\bdev\.?\b": "developer",
    r"\barch\.?\b": "architect",
    r"\bspec\.?\b": "specialist",
    r"\bcoord\.?\b": "coordinator",
    r"\banalyst\b": "analyst",
    r"\btech\.?\b": "technical",
    r"\bproj\.?\b": "project",
    r"\bassoc\.?\b": "associate",
}

# Connector words to remove from titles before comparison
_TITLE_CONNECTORS = re.compile(r"\b(of|the|and|&|a|an|for|in|at|to)\b", re.IGNORECASE)

# Action verbs common at the start of resume bullets
_ACTION_VERBS = {
    "led", "built", "designed", "developed", "managed", "delivered", "launched",
    "created", "owned", "drove", "reduced", "increased", "improved", "scaled",
    "implemented", "deployed", "negotiated", "partnered", "established", "grew",
    "architected", "authored", "coordinated", "directed", "executed", "facilitated",
    "generated", "identified", "oversaw", "produced", "resolved", "spearheaded",
    "streamlined", "transformed", "utilized", "advised", "aligned", "analyzed",
    "automated", "championed", "collaborated", "consolidated", "crafted", "defined",
    "eliminated", "enabled", "engineered", "expanded", "founded", "hired",
    "influenced", "integrated", "introduced", "maintained", "mentored", "migrated",
    "modeled", "monitored", "optimized", "orchestrated", "planned", "prioritized",
    "recruited", "refactored", "restructured", "secured", "shaped", "shipped",
    "standardized", "supported", "trained", "unified",
}

# Institution normalisation patterns
_INSTITUTION_ABBREVS = [
    (re.compile(r"\buniv\.?\s+of\b", re.IGNORECASE), "university of"),
    (re.compile(r"\buniv\.?\b", re.IGNORECASE), "university"),
    (re.compile(r"\bcoll\.?\b", re.IGNORECASE), "college"),
    (re.compile(r"\binst\.?\b", re.IGNORECASE), "institute"),
    (re.compile(r"\btech\.?\b", re.IGNORECASE), "technology"),
    (re.compile(r"\bstate\b", re.IGNORECASE), "state"),
]


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _normalize_name(name: str) -> str:
    """Lowercase, strip, resolve SKILL_SYNONYMS."""
    if not name:
        return ""
    key = name.strip().lower()
    return SKILL_SYNONYMS.get(key, key)


def _completeness_score(record: dict, fields: list) -> int:
    """Count non-null, non-empty values among the listed fields."""
    score = 0
    for f in fields:
        v = record.get(f)
        if v is not None and v != "" and v != []:
            score += 1
    return score


def _pick_winner(members: list, fields: list) -> dict:
    """Return the member with the highest completeness score. Tie-breaks to first."""
    if not members:
        return {}
    return max(members, key=lambda r: _completeness_score(r, fields))


def _employer_normalize(name: str) -> str:
    """Strip legal suffixes, punctuation, extra whitespace; lowercase."""
    if not name:
        return ""
    n = _EMPLOYER_STRIP.sub("", name)
    n = re.sub(r"\.com\b", "", n, flags=re.IGNORECASE)
    n = re.sub(r"[,\.\-]", " ", n)
    n = re.sub(r"\s+", " ", n).strip().lower()
    return n


def _title_normalize(title: str) -> str:
    """Expand abbreviations, remove connectors, collapse whitespace; lowercase."""
    if not title:
        return ""
    t = title.lower()
    for pattern, replacement in _TITLE_ABBREVS.items():
        t = re.sub(pattern, replacement, t, flags=re.IGNORECASE)
    t = _TITLE_CONNECTORS.sub("", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _dates_overlap(a: dict, b: dict) -> bool:
    """Return True if two records' date ranges overlap.

    Uses start_date / end_date keys (strings like "2020-01" or "2020").
    A missing end_date is treated as present (ongoing).
    """
    def _year(val) -> int | None:
        if not val:
            return None
        m = re.search(r"(\d{4})", str(val))
        return int(m.group(1)) if m else None

    a_start = _year(a.get("start_date"))
    a_end = _year(a.get("end_date")) or 9999
    b_start = _year(b.get("start_date"))
    b_end = _year(b.get("end_date")) or 9999

    if a_start is None or b_start is None:
        return False  # can't determine overlap without start dates

    return a_start <= b_end and b_start <= a_end


def _institution_normalize(name: str) -> str:
    """Normalize university/institution names for comparison."""
    if not name:
        return ""
    n = name.lower()
    for pattern, replacement in _INSTITUTION_ABBREVS:
        n = pattern.sub(replacement, n)
    n = re.sub(r"[,\.\-]", " ", n)
    n = re.sub(r"\s+", " ", n).strip()
    return n


def _looks_like_bullet(text: str) -> bool:
    """Heuristic: True if text looks like a resume bullet rather than a summary paragraph.

    Criteria (for strings under 200 chars): starts with an action verb OR contains a metric.
    """
    if not text or len(text) > 200:
        return False
    first_word = text.strip().split()[0].lower().rstrip(".,;:") if text.strip() else ""
    has_action_verb = first_word in _ACTION_VERBS
    has_metric = bool(re.search(r"[\$%]|\b\d+[xX]\b|\b\d+\s*(percent|million|billion|k\b)", text))
    return has_action_verb or has_metric


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def _make_group(winner: dict, members: list) -> dict:
    return {"winner": winner, "members": members}


# ---------------------------------------------------------------------------
# 1. Skills
# ---------------------------------------------------------------------------

def _classify_skill(entry: dict) -> dict | None:
    """Classify a skill entry. Returns a junk dict with action info, or None if clean.

    Possible actions in returned dict:
    - "delete": junk, should be removed
    - "split": contains multiple skills, should be split into individual entries
    - "reclassify": belongs in another table (education, etc.)
    """
    n = (entry.get("name") or "").strip()
    if not n:
        return {"id": entry.get("id", 0), "content_preview": "", "reason": "Empty skill name", "action": "delete"}

    lower = n.lower()

    # Slash-separated skill lists — split into individual skills
    if n.count("/") >= 3:
        parts = [p.strip() for p in n.split("/") if p.strip()]
        return {
            "id": entry.get("id", 0), "content_preview": n[:100],
            "reason": f"Slash-separated list — contains {len(parts)} skills",
            "action": "split", "extracted_skills": parts,
        }

    # Semicolon-separated lists — split into individual skills
    if n.count(";") >= 2:
        parts = [p.strip() for p in n.split(";") if p.strip()]
        return {
            "id": entry.get("id", 0), "content_preview": n[:100],
            "reason": f"Semicolon-separated list — contains {len(parts)} skills",
            "action": "split", "extracted_skills": parts,
        }

    # Education entry that landed in skills — reclassify
    edu_markers = ("mba", "phd", "ph.d", "m.s.", "b.s.", "master of business", "bachelor of")
    if any(lower.startswith(m) or f" {m}" in lower for m in edu_markers):
        return {
            "id": entry.get("id", 0), "content_preview": n[:100],
            "reason": "Looks like an education entry, not a skill",
            "action": "reclassify",
            "suggested_reclassify": {"target_table": "education"},
        }

    # Too long — likely a sentence fragment
    if len(n) > 50:
        return {"id": entry.get("id", 0), "content_preview": n[:100],
                "reason": f"Too long ({len(n)} chars) — likely a sentence fragment", "action": "delete"}

    # Sentence-ending punctuation
    if any(c in n for c in "!?"):
        return {"id": entry.get("id", 0), "content_preview": n[:100],
                "reason": "Contains sentence punctuation", "action": "delete"}
    if "." in n and len(n) > 35:
        return {"id": entry.get("id", 0), "content_preview": n[:100],
                "reason": "Long text with periods — likely a sentence fragment", "action": "delete"}

    # Gerund/verb-starting sentence fragments
    frag_starts = (
        "ensuring", "fostering", "leveraging", "whether", "through", "working",
        "supporting", "particularly", "performing", "utilizing", "managing",
        "leading", "building", "driving", "delivering", "overseeing",
        "architecting", "designing", "implementing", "developing",
    )
    if any(lower.startswith(w) for w in frag_starts) and " " in n:
        return {"id": entry.get("id", 0), "content_preview": n[:100],
                "reason": "Starts with gerund/verb — sentence fragment", "action": "delete"}

    # Descriptive phrases
    desc_phrases = (
        "let's connect", "about me", "i'm always", "open to", "feel free",
        "don't hesitate", "years of experience", "proven track record",
    )
    if any(p in lower for p in desc_phrases):
        return {"id": entry.get("id", 0), "content_preview": n[:100],
                "reason": "Descriptive phrase, not a skill", "action": "delete"}

    # Location patterns
    import re
    if re.match(r".*,\s*[A-Z]{2}\b", n):
        return {"id": entry.get("id", 0), "content_preview": n[:100],
                "reason": "Looks like a location (City, ST)", "action": "delete"}

    return None


def group_skills(skills: list) -> dict:
    """Group skills by name.

    auto_merge  — same canonical name (case-insensitive / synonym resolution)
    needs_review — different canonical names but same synonym canonical (abbreviation)
    junk — entries that are not real skills, with actionable suggestions (split, reclassify, delete)
    """
    FIELDS = ["name", "category", "proficiency", "last_used_year", "years_experience"]

    # First pass: classify each skill
    junk = []
    clean_skills = []
    for s in skills:
        classification = _classify_skill(s)
        if classification:
            junk.append(classification)
        else:
            clean_skills.append(s)

    # Bucket by canonical name (only clean skills)
    canonical_buckets: dict[str, list] = {}
    for s in clean_skills:
        key = _normalize_name(s.get("name", ""))
        canonical_buckets.setdefault(key, []).append(s)

    auto_merge = []
    needs_review = []

    for canon, members in canonical_buckets.items():
        winner = _pick_winner(members, FIELDS)
        if len(members) > 1:
            raw_names = {m.get("name", "").strip().lower() for m in members}
            if len(raw_names) == 1:
                auto_merge.append(_make_group(winner, members))
            else:
                needs_review.append(_make_group(winner, members))

    return {"auto_merge": auto_merge, "needs_review": needs_review, "junk": junk}


# ---------------------------------------------------------------------------
# 2. Education
# ---------------------------------------------------------------------------

def _classify_education(entry: dict) -> dict | None:
    """Classify an education entry. Returns junk dict with action, or None if clean."""
    degree = (entry.get("degree") or "").strip()
    institution = (entry.get("institution") or "").strip()
    field = (entry.get("field") or "").strip()
    eid = entry.get("id", 0)
    preview = f"{degree} — {institution}"[:100]

    if not degree and not institution:
        return {"id": eid, "content_preview": preview, "reason": "Missing both degree and institution", "action": "delete"}

    combined = f"{degree} {institution} {field}".lower()

    # Awards — reclassify as career achievement/bullet
    if "award" in combined:
        return {"id": eid, "content_preview": preview,
                "reason": "Award entry, not education",
                "action": "reclassify", "suggested_reclassify": {"target_table": "bullets"}}

    # Job descriptions / experience entries
    exp_markers = ("consult", "developed", "grew", "managed", "secured", "worked with",
                   "as the senior", "as japan", "technologies:")
    matched = next((m for m in exp_markers if m in combined), None)
    if matched:
        return {"id": eid, "content_preview": preview,
                "reason": f"Job description/experience entry (contains '{matched}')",
                "action": "reclassify", "suggested_reclassify": {"target_table": "bullets"}}

    # Volunteer, memberships, speaker — not education
    non_edu_markers = ("volunteer", "member", "speaker", "about me", "hobby",
                       "hobbies", "objective", "summary", "profile", "reference")
    matched = next((m for m in non_edu_markers if m in combined), None)
    if matched:
        return {"id": eid, "content_preview": preview,
                "reason": f"Non-education entry (contains '{matched}')", "action": "delete"}

    # Very long degree names
    if len(degree) > 80:
        return {"id": eid, "content_preview": preview,
                "reason": f"Degree name too long ({len(degree)} chars) — likely misclassified",
                "action": "delete"}

    # No institution with long degree text
    if not institution and len(degree) > 30:
        return {"id": eid, "content_preview": preview,
                "reason": "Long degree text with no institution", "action": "delete"}

    return None


def group_education(entries: list) -> dict:
    """Group education by normalized institution + degree. Detect junk entries."""
    FIELDS = ["institution", "degree", "field_of_study", "start_date", "end_date",
              "gpa", "honors", "location"]

    # First pass: classify each entry
    junk = []
    clean_entries = []
    for e in entries:
        classification = _classify_education(e)
        if classification:
            junk.append(classification)
        else:
            clean_entries.append(e)

    # Dedup: group by normalized institution + degree
    buckets: dict[tuple, list] = {}
    for e in clean_entries:
        inst = _institution_normalize(e.get("institution", ""))
        deg = (e.get("degree") or "").strip().lower()
        key = (inst, deg)
        buckets.setdefault(key, []).append(e)

    auto_merge = []
    needs_review = []
    for key, members in buckets.items():
        winner = _pick_winner(members, FIELDS)
        if len(members) > 1:
            auto_merge.append(_make_group(winner, members))

    # Also check for near-duplicate institutions with similar degrees
    inst_buckets: dict[str, list] = {}
    for e in clean_entries:
        inst = _institution_normalize(e.get("institution", ""))
        inst_buckets.setdefault(inst, []).append(e)

    for inst, members in inst_buckets.items():
        if len(members) < 2:
            continue
        # Check pairs with similar (but not identical) degree names
        for i, a in enumerate(members):
            for b in members[i+1:]:
                deg_a = (a.get("degree") or "").strip().lower()
                deg_b = (b.get("degree") or "").strip().lower()
                if deg_a == deg_b:
                    continue  # already caught by exact dedup
                sim = _similarity(deg_a, deg_b)
                if sim >= 0.75:
                    winner = _pick_winner([a, b], FIELDS)
                    needs_review.append({
                        "winner": winner,
                        "members": [a, b],
                        "similarity_score": round(sim, 3),
                        "reason": f"Similar degrees at same institution: '{a.get('degree')}' vs '{b.get('degree')}'",
                    })

    return {"auto_merge": auto_merge, "needs_review": needs_review, "junk": junk}


# ---------------------------------------------------------------------------
# 3. Certifications
# ---------------------------------------------------------------------------

def _classify_certification(entry: dict) -> dict | None:
    """Classify a certification entry. Returns junk dict with action, or None if clean."""
    name = (entry.get("name") or "").strip()
    cid = entry.get("id", 0)

    if not name:
        return {"id": cid, "content_preview": "", "reason": "Empty certification name", "action": "delete"}

    lower = name.lower()

    # Compound certs with slash or semicolons — split
    if name.count("/") >= 2 and len(name) > 50:
        parts = [p.strip() for p in name.split("/") if p.strip()]
        return {"id": cid, "content_preview": name[:100],
                "reason": f"Compound certification — contains {len(parts)} certs",
                "action": "split", "extracted_certs": parts}

    # Very long names with URLs
    if len(name) > 80:
        return {"id": cid, "content_preview": name[:100],
                "reason": f"Too long ({len(name)} chars) — likely misclassified", "action": "delete"}

    # Sentence fragments
    if any(c in name for c in "!?") or ("." in name and len(name) > 40 and "http" not in lower):
        return {"id": cid, "content_preview": name[:100],
                "reason": "Contains punctuation — likely a sentence fragment", "action": "delete"}

    # Non-certifications
    non_cert_markers = ("award", "volunteer", "speaker", "about me", "summary",
                        "experience", "hobby", "objective", "reference")
    matched = next((m for m in non_cert_markers if m in lower), None)
    if matched:
        return {"id": cid, "content_preview": name[:100],
                "reason": f"Not a certification (contains '{matched}')", "action": "delete"}

    return None


def group_certifications(certs: list) -> dict:
    """Group certifications by name (exact = auto_merge, synonym = needs_review). Detect junk."""
    FIELDS = ["name", "issuer", "issued_date", "expiry_date", "is_active", "cert_id"]

    def _cert_canon(name: str) -> str:
        key = (name or "").strip().lower()
        return CERT_SYNONYMS.get(key, key)

    def _cert_winner(members: list) -> dict:
        active = [m for m in members if m.get("is_active")]
        pool = active if active else members
        return _pick_winner(pool, FIELDS)

    # First pass: classify each cert
    junk = []
    clean_certs = []
    for c in certs:
        classification = _classify_certification(c)
        if classification:
            junk.append(classification)
        else:
            clean_certs.append(c)

    # Exact (case-insensitive) name buckets
    exact_buckets: dict[str, list] = {}
    for c in clean_certs:
        key = (c.get("name") or "").strip().lower()
        exact_buckets.setdefault(key, []).append(c)

    auto_merge = []
    needs_review = []

    for key, members in exact_buckets.items():
        if len(members) > 1:
            winner = _cert_winner(members)
            auto_merge.append(_make_group(winner, members))

    # Synonym grouping
    canon_buckets: dict[str, list] = {}
    for key, members in exact_buckets.items():
        if len(members) == 1:
            canon = _cert_canon(key)
            canon_buckets.setdefault(canon, []).append(members[0])

    for canon, members in canon_buckets.items():
        if len(members) > 1:
            winner = _cert_winner(members)
            needs_review.append(_make_group(winner, members))

    return {"auto_merge": auto_merge, "needs_review": needs_review, "junk": junk}


# ---------------------------------------------------------------------------
# 4. Career History
# ---------------------------------------------------------------------------

def group_career_history(jobs: list) -> dict:
    """Two-phase grouping: employer_merge then role_merge.

    employer_merge — jobs sharing a normalized employer name
    role_merge     — within same employer, jobs with similar title + overlapping dates
    junk           — records missing both employer and title
    """
    EMPLOYER_FIELDS = ["company", "title", "start_date", "end_date", "location",
                       "description", "employment_type"]
    ROLE_FIELDS = ["title", "start_date", "end_date", "location", "description",
                   "employment_type", "team", "reports_to"]

    junk = []
    valid = []
    for j in jobs:
        emp = j.get("company") or j.get("employer") or ""
        title = j.get("title") or ""
        if not emp.strip() and not title.strip():
            junk.append(_make_group(j, [j]))
        else:
            valid.append(j)

    # Phase A: employer grouping
    emp_buckets: dict[str, list] = {}
    for j in valid:
        raw_emp = j.get("company") or j.get("employer") or ""
        key = _employer_normalize(raw_emp)
        emp_buckets.setdefault(key, []).append(j)

    employer_merge = []
    for key, members in emp_buckets.items():
        # Only flag as employer_merge when raw names actually differ
        raw_names = set((m.get("company") or m.get("employer") or "").strip() for m in members)
        if len(raw_names) > 1:
            canonical_name = max(raw_names, key=len)
            winner = _pick_winner(members, EMPLOYER_FIELDS)
            group = _make_group(winner, members)
            group["canonical_name"] = canonical_name
            employer_merge.append(group)

    # Phase B: role grouping within each employer bucket using union-find connected components.
    # Compare ALL pairs; build adjacency graph where edges mean title_similarity >= 0.80 AND
    # dates_overlap. Then find connected components — each with 2+ members is a role_merge group.
    role_merge = []
    for key, members in emp_buckets.items():
        if len(members) < 2:
            continue
        n = len(members)
        # Union-Find
        parent = list(range(n))

        def _find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def _union(x, y):
            rx, ry = _find(x), _find(y)
            if rx != ry:
                parent[rx] = ry

        # Compare all pairs
        for i in range(n):
            t_i = _title_normalize(members[i].get("title", ""))
            for j in range(i + 1, n):
                t_j = _title_normalize(members[j].get("title", ""))
                if _similarity(t_i, t_j) >= 0.80 and _dates_overlap(members[i], members[j]):
                    _union(i, j)

        # Collect connected components
        components: dict[int, list] = {}
        for i in range(n):
            root = _find(i)
            components.setdefault(root, []).append(members[i])

        for component in components.values():
            if len(component) > 1:
                winner = _pick_winner(component, ROLE_FIELDS)
                role_merge.append(_make_group(winner, component))

    return {"employer_merge": employer_merge, "role_merge": role_merge, "junk": junk}


# ---------------------------------------------------------------------------
# 5. Bullets
# ---------------------------------------------------------------------------

def group_bullets(bullets: list) -> dict:
    """Group bullets by career_history_id, then by text similarity.

    auto_merge   — similarity >= 0.95
    needs_review — 0.75 <= similarity < 0.95
    junk         — shorter than 15 chars or no alpha chars
    """
    auto_merge = []
    needs_review = []
    junk = []

    # Identify junk first
    valid = []
    for b in bullets:
        text = b.get("content") or b.get("text") or b.get("bullet") or ""
        if len(text) < 15 or not re.search(r"[a-zA-Z]", text):
            junk.append(_make_group(b, [b]))
        else:
            valid.append(b)

    # Group by career_history_id
    job_buckets: dict = {}
    no_job = []
    for b in valid:
        jid = b.get("career_history_id")
        if jid is None:
            no_job.append(b)
        else:
            job_buckets.setdefault(jid, []).append(b)

    # Also group bullets with no job_id together
    job_buckets["_no_job"] = no_job

    def _get_text(b):
        return (b.get("content") or b.get("text") or b.get("bullet") or "")[:200]

    def _process_bucket(bucket_items):
        # Pre-compute word sets and texts for fast filtering
        texts = [_get_text(b) for b in bucket_items]
        word_sets = [set(re.findall(r'\w{4,}', t.lower())) for t in texts]

        used = [False] * len(bucket_items)
        for i in range(len(bucket_items)):
            if used[i]:
                continue
            text_i = texts[i]
            words_i = word_sets[i]
            group_members = [bucket_items[i]]
            used[i] = True
            best_sim_for_group = 0.0
            for j in range(i + 1, len(bucket_items)):
                if used[j]:
                    continue
                text_j = texts[j]
                # Quick pre-filters
                len_ratio = min(len(text_i), len(text_j)) / max(len(text_i), len(text_j), 1)
                if len_ratio < 0.6:
                    continue
                words_j = word_sets[j]
                if words_i and words_j:
                    overlap = len(words_i & words_j) / max(len(words_i | words_j), 1)
                    if overlap < 0.4:
                        continue
                sim = _similarity(text_i, text_j)
                if sim >= 0.75:
                    group_members.append(bucket_items[j])
                    used[j] = True
                    best_sim_for_group = max(best_sim_for_group, sim)
            if len(group_members) > 1:
                # Winner = longest bullet (use full text, not truncated)
                winner = max(group_members, key=lambda r: len(r.get("content") or r.get("text") or r.get("bullet") or ""))
                group = _make_group(winner, group_members)
                if best_sim_for_group >= 0.95:
                    auto_merge.append(group)
                else:
                    needs_review.append(group)

    for bucket in job_buckets.values():
        _process_bucket(bucket)

    # Second pass: cross-job dedup using word-set pre-filter for speed.
    # Build word-set fingerprints, only compare bullets with >= 60% word overlap.
    def _words(text):
        return set(re.findall(r'\w{4,}', text.lower()))

    cross_items = []
    for jid, bucket in job_buckets.items():
        for b in bucket:
            text = (b.get("content") or b.get("text") or b.get("bullet") or "")[:200]
            cross_items.append((jid, b, _words(text), text))

    cj_used = set()
    for i in range(len(cross_items)):
        if i in cj_used:
            continue
        jid_i, b_i, words_i, text_i = cross_items[i]
        if not words_i:
            continue
        group_members = [b_i]
        for j in range(i + 1, len(cross_items)):
            if j in cj_used:
                continue
            jid_j, b_j, words_j, text_j = cross_items[j]
            if jid_i == jid_j:
                continue
            # Quick pre-filters before expensive SequenceMatcher
            if not words_j:
                continue
            # Length check — very different lengths can't be 95% similar
            len_ratio = min(len(text_i), len(text_j)) / max(len(text_i), len(text_j), 1)
            if len_ratio < 0.7:
                continue
            overlap = len(words_i & words_j) / max(len(words_i | words_j), 1)
            if overlap < 0.6:
                continue
            if _similarity(text_i, text_j) >= 0.95:
                group_members.append(b_j)
                cj_used.add(j)
        if len(group_members) > 1:
            cj_used.add(i)
            winner = max(group_members, key=lambda r: len(r.get("content") or r.get("text") or r.get("bullet") or ""))
            needs_review.append(_make_group(winner, group_members))

    return {"auto_merge": auto_merge, "needs_review": needs_review, "junk": junk}


# ---------------------------------------------------------------------------
# 6. Summaries
# ---------------------------------------------------------------------------

def group_summaries(summaries: list) -> dict:
    """Group summaries by text similarity. Extended result includes mixed_content
    and role_type_suggestions.

    auto_merge         — similarity >= 0.90
    needs_review       — 0.70 <= similarity < 0.90
    junk               — empty or very short (<20 chars)
    mixed_content      — summaries containing bullet-like content
    role_type_suggestions — summaries whose role_type looks auto-generated
    """
    auto_merge = []
    needs_review = []
    junk = []
    mixed_content = []
    role_type_suggestions = []

    # Flag mixed content and auto role_types
    valid = []
    for s in summaries:
        text = s.get("content") or s.get("text") or s.get("summary") or ""
        if not text or len(text.strip()) < 20:
            junk.append(_make_group(s, [s]))
            continue
        if _looks_like_bullet(text):
            mixed_content.append(s)
        role_type = s.get("role_type") or ""
        if re.match(r"^(auto_|type_)", role_type, re.IGNORECASE):
            role_type_suggestions.append(s)
        valid.append(s)

    # Dedup by similarity
    used = [False] * len(valid)
    for i in range(len(valid)):
        if used[i]:
            continue
        text_i = valid[i].get("content") or valid[i].get("text") or valid[i].get("summary") or ""
        group_members = [valid[i]]
        used[i] = True
        best_sim = 0.0
        for j in range(i + 1, len(valid)):
            if used[j]:
                continue
            text_j = valid[j].get("content") or valid[j].get("text") or valid[j].get("summary") or ""
            sim = _similarity(text_i, text_j)
            if sim >= 0.70:
                group_members.append(valid[j])
                used[j] = True
                best_sim = max(best_sim, sim)
        if len(group_members) > 1:
            FIELDS = ["content", "text", "summary", "role_type", "created_at"]
            winner = _pick_winner(group_members, FIELDS)
            group = _make_group(winner, group_members)
            if best_sim >= 0.90:
                auto_merge.append(group)
            else:
                needs_review.append(group)

    return {
        "auto_merge": auto_merge,
        "needs_review": needs_review,
        "junk": junk,
        "mixed_content": mixed_content,
        "role_type_suggestions": role_type_suggestions,
    }


# ---------------------------------------------------------------------------
# 7. Languages
# ---------------------------------------------------------------------------

def group_languages(languages: list) -> dict:
    """Group languages by case-insensitive name. Winner = one with proficiency set."""
    FIELDS = ["language", "name", "proficiency", "notes"]

    buckets: dict[str, list] = {}
    for lang in languages:
        key = (lang.get("language") or lang.get("name") or "").strip().lower()
        buckets.setdefault(key, []).append(lang)

    auto_merge = []
    for key, members in buckets.items():
        if len(members) > 1:
            # Prefer record with proficiency
            with_prof = [m for m in members if m.get("proficiency")]
            winner = with_prof[0] if with_prof else _pick_winner(members, FIELDS)
            auto_merge.append(_make_group(winner, members))

    return {"auto_merge": auto_merge, "needs_review": [], "junk": []}


# ---------------------------------------------------------------------------
# 8. References
# ---------------------------------------------------------------------------

def group_references(references: list) -> dict:
    """Group references by normalized name + normalized company."""
    FIELDS = ["name", "title", "company", "email", "phone", "relationship", "notes"]

    def _norm_ref_name(name: str) -> str:
        return re.sub(r"\s+", " ", (name or "").strip().lower())

    buckets: dict[tuple, list] = {}
    for r in references:
        name_key = _norm_ref_name(r.get("name", ""))
        company_key = _employer_normalize(r.get("company") or r.get("organization") or "")
        key = (name_key, company_key)
        buckets.setdefault(key, []).append(r)

    auto_merge = []
    for key, members in buckets.items():
        if len(members) > 1:
            winner = _pick_winner(members, FIELDS)
            auto_merge.append(_make_group(winner, members))

    return {"auto_merge": auto_merge, "needs_review": [], "junk": []}


# ---------------------------------------------------------------------------
# AI-Enhanced Grouping
# ---------------------------------------------------------------------------

# Prompt templates

DEDUP_PROMPT_TEMPLATE = """You are a duplicate-detection expert for a resume knowledge base.

Entity type: {entity_type}
Entries (JSON):
{entries_json}

Find groups of duplicates in the above entries. For each group, assign a confidence
score (0.0–1.0) reflecting how certain you are these are duplicates. Also flag any
entries that are junk (empty, nonsensical, or clearly invalid).

Return ONLY valid JSON in this exact shape — no commentary, no markdown fences:
{{
  "groups": [
    {{"ids": [1, 2], "canonical": "best display name", "confidence": 0.95, "reason": "exact match after normalization"}},
    ...
  ],
  "junk": [
    {{"id": 3, "reason": "empty content"}},
    ...
  ]
}}

Rules:
- Only include groups with 2+ members.
- confidence >= 0.85 means clearly the same item.
- confidence 0.50–0.84 means probably the same but needs human review.
- confidence < 0.50 means probably different — do NOT include in groups.
- ids must be the "id" field from each entry exactly as given.
"""

SUMMARY_SPLIT_PROMPT = """You are reviewing a professional summary from a resume knowledge base.

Summary text:
{summary_text}

Determine whether this text contains a mix of a true professional summary paragraph
AND resume bullet content (action-verb phrases with metrics).

Return ONLY valid JSON — no commentary, no markdown fences:
{{
  "summary_portion": "the narrative paragraph portion only",
  "bullet_portions": ["bullet 1", "bullet 2"],
  "is_mixed": true
}}

If the text is purely a summary paragraph with no bullet content, return:
{{
  "summary_portion": "<the full text>",
  "bullet_portions": [],
  "is_mixed": false
}}
"""

ROLE_TYPE_PROMPT = """You are a career data expert. Below are professional summaries with their current role_type labels.

Summaries (JSON):
{summaries_json}

For summaries where the current role_type looks auto-generated (starts with "auto_" or "type_")
or is clearly wrong, suggest a better role_type label (e.g. "CTO", "VP Engineering",
"Product Manager", "Software Engineer", "Data Scientist").

Return ONLY valid JSON — no commentary, no markdown fences:
{{
  "suggestions": [
    {{"id": 1, "current_role_type": "auto_type_1", "suggested_role_type": "VP Engineering"}},
    ...
  ]
}}

Only include entries where you have a meaningful suggestion. If the current label is already
correct, omit it from suggestions.
"""


def _build_entries_json(entity_type: str, entries: list) -> str:
    """Build compact JSON for AI prompts — only relevant fields, long text truncated."""
    _MAX_TEXT = 300  # chars

    def _truncate(val, max_len=_MAX_TEXT):
        if isinstance(val, str) and len(val) > max_len:
            return val[:max_len] + "..."
        return val

    # Field sets per entity type (keep only what helps with dedup)
    _FIELDS = {
        "skills": ["id", "name", "category", "proficiency"],
        "education": ["id", "institution", "degree", "field_of_study", "start_date", "end_date"],
        "certifications": ["id", "name", "issuer", "issued_date", "is_active"],
        "career_history": ["id", "company", "employer", "title", "start_date", "end_date"],
        "bullets": ["id", "content", "text", "bullet", "career_history_id"],
        "summaries": ["id", "content", "text", "summary", "role_type"],
        "languages": ["id", "language", "name", "proficiency"],
        "references": ["id", "name", "company", "organization", "title", "email"],
    }
    fields = _FIELDS.get(entity_type, None)

    compact = []
    for i, entry in enumerate(entries):
        # Use entry's own "id" if present, else use positional index (1-based)
        row: dict = {"id": entry.get("id", i + 1)}
        if fields:
            for f in fields:
                if f == "id":
                    continue
                v = entry.get(f)
                if v is not None and v != "" and v != []:
                    row[f] = _truncate(v)
        else:
            for k, v in entry.items():
                if k != "id":
                    row[k] = _truncate(v)
        compact.append(row)

    return json.dumps(compact, indent=2, default=str)


def _entries_by_id(entries: list) -> dict:
    """Build id->entry lookup dict. Uses positional index (1-based) when no 'id' field."""
    return {entry.get("id", i + 1): entry for i, entry in enumerate(entries)}


def _python_group_for_type(entity_type: str):
    """Return the Python fallback grouping function for an entity type."""
    _MAP = {
        "skills": group_skills,
        "education": group_education,
        "certifications": group_certifications,
        "career_history": group_career_history,
        "bullets": group_bullets,
        "summaries": group_summaries,
        "languages": group_languages,
        "references": group_references,
    }
    return _MAP.get(entity_type)


def _parse_ai_dedup_response(ai_result: dict, entries: list) -> dict:
    """Convert raw AI JSON response into the standard grouping result shape.

    Confidence >= 0.85 -> auto_merge
    Confidence 0.50-0.84 -> needs_review
    Junk items -> junk list
    """
    id_map = _entries_by_id(entries)
    FIELDS = list(entries[0].keys()) if entries else []

    auto_merge = []
    needs_review = []
    junk = []

    for group_def in ai_result.get("groups", []):
        ids = group_def.get("ids", [])
        confidence = float(group_def.get("confidence", 0.0))
        if confidence < 0.50 or len(ids) < 2:
            continue
        members = [id_map[i] for i in ids if i in id_map]
        if len(members) < 2:
            continue
        winner = _pick_winner(members, FIELDS)
        group = _make_group(winner, members)
        group["confidence"] = confidence
        group["reason"] = group_def.get("reason", "")
        if confidence >= 0.85:
            auto_merge.append(group)
        else:
            needs_review.append(group)

    for junk_def in ai_result.get("junk", []):
        jid = junk_def.get("id")
        if jid in id_map:
            entry = id_map[jid]
            grp = _make_group(entry, [entry])
            grp["reason"] = junk_def.get("reason", "")
            junk.append(grp)

    return {"auto_merge": auto_merge, "needs_review": needs_review, "junk": junk}


def ai_enhanced_group(entity_type: str, entries: list) -> dict:
    """AI-enhanced duplicate grouping for any entity type.

    Falls back to Python grouping if AI is unavailable or errors out.

    Args:
        entity_type: One of skills/education/certifications/career_history/
                     bullets/summaries/languages/references
        entries:     List of records to deduplicate

    Returns:
        Standard {"auto_merge": [...], "needs_review": [...], "junk": [...]} dict
        (or career_history shape for that entity type).
        Includes "analysis_mode": "ai"|"rule_based" key.
    """
    from ai_providers.router import route_inference

    python_fn = _python_group_for_type(entity_type)
    if python_fn is None:
        raise ValueError(f"Unknown entity_type: {entity_type!r}")

    entries_json = _build_entries_json(entity_type, entries)
    prompt = DEDUP_PROMPT_TEMPLATE.format(
        entity_type=entity_type,
        entries_json=entries_json,
    )

    def _python_fallback(_ctx):
        return python_fn(entries)

    def _ai_handler(provider):
        raw = provider.generate(prompt, response_format="json")
        if isinstance(raw, str):
            raw = json.loads(raw)
        return _parse_ai_dedup_response(raw, entries)

    return route_inference(
        task=f"dedup_group_{entity_type}",
        context={"entity_type": entity_type, "count": len(entries)},
        python_fallback=_python_fallback,
        ai_handler=_ai_handler,
    )


def ai_split_summary(summary_text: str) -> dict:
    """AI-powered summary content splitting.

    Separates professional summary narrative from embedded bullet content.
    Falls back to heuristic _looks_like_bullet() splitting if AI unavailable.

    Returns:
        {"summary_portion": str, "bullet_portions": [...], "is_mixed": bool,
         "analysis_mode": "ai"|"rule_based"}
    """
    from ai_providers.router import route_inference

    prompt = SUMMARY_SPLIT_PROMPT.format(summary_text=summary_text)

    def _python_fallback(_ctx):
        lines = [ln.strip() for ln in summary_text.splitlines() if ln.strip()]
        bullets = [ln for ln in lines if _looks_like_bullet(ln)]
        non_bullets = [ln for ln in lines if not _looks_like_bullet(ln)]
        return {
            "summary_portion": " ".join(non_bullets),
            "bullet_portions": bullets,
            "is_mixed": len(bullets) > 0,
        }

    def _ai_handler(provider):
        raw = provider.generate(prompt, response_format="json")
        if isinstance(raw, str):
            raw = json.loads(raw)
        return raw

    return route_inference(
        task="split_summary",
        context={"text_length": len(summary_text)},
        python_fallback=_python_fallback,
        ai_handler=_ai_handler,
    )


def ai_suggest_role_types(summaries: list) -> dict:
    """AI suggests meaningful role_types based on summary content.

    Args:
        summaries: List of summary records with at least
                   {"id": N, "content": "...", "role_type": "..."}

    Returns:
        {"suggestions": [{"id": N, "current_role_type": "...",
                          "suggested_role_type": "..."}],
         "analysis_mode": "ai"|"rule_based"}
    """
    from ai_providers.router import route_inference

    summaries_json = _build_entries_json("summaries", summaries)
    prompt = ROLE_TYPE_PROMPT.format(summaries_json=summaries_json)

    def _python_fallback(_ctx):
        suggestions = []
        for i, s in enumerate(summaries):
            sid = s.get("id", i + 1)
            role_type = s.get("role_type") or ""
            if re.match(r"^(auto_|type_)", role_type, re.IGNORECASE):
                suggestions.append({
                    "id": sid,
                    "current_role_type": role_type,
                    "suggested_role_type": "needs_review",
                })
        return {"suggestions": suggestions}

    def _ai_handler(provider):
        raw = provider.generate(prompt, response_format="json")
        if isinstance(raw, str):
            raw = json.loads(raw)
        return raw

    return route_inference(
        task="suggest_role_types",
        context={"count": len(summaries)},
        python_fallback=_python_fallback,
        ai_handler=_ai_handler,
    )


# ---------------------------------------------------------------------------
# Merge Execution
# ---------------------------------------------------------------------------

# Table name map for simple entity types
_ENTITY_TABLE = {
    "career_history": "career_history",
    "bullets": "bullets",
    "skills": "skills",
    "education": "education",
    "certifications": "certifications",
    "summary_variants": "summary_variants",
    "languages": "languages",
    "references": "references",
}


def execute_merge(entity_type: str, winner_id: int, loser_ids: list, conn=None) -> dict:
    """Merge loser records into winner by repointing FKs then deleting losers.

    For career_history: repoints bullets.career_history_id and
    "references".career_history_id before deleting losers.

    Args:
        conn: Optional existing psycopg2 connection. When provided the caller
              owns commit/rollback. When None, a pooled connection is used.

    Returns {"merged": N, "errors": []}
    """
    import db

    table = _ENTITY_TABLE.get(entity_type)
    if table is None:
        raise ValueError(f"Unknown entity_type: {entity_type!r}")
    if not loser_ids:
        return {"merged": 0, "errors": []}

    errors = []
    merged = 0

    def _run(cur):
        nonlocal merged
        if entity_type == "career_history":
            cur.execute(
                "UPDATE bullets SET career_history_id = %s "
                "WHERE career_history_id = ANY(%s)",
                [winner_id, loser_ids],
            )
            cur.execute(
                'UPDATE "references" SET career_history_id = %s '
                "WHERE career_history_id = ANY(%s)",
                [winner_id, loser_ids],
            )
        cur.execute(
            f"DELETE FROM {table} WHERE id = ANY(%s)",
            [loser_ids],
        )
        merged = cur.rowcount

    try:
        if conn is not None:
            with conn.cursor() as cur:
                _run(cur)
        else:
            with db.get_conn() as _conn:
                with _conn.cursor() as cur:
                    _run(cur)
    except Exception as exc:
        logger.exception("execute_merge failed for %s", entity_type)
        errors.append(str(exc))

    return {"merged": merged, "errors": errors}


def execute_delete(entity_type: str, ids: list, conn=None) -> dict:
    """Delete entities by ID.

    For career_history: cascades by deleting bullets first, then nulling
    "references".career_history_id before deleting the career_history rows.

    Args:
        conn: Optional existing psycopg2 connection (caller owns commit/rollback).

    Returns {"deleted": N, "errors": []}
    """
    import db

    table = _ENTITY_TABLE.get(entity_type)
    if table is None:
        raise ValueError(f"Unknown entity_type: {entity_type!r}")
    if not ids:
        return {"deleted": 0, "errors": []}

    errors = []
    deleted = 0

    def _run(cur):
        nonlocal deleted
        if entity_type == "career_history":
            cur.execute(
                "DELETE FROM bullets WHERE career_history_id = ANY(%s)",
                [ids],
            )
            cur.execute(
                'UPDATE "references" SET career_history_id = NULL '
                "WHERE career_history_id = ANY(%s)",
                [ids],
            )
        cur.execute(
            f"DELETE FROM {table} WHERE id = ANY(%s)",
            [ids],
        )
        deleted = cur.rowcount

    try:
        if conn is not None:
            with conn.cursor() as cur:
                _run(cur)
        else:
            with db.get_conn() as _conn:
                with _conn.cursor() as cur:
                    _run(cur)
    except Exception as exc:
        logger.exception("execute_delete failed for %s", entity_type)
        errors.append(str(exc))

    return {"deleted": deleted, "errors": errors}


def execute_reclassify(source_type: str, target_type: str, items: list, conn=None) -> dict:
    """Move items from source table to target table.

    Primary use case: summary_variants → bullets.
    Each item: {"id": N, "career_history_id": optional}

    Args:
        conn: Optional existing psycopg2 connection (caller owns commit/rollback).

    Returns {"reclassified": N, "errors": []}
    """
    import db

    src_table = _ENTITY_TABLE.get(source_type)
    tgt_table = _ENTITY_TABLE.get(target_type)
    if src_table is None:
        raise ValueError(f"Unknown source_type: {source_type!r}")
    if tgt_table is None:
        raise ValueError(f"Unknown target_type: {target_type!r}")
    if not items:
        return {"reclassified": 0, "errors": []}

    errors = []
    reclassified = 0

    def _run(cur):
        nonlocal reclassified
        for item in items:
            src_id = item["id"]
            career_history_id = item.get("career_history_id")

            cur.execute(f"SELECT * FROM {src_table} WHERE id = %s", [src_id])
            row = cur.fetchone()
            if row is None:
                errors.append(f"{source_type} id={src_id} not found")
                continue

            col_names = [desc[0] for desc in cur.description]
            row_dict = dict(zip(col_names, row))

            text_val = (
                row_dict.get("text")
                or row_dict.get("content")
                or row_dict.get("summary")
                or ""
            )

            if target_type == "bullets":
                cur.execute(
                    "INSERT INTO bullets (career_history_id, text, type) "
                    "VALUES (%s, %s, %s)",
                    [career_history_id, text_val, "reclassified"],
                )
            elif source_type == "bullets" and target_type == "summary_variants":
                role_type = row_dict.get("role_type") or f"reclassified_{src_id}"
                cur.execute(
                    "INSERT INTO summary_variants (role_type, text) "
                    "VALUES (%s, %s) ON CONFLICT (role_type) DO NOTHING",
                    [role_type, text_val],
                )
            else:
                errors.append(
                    f"Unsupported reclassify path: {source_type} -> {target_type}"
                )
                continue

            cur.execute(f"DELETE FROM {src_table} WHERE id = %s", [src_id])
            reclassified += 1

    try:
        if conn is not None:
            with conn.cursor() as cur:
                _run(cur)
        else:
            with db.get_conn() as _conn:
                with _conn.cursor() as cur:
                    _run(cur)
    except Exception as exc:
        logger.exception("execute_reclassify failed %s->%s", source_type, target_type)
        errors.append(str(exc))

    return {"reclassified": reclassified, "errors": errors}


def execute_employer_rename(career_history_ids: list, canonical_name: str, conn=None) -> dict:
    """Update the employer column for a set of career_history records.

    Args:
        conn: Optional existing psycopg2 connection (caller owns commit/rollback).

    Returns {"updated": N}
    """
    import db

    if not career_history_ids:
        return {"updated": 0}

    if conn is not None:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE career_history SET employer = %s WHERE id = ANY(%s)",
                [canonical_name, career_history_ids],
            )
            return {"updated": cur.rowcount}

    rowcount = db.execute(
        "UPDATE career_history SET employer = %s WHERE id = ANY(%s)",
        [canonical_name, career_history_ids],
    )
    return {"updated": rowcount}


def execute_summary_role_type_rename(reassignments: dict, conn=None) -> dict:
    """Rename role_types in summary_variants.

    reassignments: {old_role_type: new_role_type}

    Args:
        conn: Optional existing psycopg2 connection (caller owns commit/rollback).

    Returns {"updated": N}
    """
    import db

    if not reassignments:
        return {"updated": 0}

    updated = 0

    def _run(cur):
        nonlocal updated
        for old_role_type, new_role_type in reassignments.items():
            cur.execute(
                "UPDATE summary_variants SET role_type = %s WHERE role_type = %s",
                [new_role_type, old_role_type],
            )
            updated += cur.rowcount

    if conn is not None:
        with conn.cursor() as cur:
            _run(cur)
    else:
        with db.get_conn() as _conn:
            with _conn.cursor() as cur:
                _run(cur)

    return {"updated": updated}


def execute_summary_split(
    split_id: int,
    keep_summary_text: str,
    extract_bullets: list,
    career_history_id: int = None,
    conn=None,
) -> dict:
    """Update a summary_variants record's text and create new bullet records.

    Args:
        split_id:           ID of the summary_variants record to update.
        keep_summary_text:  The cleaned summary text to write back.
        extract_bullets:    List of strings to insert as new bullet records.
        career_history_id:  Optional FK for the new bullets.
        conn:               Optional existing psycopg2 connection (caller owns
                            commit/rollback).

    Returns {"summary_updated": True, "bullets_created": N}
    """
    import db

    bullets_created = 0

    def _run(cur):
        nonlocal bullets_created
        cur.execute(
            "UPDATE summary_variants SET text = %s WHERE id = %s",
            [keep_summary_text, split_id],
        )
        for bullet_text in extract_bullets:
            if not bullet_text or not bullet_text.strip():
                continue
            cur.execute(
                "INSERT INTO bullets (career_history_id, text, type) "
                "VALUES (%s, %s, %s)",
                [career_history_id, bullet_text.strip(), "extracted_from_summary"],
            )
            bullets_created += 1

    if conn is not None:
        with conn.cursor() as cur:
            _run(cur)
    else:
        with db.get_conn() as _conn:
            with _conn.cursor() as cur:
                _run(cur)

    return {"summary_updated": True, "bullets_created": bullets_created}


def execute_split_skill(skill_id: int, new_skill_names: list, conn=None) -> dict:
    """Delete a compound skill and insert individual skills from it.

    Args:
        skill_id:        ID of the skill to delete.
        new_skill_names: List of individual skill name strings to insert.
        conn:            Optional existing psycopg2 connection.

    Returns {"deleted": 1, "created": N}
    """
    import db

    created = 0

    def _run(cur):
        nonlocal created
        # Get the original skill's category (inherit to children)
        cur.execute("SELECT category FROM skills WHERE id = %s", [skill_id])
        row = cur.fetchone()
        category = row[0] if row else None

        # Delete the compound skill
        cur.execute("DELETE FROM skills WHERE id = %s", [skill_id])

        # Insert individual skills (skip if already exists)
        for name in new_skill_names:
            name = name.strip()
            if not name:
                continue
            cur.execute("SELECT id FROM skills WHERE lower(name) = lower(%s)", [name])
            if cur.fetchone():
                continue  # already exists, skip
            cur.execute(
                "INSERT INTO skills (name, category) VALUES (%s, %s)",
                [name, category],
            )
            created += 1

    if conn is not None:
        with conn.cursor() as cur:
            _run(cur)
    else:
        with db.get_conn() as _conn:
            with _conn.cursor() as cur:
                _run(cur)

    return {"deleted": 1, "created": created}


def execute_split_certification(cert_id: int, new_cert_names: list, conn=None) -> dict:
    """Delete a compound certification and insert individual certs.

    Args:
        cert_id:         ID of the certification to delete.
        new_cert_names:  List of individual certification name strings to insert.
        conn:            Optional existing psycopg2 connection.

    Returns {"deleted": 1, "created": N}
    """
    import db

    created = 0

    def _run(cur):
        nonlocal created
        # Get original issuer
        cur.execute("SELECT issuer FROM certifications WHERE id = %s", [cert_id])
        row = cur.fetchone()
        issuer = row[0] if row else None

        cur.execute("DELETE FROM certifications WHERE id = %s", [cert_id])

        for name in new_cert_names:
            name = name.strip()
            if not name:
                continue
            cur.execute("SELECT id FROM certifications WHERE lower(name) = lower(%s)", [name])
            if cur.fetchone():
                continue
            cur.execute(
                "INSERT INTO certifications (name, issuer) VALUES (%s, %s)",
                [name, issuer],
            )
            created += 1

    if conn is not None:
        with conn.cursor() as cur:
            _run(cur)
    else:
        with db.get_conn() as _conn:
            with _conn.cursor() as cur:
                _run(cur)

    return {"deleted": 1, "created": created}
