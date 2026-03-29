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

import re
from difflib import SequenceMatcher

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

def group_skills(skills: list) -> dict:
    """Group skills by name.

    auto_merge  — same canonical name (case-insensitive / synonym resolution)
    needs_review — different canonical names but same synonym canonical (abbreviation)
    """
    FIELDS = ["name", "category", "proficiency", "last_used_year", "years_experience"]

    # Bucket by canonical name
    canonical_buckets: dict[str, list] = {}
    for s in skills:
        key = _normalize_name(s.get("name", ""))
        canonical_buckets.setdefault(key, []).append(s)

    auto_merge = []
    needs_review = []

    for canon, members in canonical_buckets.items():
        winner = _pick_winner(members, FIELDS)
        if len(members) > 1:
            # Check if all members share the same lowercased raw name (exact match)
            raw_names = {m.get("name", "").strip().lower() for m in members}
            if len(raw_names) == 1:
                # All identical raw names (case-insensitive) → auto_merge
                auto_merge.append(_make_group(winner, members))
            else:
                # Different raw names resolved to same canonical via synonym → needs_review
                needs_review.append(_make_group(winner, members))
        else:
            # Single record — no duplicate, skip entirely (Fix 4: don't flag single abbreviations)
            pass

    return {"auto_merge": auto_merge, "needs_review": needs_review, "junk": []}


# ---------------------------------------------------------------------------
# 2. Education
# ---------------------------------------------------------------------------

def group_education(entries: list) -> dict:
    """Group education by normalized institution + degree."""
    FIELDS = ["institution", "degree", "field_of_study", "start_date", "end_date",
              "gpa", "honors", "location"]

    buckets: dict[tuple, list] = {}
    for e in entries:
        inst = _institution_normalize(e.get("institution", ""))
        deg = (e.get("degree") or "").strip().lower()
        key = (inst, deg)
        buckets.setdefault(key, []).append(e)

    auto_merge = []
    for key, members in buckets.items():
        winner = _pick_winner(members, FIELDS)
        if len(members) > 1:
            auto_merge.append(_make_group(winner, members))

    return {"auto_merge": auto_merge, "needs_review": [], "junk": []}


# ---------------------------------------------------------------------------
# 3. Certifications
# ---------------------------------------------------------------------------

def group_certifications(certs: list) -> dict:
    """Group certifications by name (exact = auto_merge, synonym = needs_review)."""
    FIELDS = ["name", "issuer", "issued_date", "expiry_date", "is_active", "cert_id"]

    def _cert_canon(name: str) -> str:
        key = (name or "").strip().lower()
        return CERT_SYNONYMS.get(key, key)

    # Prefer active records
    def _cert_winner(members: list) -> dict:
        active = [m for m in members if m.get("is_active")]
        pool = active if active else members
        return _pick_winner(pool, FIELDS)

    # Exact (case-insensitive) name buckets
    exact_buckets: dict[str, list] = {}
    for c in certs:
        key = (c.get("name") or "").strip().lower()
        exact_buckets.setdefault(key, []).append(c)

    auto_merge = []
    needs_review = []
    processed_keys = set()

    for key, members in exact_buckets.items():
        if len(members) > 1:
            winner = _cert_winner(members)
            auto_merge.append(_make_group(winner, members))
        processed_keys.add(key)

    # Synonym grouping — group remaining single-record keys by canonical synonym
    canon_buckets: dict[str, list] = {}
    for key, members in exact_buckets.items():
        if len(members) == 1:
            canon = _cert_canon(key)
            canon_buckets.setdefault(canon, []).append(members[0])

    for canon, members in canon_buckets.items():
        if len(members) > 1:
            winner = _cert_winner(members)
            needs_review.append(_make_group(winner, members))

    return {"auto_merge": auto_merge, "needs_review": needs_review, "junk": []}


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
        # canonical_name = longest raw employer name among members
        raw_names = [m.get("company") or m.get("employer") or "" for m in members]
        canonical_name = max(raw_names, key=len) if raw_names else key
        winner = _pick_winner(members, EMPLOYER_FIELDS)
        if len(members) > 1:
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

    def _process_bucket(bucket_items):
        used = [False] * len(bucket_items)
        for i in range(len(bucket_items)):
            if used[i]:
                continue
            text_i = bucket_items[i].get("content") or bucket_items[i].get("text") or bucket_items[i].get("bullet") or ""
            group_members = [bucket_items[i]]
            used[i] = True
            best_sim_for_group = 0.0
            for j in range(i + 1, len(bucket_items)):
                if used[j]:
                    continue
                text_j = bucket_items[j].get("content") or bucket_items[j].get("text") or bucket_items[j].get("bullet") or ""
                sim = _similarity(text_i, text_j)
                if sim >= 0.75:
                    group_members.append(bucket_items[j])
                    used[j] = True
                    best_sim_for_group = max(best_sim_for_group, sim)
            if len(group_members) > 1:
                # Winner = longest bullet
                winner = max(group_members, key=lambda r: len(r.get("content") or r.get("text") or r.get("bullet") or ""))
                group = _make_group(winner, group_members)
                if best_sim_for_group >= 0.95:
                    auto_merge.append(group)
                else:
                    needs_review.append(group)

    for bucket in job_buckets.values():
        _process_bucket(bucket)

    # Second pass: cross-job dedup.
    # Collect one representative (winner) per intra-job group plus all singletons,
    # then compare across different career_history_id buckets.  Cross-job near-exact
    # duplicates (>= 0.95) go to needs_review (never auto_merge — user must decide
    # which job record to keep the bullet under).
    cross_job_singles: list = []  # (career_history_id, bullet_record)
    for jid, bucket in job_buckets.items():
        for b in bucket:
            cross_job_singles.append((jid, b))

    cj_used = [False] * len(cross_job_singles)
    for i in range(len(cross_job_singles)):
        if cj_used[i]:
            continue
        jid_i, b_i = cross_job_singles[i]
        text_i = b_i.get("content") or b_i.get("text") or b_i.get("bullet") or ""
        group_members = [b_i]
        for j in range(i + 1, len(cross_job_singles)):
            if cj_used[j]:
                continue
            jid_j, b_j = cross_job_singles[j]
            if jid_i == jid_j:
                continue  # same job — already handled in first pass
            text_j = b_j.get("content") or b_j.get("text") or b_j.get("bullet") or ""
            if _similarity(text_i, text_j) >= 0.95:
                group_members.append(b_j)
                cj_used[j] = True
        if len(group_members) > 1:
            cj_used[i] = True
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
