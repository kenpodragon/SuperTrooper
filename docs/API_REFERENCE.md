# API Reference

SuperTroopers REST API. Base URL: `http://localhost:8055`

All endpoints return JSON. POST/PATCH/PUT accept JSON request bodies with `Content-Type: application/json`.

---

## Health & Settings

### GET /api/health

Check API and database connectivity.

**Response:**
```json
{ "status": "healthy", "db": "connected" }
```

---

### GET /api/settings

Return the single settings row.

**Response:**
```json
{
  "id": 1,
  "ai_provider": "openai",
  "ai_enabled": true,
  "ai_model": "gpt-4o",
  "default_template_id": 1,
  "duplicate_threshold": 0.92,
  "preferences": {},
  "created_at": "2025-01-01T00:00:00",
  "updated_at": "2025-01-01T00:00:00"
}
```

---

### PATCH /api/settings

Update allowed settings fields.

**Request Body:**
```json
{
  "ai_provider": "openai",
  "ai_enabled": true,
  "ai_model": "gpt-4o",
  "default_template_id": 1,
  "duplicate_threshold": 0.92,
  "preferences": {}
}
```

All fields optional. Only the fields listed above are accepted.

**Response:** Updated settings row (same shape as GET).

---

### POST /api/settings/test-ai

Test the configured (or a specified) AI provider connection.

**Request Body:**
```json
{ "provider": "openai" }
```

`provider` is optional. If omitted, tests the currently configured provider.

**Response:**
```json
{
  "status": "ok",
  "provider": "openai",
  "health": { "available": true, "model": "gpt-4o" },
  "providers": ["openai", "anthropic"]
}
```

---

## Career Data

### GET /api/career-history

List career history entries.

**Parameters:**
| Name | In | Type | Required | Description |
|------|-----|------|----------|-------------|
| industry | query | string | No | Filter by industry (case-insensitive partial match) |
| is_current | query | boolean | No | Filter to current roles (`true`/`false`) |
| limit | query | integer | No | Max rows to return (default: 50) |
| offset | query | integer | No | Pagination offset (default: 0) |

**Response:**
```json
[
  {
    "id": 1,
    "employer": "Acme Corp",
    "title": "VP Engineering",
    "start_date": "2020-01-01",
    "end_date": null,
    "location": "Remote",
    "industry": "Technology",
    "team_size": 45,
    "budget_usd": 5000000,
    "revenue_impact": "Led $50M ARR product line",
    "is_current": true,
    "linkedin_dates": "Jan 2020 - Present",
    "notes": null,
    "created_at": "2025-01-01T00:00:00",
    "updated_at": "2025-01-01T00:00:00"
  }
]
```

---

### GET /api/career-history/:career_id

Single career history entry with all its bullets.

**Parameters:**
| Name | In | Type | Required | Description |
|------|-----|------|----------|-------------|
| career_id | path | integer | Yes | Career history ID |

**Response:**
```json
{
  "id": 1,
  "employer": "Acme Corp",
  "title": "VP Engineering",
  "bullets": [
    {
      "id": 10,
      "text": "Led migration to microservices, reducing deploy time 60%",
      "type": "core",
      "star_situation": null,
      "star_task": null,
      "star_action": null,
      "star_result": null,
      "metrics_json": {},
      "tags": ["engineering", "cloud"],
      "role_suitability": ["CTO", "VP Engineering"],
      "industry_suitability": ["SaaS"],
      "detail_recall": "high",
      "source_file": null,
      "created_at": "2025-01-01T00:00:00"
    }
  ]
}
```

---

### POST /api/career-history

Add a new career history entry.

**Request Body:**
```json
{
  "employer": "Acme Corp",
  "title": "VP Engineering",
  "start_date": "2020-01-01",
  "end_date": null,
  "location": "Remote",
  "industry": "Technology",
  "team_size": 45,
  "budget_usd": 5000000,
  "revenue_impact": "Led $50M ARR product line",
  "is_current": true,
  "linkedin_dates": "Jan 2020 - Present",
  "intro_text": null,
  "career_links": null,
  "notes": null
}
```

`employer` and `title` are required.

**Response:** Created row (HTTP 201).

---

### PATCH /api/career-history/:career_id

Update career history fields.

**Parameters:**
| Name | In | Type | Required | Description |
|------|-----|------|----------|-------------|
| career_id | path | integer | Yes | Career history ID |

**Request Body:** Any subset of fields from POST (all optional).

**Response:** Updated row.

---

### DELETE /api/career-history/:career_id

Delete a career history entry. Cascades to bullets.

**Parameters:**
| Name | In | Type | Required | Description |
|------|-----|------|----------|-------------|
| career_id | path | integer | Yes | Career history ID |

**Response:**
```json
{ "deleted": 1 }
```

---

### GET /api/bullets

Search/filter bullets across all employers.

**Parameters:**
| Name | In | Type | Required | Description |
|------|-----|------|----------|-------------|
| q | query | string | No | Text search (case-insensitive partial match) |
| tags | query | string[] | No | Filter by tags (array intersection) |
| role_type | query | string | No | Filter by role suitability |
| industry | query | string | No | Filter by industry suitability |
| type | query | string | No | Filter by bullet type (e.g. `core`, `achievement`) |
| limit | query | integer | No | Max rows (default: 50) |
| offset | query | integer | No | Pagination offset (default: 0) |

**Response:**
```json
[
  {
    "id": 10,
    "career_history_id": 1,
    "text": "Led migration...",
    "type": "core",
    "tags": ["engineering"],
    "role_suitability": ["VP Engineering"],
    "industry_suitability": ["SaaS"],
    "metrics_json": {},
    "detail_recall": "high",
    "source_file": null,
    "created_at": "2025-01-01T00:00:00",
    "employer": "Acme Corp",
    "title": "VP Engineering"
  }
]
```

---

### GET /api/bullets/:bullet_id

Single bullet with employer context.

**Parameters:**
| Name | In | Type | Required | Description |
|------|-----|------|----------|-------------|
| bullet_id | path | integer | Yes | Bullet ID |

**Response:** Single bullet object (same shape as list item above, with full STAR fields).

---

### POST /api/bullets

Add a new bullet.

**Request Body:**
```json
{
  "career_history_id": 1,
  "text": "Led migration to microservices, reducing deploy time 60%",
  "type": "core",
  "star_situation": null,
  "star_task": null,
  "star_action": null,
  "star_result": null,
  "metrics_json": {},
  "tags": ["engineering"],
  "role_suitability": ["VP Engineering"],
  "industry_suitability": ["SaaS"],
  "detail_recall": "high",
  "source_file": null
}
```

`text` is required. `type` defaults to `"core"`. `detail_recall` defaults to `"high"`.

**Response:** Created row (HTTP 201).

---

### PATCH /api/bullets/:bullet_id

Update bullet fields.

**Parameters:**
| Name | In | Type | Required | Description |
|------|-----|------|----------|-------------|
| bullet_id | path | integer | Yes | Bullet ID |

**Request Body:** Any subset of POST fields (all optional).

**Response:** Updated row.

---

### DELETE /api/bullets/:bullet_id

Delete a bullet.

**Parameters:**
| Name | In | Type | Required | Description |
|------|-----|------|----------|-------------|
| bullet_id | path | integer | Yes | Bullet ID |

**Response:**
```json
{ "deleted": 10 }
```

---

### GET /api/skills

List skills with optional filters.

**Parameters:**
| Name | In | Type | Required | Description |
|------|-----|------|----------|-------------|
| category | query | string | No | Filter by category |
| proficiency | query | string | No | Filter by proficiency level |
| limit | query | integer | No | Max rows (default: 100) |
| offset | query | integer | No | Pagination offset (default: 0) |

**Response:**
```json
[
  {
    "id": 1,
    "name": "Python",
    "category": "Programming",
    "proficiency": "expert",
    "last_used_year": 2025,
    "career_history_ids": [1, 2],
    "created_at": "2025-01-01T00:00:00"
  }
]
```

---

### POST /api/skills

Add a new skill.

**Request Body:**
```json
{
  "name": "Python",
  "category": "Programming",
  "proficiency": "expert",
  "last_used_year": 2025,
  "career_history_ids": [1, 2]
}
```

`name` is required.

**Response:** Created row (HTTP 201).

---

### PATCH /api/skills/:skill_id

Update a skill.

**Parameters:**
| Name | In | Type | Required | Description |
|------|-----|------|----------|-------------|
| skill_id | path | integer | Yes | Skill ID |

**Request Body:** Any subset of POST fields (all optional).

**Response:** Updated row.

---

### DELETE /api/skills/:skill_id

Delete a skill.

**Parameters:**
| Name | In | Type | Required | Description |
|------|-----|------|----------|-------------|
| skill_id | path | integer | Yes | Skill ID |

**Response:**
```json
{ "deleted": 1 }
```

---

### GET /api/summary-variants

List all summary variants.

**Response:**
```json
[
  {
    "id": 1,
    "role_type": "CTO",
    "text": "Technology executive with 15+ years...",
    "updated_at": "2025-01-01T00:00:00"
  }
]
```

---

### GET /api/summary-variants/:role_type

Single summary variant by role_type string.

**Parameters:**
| Name | In | Type | Required | Description |
|------|-----|------|----------|-------------|
| role_type | path | string | Yes | Role type (e.g. `CTO`) |

**Response:** Single variant object.

---

### POST /api/summary-variants

Add a new summary variant.

**Request Body:**
```json
{
  "role_type": "CTO",
  "text": "Technology executive with 15+ years..."
}
```

Both fields required.

**Response:** Created row (HTTP 201).

---

### PATCH /api/summary-variants/:variant_id

Update a summary variant.

**Parameters:**
| Name | In | Type | Required | Description |
|------|-----|------|----------|-------------|
| variant_id | path | integer | Yes | Variant ID |

**Request Body:** `role_type` and/or `text` (at least one required).

**Response:** Updated row.

---

### DELETE /api/summary-variants/:variant_id

Delete a summary variant.

**Parameters:**
| Name | In | Type | Required | Description |
|------|-----|------|----------|-------------|
| variant_id | path | integer | Yes | Variant ID |

**Response:**
```json
{ "deleted": 1 }
```

---

### GET /api/kb/export

Export all knowledge base data as a single JSON snapshot.

**Response:**
```json
{
  "career_history": [...],
  "bullets": [...],
  "skills": [...],
  "summary_variants": [...],
  "resume_header": {...},
  "education": [...],
  "certifications": [...],
  "counts": {
    "career_history": 5,
    "bullets": 120,
    "skills": 45,
    "summary_variants": 4,
    "education": 3,
    "certifications": 6
  }
}
```

---

## Resume Management

### GET /api/resume/recipes

List resume recipes.

**Parameters:**
| Name | In | Type | Required | Description |
|------|-----|------|----------|-------------|
| template_id | query | integer | No | Filter by template |
| is_active | query | boolean | No | Filter active recipes (default: `true`) |

**Response:**
```json
{
  "recipes": [
    {
      "id": 1,
      "name": "Base v32",
      "description": null,
      "headline": "Technology Executive",
      "template_id": 1,
      "application_id": null,
      "is_active": true,
      "created_at": "2025-01-01T00:00:00",
      "updated_at": "2025-01-01T00:00:00"
    }
  ],
  "count": 1
}
```

---

### GET /api/resume/recipes/:recipe_id

Get a single recipe with full slot JSON.

**Parameters:**
| Name | In | Type | Required | Description |
|------|-----|------|----------|-------------|
| recipe_id | path | integer | Yes | Recipe ID |
| resolve | query | boolean | No | If `true`, resolves DB references to text and adds `resolved_preview` |

**Response:** Full recipe row including `recipe` JSON. If `resolve=true`, also includes `resolved_preview` object with placeholder -> text mappings.

---

### GET /api/resume/recipes/:recipe_id/validate

Validate a recipe's DB references.

**Parameters:**
| Name | In | Type | Required | Description |
|------|-----|------|----------|-------------|
| recipe_id | path | integer | Yes | Recipe ID |

**Response:**
```json
{
  "valid": true,
  "errors": [],
  "stats": {
    "total_slots": 42,
    "db_refs": 38,
    "literals": 4,
    "valid_refs": 38,
    "missing_refs": 0
  }
}
```

---

### POST /api/resume/recipes

Create a new recipe.

**Request Body:**
```json
{
  "name": "Tailored for Stripe",
  "template_id": 1,
  "recipe": {
    "HEADLINE": { "literal": "Payments Technology Executive" },
    "JOB_1_BULLET_1": { "table": "bullets", "id": 42, "column": "text" }
  },
  "headline": "Payments Technology Executive",
  "description": null,
  "application_id": null
}
```

`name`, `template_id`, and `recipe` are required.

**Response:** Created row (HTTP 201).

---

### PUT /api/resume/recipes/:recipe_id

Update a recipe (partial update).

**Parameters:**
| Name | In | Type | Required | Description |
|------|-----|------|----------|-------------|
| recipe_id | path | integer | Yes | Recipe ID |

**Request Body:** Any subset of `name`, `description`, `headline`, `is_active`, `recipe`, `application_id`.

**Response:** Updated row.

---

### DELETE /api/resume/recipes/:recipe_id

Soft-delete a recipe (sets `is_active = false`).

**Parameters:**
| Name | In | Type | Required | Description |
|------|-----|------|----------|-------------|
| recipe_id | path | integer | Yes | Recipe ID |

**Response:**
```json
{ "status": "deleted", "id": 1 }
```

---

### POST /api/resume/recipes/:recipe_id/clone

Clone a recipe as a new entry for tailoring.

**Parameters:**
| Name | In | Type | Required | Description |
|------|-----|------|----------|-------------|
| recipe_id | path | integer | Yes | Source recipe ID |

**Request Body:**
```json
{
  "name": "Tailored for Stripe",
  "application_id": 5
}
```

Both fields optional. `name` defaults to `"{original_name} (copy)"`.

**Response:** New recipe row (HTTP 201).

---

### POST /api/resume/recipes/:recipe_id/generate

Generate a `.docx` resume file from a recipe.

**Parameters:**
| Name | In | Type | Required | Description |
|------|-----|------|----------|-------------|
| recipe_id | path | integer | Yes | Recipe ID |

**Response:** `.docx` file download (`application/vnd.openxmlformats-officedocument.wordprocessingml.document`).

---

### GET /api/resume/templates

List available resume templates (without blob data).

**Response:**
```json
{
  "templates": [
    {
      "id": 1,
      "name": "V32 Placeholder",
      "filename": "v32_template.docx",
      "description": null,
      "is_active": true,
      "size_bytes": 48320,
      "created_at": "2025-01-01T00:00:00"
    }
  ],
  "count": 1
}
```

---

### GET /api/resume/templates/:template_id/download

Download a resume template `.docx` file.

**Parameters:**
| Name | In | Type | Required | Description |
|------|-----|------|----------|-------------|
| template_id | path | integer | Yes | Template ID |

**Response:** `.docx` file download.

---

### GET /api/resume/header

Get resume header (name, credentials, contact info).

**Response:**
```json
{
  "id": 1,
  "full_name": "Stephen Salaka",
  "credentials": "PhD, MBA",
  "location": "Melbourne, FL",
  "location_note": "Open to Remote",
  "email": "stephen@example.com",
  "phone": "+1-321-555-0100",
  "linkedin_url": "https://linkedin.com/in/stephensalaka",
  "website_url": null,
  "calendly_url": null
}
```

---

### PATCH /api/resume/header

Update resume header fields (upserts if no row exists).

**Request Body:** Any subset of `full_name`, `credentials`, `location`, `location_note`, `email`, `phone`, `linkedin_url`, `website_url`, `calendly_url`.

**Response:** Updated header row.

---

### GET /api/education

Get all education entries ordered by `sort_order`.

**Response:**
```json
{
  "education": [
    {
      "id": 1,
      "degree": "PhD",
      "field": "Industrial-Organizational Psychology",
      "institution": "Florida Institute of Technology",
      "location": "Melbourne, FL",
      "type": "degree",
      "sort_order": 0
    }
  ],
  "count": 3
}
```

---

### POST /api/education

Add a new education entry.

**Request Body:**
```json
{
  "degree": "PhD",
  "institution": "Florida Institute of Technology",
  "field": "Industrial-Organizational Psychology",
  "location": "Melbourne, FL",
  "type": "degree",
  "sort_order": 0
}
```

`degree` and `institution` are required. `type` defaults to `"degree"`, `sort_order` defaults to `0`.

**Response:** Created row (HTTP 201).

---

### PATCH /api/education/:edu_id

Update an education entry.

**Parameters:**
| Name | In | Type | Required | Description |
|------|-----|------|----------|-------------|
| edu_id | path | integer | Yes | Education ID |

**Request Body:** Any subset of `degree`, `field`, `institution`, `location`, `type`, `sort_order`.

**Response:** Updated row.

---

### DELETE /api/education/:edu_id

Delete an education entry.

**Parameters:**
| Name | In | Type | Required | Description |
|------|-----|------|----------|-------------|
| edu_id | path | integer | Yes | Education ID |

**Response:**
```json
{ "deleted": 1 }
```

---

### GET /api/certifications

Get active certification entries ordered by `sort_order`.

**Response:**
```json
{
  "certifications": [
    {
      "id": 1,
      "name": "AWS Solutions Architect",
      "issuer": "Amazon",
      "is_active": true,
      "sort_order": 0
    }
  ],
  "count": 6
}
```

---

### POST /api/certifications

Add a new certification.

**Request Body:**
```json
{
  "name": "AWS Solutions Architect",
  "issuer": "Amazon",
  "is_active": true,
  "sort_order": 0
}
```

`name` is required. `is_active` defaults to `true`, `sort_order` to `0`.

**Response:** Created row (HTTP 201).

---

### PATCH /api/certifications/:cert_id

Update a certification.

**Parameters:**
| Name | In | Type | Required | Description |
|------|-----|------|----------|-------------|
| cert_id | path | integer | Yes | Certification ID |

**Request Body:** Any subset of `name`, `issuer`, `is_active`, `sort_order`.

**Response:** Updated row.

---

### DELETE /api/certifications/:cert_id

Delete a certification.

**Parameters:**
| Name | In | Type | Required | Description |
|------|-----|------|----------|-------------|
| cert_id | path | integer | Yes | Certification ID |

**Response:**
```json
{ "deleted": 1 }
```

---

### GET /api/resume/versions

List resume versions.

**Response:**
```json
{
  "versions": [
    {
      "id": 1,
      "version": "v32",
      "variant": "base",
      "is_current": true,
      "has_spec": true,
      "docx_path": null,
      "pdf_path": null,
      "summary": null,
      "target_role_type": "CTO",
      "created_at": "2025-01-01T00:00:00"
    }
  ],
  "count": 5
}
```

---

### GET /api/resume/versions/:version_id/spec

Get the full spec for a resume version.

**Parameters:**
| Name | In | Type | Required | Description |
|------|-----|------|----------|-------------|
| version_id | path | integer | Yes | Version ID |

**Response:** Full resume_versions row including `spec` JSON.

---

### GET /api/resume/data

Get all data needed to reconstruct a resume (header, education, certs, experience with bullets, spec).

**Parameters:**
| Name | In | Type | Required | Description |
|------|-----|------|----------|-------------|
| version | query | string | No | Resume version (default: `v32`) |
| variant | query | string | No | Resume variant (default: `base`) |
| format | query | string | No | `full` (default) or `spec_only` |

**Response (format=full):**
```json
{
  "version": "v32",
  "variant": "base",
  "spec": {},
  "header": {},
  "education": [],
  "certifications": [],
  "experience": [],
  "template_available": { "id": 1, "name": "V32 Placeholder" }
}
```

---

### POST /api/resume/generate

Generate a `.docx` resume from a version spec + template.

**Request Body:**
```json
{
  "version": "v32",
  "variant": "base",
  "template_name": "V32 Placeholder",
  "overrides": {
    "HEADLINE": "Custom Headline Text"
  }
}
```

All fields optional. `version` defaults to `v32`, `variant` to `base`, `template_name` to `V32 Placeholder`.

**Response:** `.docx` file download.

---

## Job Search

### GET /api/saved-jobs

List saved jobs with optional filters.

**Parameters:**
| Name | In | Type | Required | Description |
|------|-----|------|----------|-------------|
| status | query | string | No | Filter by status (e.g. `saved`, `applied`) |
| source | query | string | No | Filter by source |
| company | query | string | No | Filter by company name (partial match) |
| min_fit_score | query | number | No | Minimum fit score |
| limit | query | integer | No | Max rows (default: 50) |
| offset | query | integer | No | Pagination offset (default: 0) |

**Response:**
```json
[
  {
    "id": 1,
    "url": "https://example.com/job/123",
    "title": "VP of Engineering",
    "company": "Stripe",
    "company_id": 5,
    "location": "Remote",
    "salary_range": "$200K-$250K",
    "source": "LinkedIn",
    "fit_score": 87,
    "status": "saved",
    "notes": null,
    "co_sector": "Fintech",
    "co_priority": "A"
  }
]
```

---

### GET /api/saved-jobs/:job_id

Single saved job with linked gap analyses.

**Parameters:**
| Name | In | Type | Required | Description |
|------|-----|------|----------|-------------|
| job_id | path | integer | Yes | Saved job ID |

**Response:** Job object with `gap_analyses` array.

---

### POST /api/saved-jobs

Save a job for evaluation.

**Request Body:**
```json
{
  "title": "VP of Engineering",
  "url": "https://example.com/job/123",
  "company": "Stripe",
  "company_id": 5,
  "location": "Remote",
  "salary_range": "$200K-$250K",
  "source": "LinkedIn",
  "jd_text": "Full job description...",
  "jd_url": "https://example.com/job/123",
  "fit_score": 87,
  "status": "saved",
  "notes": null
}
```

`title` is required. `status` defaults to `"saved"`.

**Response:** Created row (HTTP 201).

---

### PATCH /api/saved-jobs/:job_id

Update a saved job.

**Parameters:**
| Name | In | Type | Required | Description |
|------|-----|------|----------|-------------|
| job_id | path | integer | Yes | Saved job ID |

**Request Body:** Any subset of POST fields (all optional).

**Response:** Updated row.

---

### DELETE /api/saved-jobs/:job_id

Delete a saved job.

**Parameters:**
| Name | In | Type | Required | Description |
|------|-----|------|----------|-------------|
| job_id | path | integer | Yes | Saved job ID |

**Response:**
```json
{ "deleted": 1 }
```

---

### POST /api/saved-jobs/:job_id/apply

Convert a saved job into an application. Creates an `applications` row from saved job data and marks the saved job as `applied`.

**Parameters:**
| Name | In | Type | Required | Description |
|------|-----|------|----------|-------------|
| job_id | path | integer | Yes | Saved job ID |

**Request Body:**
```json
{
  "status": "Applied",
  "notes": null
}
```

Both fields optional. `status` defaults to `"Applied"`.

**Response:** Created application row (HTTP 201).

---

### GET /api/gap-analyses

List persisted gap analyses.

**Parameters:**
| Name | In | Type | Required | Description |
|------|-----|------|----------|-------------|
| application_id | query | integer | No | Filter by application |
| saved_job_id | query | integer | No | Filter by saved job |
| recommendation | query | string | No | Filter by recommendation value |
| min_score | query | number | No | Minimum overall_score |
| limit | query | integer | No | Max rows (default: 50) |
| offset | query | integer | No | Pagination offset (default: 0) |

**Response:**
```json
[
  {
    "id": 1,
    "application_id": null,
    "saved_job_id": 3,
    "overall_score": 82.5,
    "recommendation": "apply",
    "notes": null,
    "created_at": "2025-01-01T00:00:00",
    "updated_at": "2025-01-01T00:00:00",
    "job_title": "VP of Engineering",
    "job_company": "Stripe"
  }
]
```

---

### GET /api/gap-analyses/:gap_id

Single gap analysis with full details.

**Parameters:**
| Name | In | Type | Required | Description |
|------|-----|------|----------|-------------|
| gap_id | path | integer | Yes | Gap analysis ID |

**Response:** Full gap_analyses row including parsed JSON fields (`jd_parsed`, `strong_matches`, `partial_matches`, `gaps`, `bonus_value`, `fit_scores`).

---

### POST /api/gap-analyses

Save a new gap analysis result.

**Request Body:**
```json
{
  "application_id": null,
  "saved_job_id": 3,
  "jd_text": "Full JD text...",
  "jd_parsed": {},
  "strong_matches": [],
  "partial_matches": [],
  "gaps": [],
  "bonus_value": [],
  "fit_scores": {},
  "overall_score": 82.5,
  "recommendation": "apply",
  "notes": null
}
```

All fields optional. If `application_id` is provided, the application's `gap_analysis_id` is updated.

**Response:** Created row (HTTP 201).

---

### PATCH /api/gap-analyses/:gap_id

Update a gap analysis.

**Parameters:**
| Name | In | Type | Required | Description |
|------|-----|------|----------|-------------|
| gap_id | path | integer | Yes | Gap analysis ID |

**Request Body:** Any subset of POST fields (all optional).

**Response:** Updated row.

---

### DELETE /api/gap-analyses/:gap_id

Delete a gap analysis.

**Parameters:**
| Name | In | Type | Required | Description |
|------|-----|------|----------|-------------|
| gap_id | path | integer | Yes | Gap analysis ID |

**Response:**
```json
{ "deleted": 1 }
```

---

## Applications & Pipeline

### GET /api/applications

List/filter applications.

**Parameters:**
| Name | In | Type | Required | Description |
|------|-----|------|----------|-------------|
| status | query | string | No | Filter by status (e.g. `Applied`, `Interview`, `Offer`, `Rejected`) |
| source | query | string | No | Filter by source |
| company | query | string | No | Filter by company name (partial match) |
| company_id | query | integer | No | Filter by company ID |
| after | query | date | No | Applied on or after this date (`YYYY-MM-DD`) |
| before | query | date | No | Applied on or before this date (`YYYY-MM-DD`) |
| limit | query | integer | No | Max rows (default: 50) |
| offset | query | integer | No | Pagination offset (default: 0) |

**Response:**
```json
[
  {
    "id": 1,
    "company_id": 5,
    "company_name": "Stripe",
    "role": "VP of Engineering",
    "date_applied": "2025-01-15",
    "source": "LinkedIn",
    "status": "Interview",
    "resume_version": "v32",
    "jd_url": "https://example.com/job/123",
    "contact_name": null,
    "contact_email": null,
    "notes": null,
    "last_status_change": "2025-01-20T10:00:00",
    "created_at": "2025-01-15T00:00:00",
    "updated_at": "2025-01-20T10:00:00"
  }
]
```

---

### GET /api/applications/:app_id

Single application with interviews, emails, and company details.

**Parameters:**
| Name | In | Type | Required | Description |
|------|-----|------|----------|-------------|
| app_id | path | integer | Yes | Application ID |

**Response:** Application object with `interviews` array, `emails` array, and company fields (`co_name`, `co_sector`, `co_fit_score`, `co_priority`).

---

### POST /api/applications

Add a new application.

**Request Body:**
```json
{
  "company_id": 5,
  "company_name": "Stripe",
  "role": "VP of Engineering",
  "date_applied": "2025-01-15",
  "source": "LinkedIn",
  "status": "Applied",
  "resume_version": "v32",
  "cover_letter_path": null,
  "jd_text": null,
  "jd_url": "https://example.com/job/123",
  "contact_name": null,
  "contact_email": null,
  "notes": null
}
```

`status` defaults to `"Applied"`.

**Response:** Created row (HTTP 201).

---

### PATCH /api/applications/:app_id

Update application fields. Auto-logs status changes to `application_status_history`.

**Parameters:**
| Name | In | Type | Required | Description |
|------|-----|------|----------|-------------|
| app_id | path | integer | Yes | Application ID |

**Request Body:** Any subset of `status`, `notes`, `resume_version`, `cover_letter_path`, `jd_text`, `jd_url`, `contact_name`, `contact_email`, `source`, `saved_job_id`, `gap_analysis_id`. Optionally include `status_notes` (logged to status history but not stored on the application).

**Response:** Updated row.

---

### GET /api/applications/:app_id/status-history

Get status change history for an application.

**Parameters:**
| Name | In | Type | Required | Description |
|------|-----|------|----------|-------------|
| app_id | path | integer | Yes | Application ID |

**Response:**
```json
[
  {
    "id": 1,
    "application_id": 1,
    "old_status": "Applied",
    "new_status": "Interview",
    "notes": null,
    "changed_at": "2025-01-20T10:00:00"
  }
]
```

---

### GET /api/applications/:app_id/materials

List generated materials (resumes, cover letters) for an application.

**Parameters:**
| Name | In | Type | Required | Description |
|------|-----|------|----------|-------------|
| app_id | path | integer | Yes | Application ID |

**Response:**
```json
[
  {
    "id": 1,
    "application_id": 1,
    "type": "resume",
    "recipe_id": 2,
    "file_path": "Output/Stripe_VP_2025-01-15/resume.docx",
    "version_label": "v1",
    "notes": null,
    "generated_at": "2025-01-15T12:00:00",
    "recipe_name": "Base v32"
  }
]
```

---

### POST /api/materials

Log a generated material.

**Request Body:**
```json
{
  "application_id": 1,
  "type": "resume",
  "recipe_id": 2,
  "file_path": "Output/Stripe_VP_2025-01-15/resume.docx",
  "version_label": "v1",
  "notes": null
}
```

`type` is required.

**Response:** Created row (HTTP 201).

---

### DELETE /api/materials/:mat_id

Delete a generated material record.

**Parameters:**
| Name | In | Type | Required | Description |
|------|-----|------|----------|-------------|
| mat_id | path | integer | Yes | Material ID |

**Response:**
```json
{ "deleted": 1 }
```

---

### GET /api/applications/:app_id/follow-ups

List follow-ups for an application.

**Parameters:**
| Name | In | Type | Required | Description |
|------|-----|------|----------|-------------|
| app_id | path | integer | Yes | Application ID |

**Response:**
```json
[
  {
    "id": 1,
    "application_id": 1,
    "attempt_number": 1,
    "date_sent": "2025-01-22",
    "method": "email",
    "response_received": false,
    "notes": null
  }
]
```

---

### POST /api/follow-ups

Log a follow-up attempt. Auto-increments `attempt_number` if not provided.

**Request Body:**
```json
{
  "application_id": 1,
  "attempt_number": 1,
  "date_sent": "2025-01-22",
  "method": "email",
  "response_received": false,
  "notes": null
}
```

`application_id` is required. `response_received` defaults to `false`.

**Response:** Created row (HTTP 201).

---

### PATCH /api/follow-ups/:fu_id

Update a follow-up (e.g., mark response received).

**Parameters:**
| Name | In | Type | Required | Description |
|------|-----|------|----------|-------------|
| fu_id | path | integer | Yes | Follow-up ID |

**Request Body:** Any subset of `date_sent`, `method`, `response_received`, `notes`.

**Response:** Updated row.

---

### GET /api/applications/stale

Find active applications with no status change for N days.

**Parameters:**
| Name | In | Type | Required | Description |
|------|-----|------|----------|-------------|
| days | query | integer | No | Inactivity threshold in days (default: 14) |

**Response:**
```json
[
  {
    "id": 1,
    "company_name": "Stripe",
    "role": "VP of Engineering",
    "status": "Applied",
    "last_status_change": "2025-01-15T00:00:00",
    "date_applied": "2025-01-15",
    "days_stale": 18,
    "follow_up_count": 0
  }
]
```

Excludes applications with terminal statuses (`Rejected`, `Ghosted`, `Withdrawn`, `Accepted`, `Rescinded`).

---

## Interviews

### GET /api/interviews

List interviews with optional filters.

**Parameters:**
| Name | In | Type | Required | Description |
|------|-----|------|----------|-------------|
| application_id | query | integer | No | Filter by application |
| type | query | string | No | Filter by interview type (e.g. `Phone Screen`, `Technical`) |
| outcome | query | string | No | Filter by outcome (e.g. `pending`, `passed`, `failed`) |
| limit | query | integer | No | Max rows (default: 50) |
| offset | query | integer | No | Pagination offset (default: 0) |

**Response:**
```json
[
  {
    "id": 1,
    "application_id": 1,
    "date": "2025-01-25T14:00:00",
    "type": "Phone Screen",
    "interviewers": ["Jane Smith"],
    "calendar_event_id": null,
    "outcome": "passed",
    "feedback": null,
    "thank_you_sent": false,
    "notes": null,
    "company_name": "Stripe",
    "role": "VP of Engineering"
  }
]
```

---

### POST /api/interviews

Add an interview.

**Request Body:**
```json
{
  "application_id": 1,
  "date": "2025-01-25T14:00:00",
  "type": "Phone Screen",
  "interviewers": ["Jane Smith"],
  "calendar_event_id": null,
  "outcome": "pending",
  "feedback": null,
  "thank_you_sent": false,
  "notes": null
}
```

`outcome` defaults to `"pending"`, `thank_you_sent` to `false`.

**Response:** Created row (HTTP 201).

---

### PATCH /api/interviews/:interview_id

Update interview outcome, notes, etc.

**Parameters:**
| Name | In | Type | Required | Description |
|------|-----|------|----------|-------------|
| interview_id | path | integer | Yes | Interview ID |

**Request Body:** Any subset of `outcome`, `feedback`, `thank_you_sent`, `notes`, `date`, `type`.

**Response:** Updated row.

---

### GET /api/interviews/:interview_id/prep

Get prep materials for an interview.

**Parameters:**
| Name | In | Type | Required | Description |
|------|-----|------|----------|-------------|
| interview_id | path | integer | Yes | Interview ID |

**Response:**
```json
{
  "id": 1,
  "interview_id": 1,
  "company_dossier": {},
  "prepared_questions": [],
  "talking_points": [],
  "star_stories_selected": [],
  "questions_to_ask": [],
  "notes": null
}
```

---

### POST /api/interviews/:interview_id/prep

Create prep materials for an interview.

**Parameters:**
| Name | In | Type | Required | Description |
|------|-----|------|----------|-------------|
| interview_id | path | integer | Yes | Interview ID |

**Request Body:**
```json
{
  "company_dossier": {},
  "prepared_questions": ["Tell me about a time..."],
  "talking_points": ["Focus on platform scale"],
  "star_stories_selected": [42, 87],
  "questions_to_ask": ["What does success look like in 90 days?"],
  "notes": null
}
```

All fields optional.

**Response:** Created row (HTTP 201).

---

### PATCH /api/interview-prep/:prep_id

Update interview prep materials.

**Parameters:**
| Name | In | Type | Required | Description |
|------|-----|------|----------|-------------|
| prep_id | path | integer | Yes | Prep record ID |

**Request Body:** Any subset of `company_dossier`, `prepared_questions`, `talking_points`, `star_stories_selected`, `questions_to_ask`, `notes`.

**Response:** Updated row.

---

### GET /api/interviews/:interview_id/debrief

Get debrief for an interview.

**Parameters:**
| Name | In | Type | Required | Description |
|------|-----|------|----------|-------------|
| interview_id | path | integer | Yes | Interview ID |

**Response:**
```json
{
  "id": 1,
  "interview_id": 1,
  "went_well": ["Strong rapport with hiring manager"],
  "went_poorly": ["Stumbled on system design question"],
  "questions_asked": ["Walk me through a platform migration"],
  "next_steps": "Panel interview with CTO next week",
  "overall_feeling": "positive",
  "lessons_learned": "Prep more system design examples",
  "notes": null
}
```

---

### POST /api/interviews/:interview_id/debrief

Create a debrief for an interview.

**Parameters:**
| Name | In | Type | Required | Description |
|------|-----|------|----------|-------------|
| interview_id | path | integer | Yes | Interview ID |

**Request Body:**
```json
{
  "went_well": ["Strong rapport with hiring manager"],
  "went_poorly": ["Stumbled on system design question"],
  "questions_asked": ["Walk me through a platform migration"],
  "next_steps": "Panel interview with CTO next week",
  "overall_feeling": "positive",
  "lessons_learned": "Prep more system design examples",
  "notes": null
}
```

All fields optional.

**Response:** Created row (HTTP 201).

---

### PATCH /api/interview-debriefs/:debrief_id

Update an interview debrief.

**Parameters:**
| Name | In | Type | Required | Description |
|------|-----|------|----------|-------------|
| debrief_id | path | integer | Yes | Debrief record ID |

**Request Body:** Any subset of `went_well`, `went_poorly`, `questions_asked`, `next_steps`, `overall_feeling`, `lessons_learned`, `notes`.

**Response:** Updated row.

---

## Networking

### GET /api/contacts

List/filter/search contacts.

**Parameters:**
| Name | In | Type | Required | Description |
|------|-----|------|----------|-------------|
| company | query | string | No | Filter by company (partial match) |
| relationship | query | string | No | Filter by relationship type |
| strength | query | string | No | Filter by relationship_strength |
| q | query | string | No | Search name or title (partial match) |
| limit | query | integer | No | Max rows (default: 50) |
| offset | query | integer | No | Pagination offset (default: 0) |

**Response:**
```json
[
  {
    "id": 1,
    "name": "Jane Smith",
    "company": "Stripe",
    "title": "Engineering Manager",
    "relationship": "colleague",
    "email": "jane@stripe.com",
    "phone": null,
    "linkedin_url": "https://linkedin.com/in/janesmith",
    "relationship_strength": "strong",
    "last_contact": "2025-01-10",
    "source": "manual",
    "notes": null,
    "created_at": "2025-01-01T00:00:00",
    "updated_at": "2025-01-01T00:00:00"
  }
]
```

---

### POST /api/contacts

Add a new contact.

**Request Body:**
```json
{
  "name": "Jane Smith",
  "company": "Stripe",
  "company_id": 5,
  "title": "Engineering Manager",
  "relationship": "colleague",
  "email": "jane@stripe.com",
  "phone": null,
  "linkedin_url": "https://linkedin.com/in/janesmith",
  "relationship_strength": "strong",
  "last_contact": "2025-01-10",
  "source": "manual",
  "notes": null
}
```

`name` is required. `source` defaults to `"manual"`.

**Response:** Created row (HTTP 201).

---

### PATCH /api/contacts/:contact_id

Update contact fields.

**Parameters:**
| Name | In | Type | Required | Description |
|------|-----|------|----------|-------------|
| contact_id | path | integer | Yes | Contact ID |

**Request Body:** Any subset of POST fields (all optional).

**Response:** Updated row.

---

### DELETE /api/contacts/:contact_id

Delete a contact.

**Parameters:**
| Name | In | Type | Required | Description |
|------|-----|------|----------|-------------|
| contact_id | path | integer | Yes | Contact ID |

**Response:**
```json
{ "deleted": 1 }
```

---

### GET /api/outreach

List outreach messages with optional filters.

**Parameters:**
| Name | In | Type | Required | Description |
|------|-----|------|----------|-------------|
| contact_id | query | integer | No | Filter by contact |
| application_id | query | integer | No | Filter by application |
| channel | query | string | No | Filter by channel (e.g. `email`, `linkedin`) |
| direction | query | string | No | Filter by direction (`inbound`/`outbound`) |
| limit | query | integer | No | Max rows (default: 50) |
| offset | query | integer | No | Pagination offset (default: 0) |

**Response:**
```json
[
  {
    "id": 1,
    "contact_id": 1,
    "application_id": null,
    "interview_id": null,
    "channel": "email",
    "direction": "outbound",
    "subject": "Following up on VP role",
    "body": null,
    "sent_at": "2025-01-20T09:00:00",
    "response_received": false,
    "notes": null,
    "contact_name": "Jane Smith",
    "company_name": null,
    "role": null
  }
]
```

---

### POST /api/outreach

Log an outreach message.

**Request Body:**
```json
{
  "contact_id": 1,
  "application_id": null,
  "interview_id": null,
  "channel": "email",
  "direction": "outbound",
  "subject": "Following up on VP role",
  "body": null,
  "sent_at": "2025-01-20T09:00:00",
  "response_received": false,
  "notes": null
}
```

`channel` and `direction` are required. `response_received` defaults to `false`.

**Response:** Created row (HTTP 201).

---

### PATCH /api/outreach/:msg_id

Update an outreach message.

**Parameters:**
| Name | In | Type | Required | Description |
|------|-----|------|----------|-------------|
| msg_id | path | integer | Yes | Outreach message ID |

**Request Body:** Any subset of POST fields (all optional).

**Response:** Updated row.

---

### DELETE /api/outreach/:msg_id

Delete an outreach message.

**Parameters:**
| Name | In | Type | Required | Description |
|------|-----|------|----------|-------------|
| msg_id | path | integer | Yes | Outreach message ID |

**Response:**
```json
{ "deleted": 1 }
```

---

### GET /api/referrals

List referrals with optional filters.

**Parameters:**
| Name | In | Type | Required | Description |
|------|-----|------|----------|-------------|
| contact_id | query | integer | No | Filter by contact |
| application_id | query | integer | No | Filter by application |
| status | query | string | No | Filter by status (e.g. `pending`, `submitted`) |
| limit | query | integer | No | Max rows (default: 50) |
| offset | query | integer | No | Pagination offset (default: 0) |

**Response:**
```json
[
  {
    "id": 1,
    "contact_id": 1,
    "application_id": 1,
    "saved_job_id": null,
    "referral_date": "2025-01-18",
    "status": "submitted",
    "notes": null,
    "contact_name": "Jane Smith",
    "contact_company": "Stripe",
    "company_name": "Stripe",
    "role": "VP of Engineering",
    "job_title": null
  }
]
```

---

### POST /api/referrals

Log a referral.

**Request Body:**
```json
{
  "contact_id": 1,
  "application_id": 1,
  "saved_job_id": null,
  "referral_date": "2025-01-18",
  "status": "pending",
  "notes": null
}
```

`contact_id` is required. `status` defaults to `"pending"`.

**Response:** Created row (HTTP 201).

---

### PATCH /api/referrals/:ref_id

Update a referral.

**Parameters:**
| Name | In | Type | Required | Description |
|------|-----|------|----------|-------------|
| ref_id | path | integer | Yes | Referral ID |

**Request Body:** Any subset of `application_id`, `saved_job_id`, `referral_date`, `status`, `notes`.

**Response:** Updated row.

---

### DELETE /api/referrals/:ref_id

Delete a referral.

**Parameters:**
| Name | In | Type | Required | Description |
|------|-----|------|----------|-------------|
| ref_id | path | integer | Yes | Referral ID |

**Response:**
```json
{ "deleted": 1 }
```

---

### GET /api/companies

List/filter/search companies.

**Parameters:**
| Name | In | Type | Required | Description |
|------|-----|------|----------|-------------|
| q | query | string | No | Search company name (partial match) |
| priority | query | string | No | Filter by priority (e.g. `A`, `B`, `C`) |
| sector | query | string | No | Filter by sector (partial match) |
| min_fit_score | query | integer | No | Minimum fit_score |
| size | query | string | No | Filter by company size |
| limit | query | integer | No | Max rows (default: 50) |
| offset | query | integer | No | Pagination offset (default: 0) |

**Response:**
```json
[
  {
    "id": 5,
    "name": "Stripe",
    "sector": "Fintech",
    "hq_location": "San Francisco, CA",
    "size": "1001-5000",
    "stage": "public",
    "fit_score": 92,
    "priority": "A",
    "target_role": "VP Engineering",
    "resume_variant": "fintech",
    "key_differentiator": "Platform engineering at scale",
    "melbourne_relevant": false,
    "comp_range": "$220K-$280K",
    "notes": null,
    "created_at": "2025-01-01T00:00:00",
    "updated_at": "2025-01-01T00:00:00"
  }
]
```

---

### GET /api/companies/:company_id

Single company with applications and contacts.

**Parameters:**
| Name | In | Type | Required | Description |
|------|-----|------|----------|-------------|
| company_id | path | integer | Yes | Company ID |

**Response:** Company object with `applications` array and `contacts` array.

---

### POST /api/companies

Add a new company.

**Request Body:**
```json
{
  "name": "Stripe",
  "sector": "Fintech",
  "hq_location": "San Francisco, CA",
  "size": "1001-5000",
  "stage": "public",
  "fit_score": 92,
  "priority": "A",
  "target_role": "VP Engineering",
  "resume_variant": "fintech",
  "key_differentiator": "Platform engineering at scale",
  "melbourne_relevant": false,
  "comp_range": "$220K-$280K",
  "notes": null
}
```

`name` is required.

**Response:** Created row (HTTP 201).

---

### PATCH /api/companies/:company_id

Update company fields.

**Parameters:**
| Name | In | Type | Required | Description |
|------|-----|------|----------|-------------|
| company_id | path | integer | Yes | Company ID |

**Request Body:** Any subset of POST fields (all optional).

**Response:** Updated row.

---

## Content & Knowledge

### GET /api/content

List all available documents and their section counts.

**Response:**
```json
{
  "documents": [
    {
      "source_document": "candidate_profile",
      "section_count": 12,
      "created_at": "2025-01-01T00:00:00",
      "updated_at": "2025-01-01T00:00:00"
    }
  ]
}
```

---

### GET /api/content/:document

Get a document reconstructed from its content sections.

**Parameters:**
| Name | In | Type | Required | Description |
|------|-----|------|----------|-------------|
| document | path | string | Yes | Document name (e.g. `candidate_profile`, `rejection_analysis`) |
| section | query | string | No | Filter by section name (partial match) |
| subsection | query | string | No | Filter by subsection name (partial match) |
| format | query | string | No | `sections` (default, structured JSON) or `text` (reconstructed markdown) |

**Response (format=sections):**
```json
{
  "document": "candidate_profile",
  "sections": [
    {
      "id": 1,
      "section": "Positioning",
      "subsection": null,
      "sort_order": 1,
      "content": "Senior technology executive...",
      "content_format": "markdown",
      "tags": [],
      "metadata": {}
    }
  ],
  "count": 12
}
```

**Response (format=text):**
```json
{
  "document": "candidate_profile",
  "text": "## Positioning\n\nSenior technology executive...",
  "section_count": 12
}
```

---

### GET /api/voice-rules

Get voice rules with optional filters.

**Parameters:**
| Name | In | Type | Required | Description |
|------|-----|------|----------|-------------|
| category | query | string | No | Filter by category (e.g. `banned_word`, `banned_construction`) |
| part | query | integer | No | Filter by part number (1-8) |
| subcategory | query | string | No | Filter by subcategory |
| format | query | string | No | `rules` (default, structured JSON) or `text` (reconstructed guide) |

**Response (format=rules):**
```json
{
  "rules": [
    {
      "id": 1,
      "part": 1,
      "part_title": "Banned Words",
      "category": "banned_word",
      "subcategory": "corporate_filler",
      "rule_text": "leverage",
      "explanation": null,
      "examples_bad": [],
      "examples_good": [],
      "sort_order": 1
    }
  ],
  "count": 85
}
```

---

### POST /api/voice-rules/check

Check a piece of text against banned words and constructions.

**Request Body:**
```json
{ "text": "We leverage cutting-edge solutions to deliver synergistic outcomes." }
```

`text` is required.

**Response:**
```json
{
  "text_length": 68,
  "violations": [
    {
      "type": "banned_word",
      "match": "leverage",
      "subcategory": "corporate_filler"
    },
    {
      "type": "banned_word",
      "match": "cutting-edge",
      "subcategory": "corporate_filler"
    }
  ],
  "violation_count": 2,
  "clean": false
}
```

---

### GET /api/salary-benchmarks

Get salary benchmarks with optional filters.

**Parameters:**
| Name | In | Type | Required | Description |
|------|-----|------|----------|-------------|
| tier | query | integer | No | Filter by tier (1-5) |
| role | query | string | No | Search by role title (partial match) |
| format | query | string | No | `rows` (default, structured JSON) or `text` (formatted document) |

**Response (format=rows):**
```json
{
  "benchmarks": [
    {
      "id": 1,
      "role_title": "VP Engineering",
      "tier": 2,
      "tier_name": "Senior Leadership",
      "national_median_range": "$200K-$260K",
      "melbourne_range": "$160K-$200K",
      "remote_range": "$200K-$260K",
      "hcol_range": "$250K-$350K",
      "target_realistic": "Yes"
    }
  ],
  "count": 18
}
```

---

### GET /api/cola-markets

Get COLA market reference data (cost-of-living adjustment factors by city).

**Response:**
```json
{
  "markets": [
    {
      "id": 1,
      "market": "Melbourne, FL",
      "cola_factor": 0.82,
      "notes": "Baseline market"
    }
  ],
  "count": 12
}
```

---

### GET /api/emails

Search/filter emails.

**Parameters:**
| Name | In | Type | Required | Description |
|------|-----|------|----------|-------------|
| q | query | string | No | Full-text search across subject, snippet, body |
| category | query | string | No | Filter by category |
| from | query | string | No | Filter by sender address or name (partial match) |
| after | query | date | No | Emails on or after this date |
| before | query | date | No | Emails on or before this date |
| application_id | query | integer | No | Filter by linked application |
| limit | query | integer | No | Max rows (default: 50) |
| offset | query | integer | No | Pagination offset (default: 0) |

**Response:**
```json
[
  {
    "id": 1,
    "gmail_id": "18abc...",
    "thread_id": "18abc...",
    "date": "2025-01-20T09:00:00",
    "from_address": "recruiter@stripe.com",
    "from_name": "Jane Recruiter",
    "to_address": "stephen@example.com",
    "subject": "Your application for VP Engineering",
    "snippet": "Hi Stephen, thank you for applying...",
    "category": "recruiter_outreach",
    "application_id": 1,
    "labels": ["INBOX"],
    "created_at": "2025-01-20T09:05:00"
  }
]
```

---

### GET /api/emails/:email_id

Single email with full body.

**Parameters:**
| Name | In | Type | Required | Description |
|------|-----|------|----------|-------------|
| email_id | path | integer | Yes | Email ID |

**Response:** Full email row including `body` field.

---

### GET /api/documents

List/filter documents by type.

**Parameters:**
| Name | In | Type | Required | Description |
|------|-----|------|----------|-------------|
| type | query | string | No | Filter by document type |
| variant | query | string | No | Filter by variant |
| limit | query | integer | No | Max rows (default: 50) |
| offset | query | integer | No | Pagination offset (default: 0) |

**Response:**
```json
[
  {
    "id": 1,
    "path": "Originals/resume_v32.docx",
    "filename": "resume_v32.docx",
    "type": "resume",
    "content_hash": "sha256:abc123...",
    "version": "v32",
    "variant": "base",
    "extracted_date": "2025-01-01T00:00:00",
    "metadata_json": {},
    "created_at": "2025-01-01T00:00:00"
  }
]
```

---

### GET /api/documents/:doc_id

Single document with full content.

**Parameters:**
| Name | In | Type | Required | Description |
|------|-----|------|----------|-------------|
| doc_id | path | integer | Yes | Document ID |

**Response:** Full document row including `content` field.

---

### GET /api/resume-versions

List all resume versions (content blueprint; see also `/api/resume/versions` for spec-based versions).

**Response:**
```json
[
  {
    "id": 1,
    "version": "v32",
    "variant": "base",
    "docx_path": "Output/v32_base.docx",
    "pdf_path": null,
    "summary": null,
    "target_role_type": "CTO",
    "document_id": 1,
    "is_current": true,
    "created_at": "2025-01-01T00:00:00"
  }
]
```

---

## Search

### GET /api/search/bullets

Full-text bullet search with optional tag and role filters.

**Parameters:**
| Name | In | Type | Required | Description |
|------|-----|------|----------|-------------|
| q | query | string | No | Text search (partial match) |
| tags | query | string[] | No | Filter by tags (array intersection) |
| role_type | query | string | No | Filter by role suitability |
| industry | query | string | No | Filter by industry suitability |
| limit | query | integer | No | Max results (default: 20) |

**Response:**
```json
{
  "count": 5,
  "results": [
    {
      "id": 42,
      "text": "Led platform migration...",
      "type": "core",
      "tags": ["engineering"],
      "role_suitability": ["CTO"],
      "industry_suitability": ["SaaS"],
      "metrics_json": {},
      "detail_recall": "high",
      "employer": "Acme Corp",
      "title": "VP Engineering"
    }
  ]
}
```

---

### GET /api/search/emails

Email search with category and date filters.

**Parameters:**
| Name | In | Type | Required | Description |
|------|-----|------|----------|-------------|
| q | query | string | No | Search subject, snippet, body |
| category | query | string | No | Filter by category |
| after | query | date | No | Emails on or after this date |
| before | query | date | No | Emails on or before this date |
| limit | query | integer | No | Max results (default: 20) |

**Response:**
```json
{
  "count": 3,
  "results": [
    {
      "id": 1,
      "date": "2025-01-20T09:00:00",
      "from_name": "Jane Recruiter",
      "from_address": "recruiter@stripe.com",
      "subject": "Your application",
      "snippet": "Hi Stephen...",
      "category": "recruiter_outreach",
      "application_id": 1
    }
  ]
}
```

---

### GET /api/search/companies

Company name search.

**Parameters:**
| Name | In | Type | Required | Description |
|------|-----|------|----------|-------------|
| q | query | string | No | Search company name (partial match) |
| limit | query | integer | No | Max results (default: 20) |

**Response:**
```json
{
  "count": 2,
  "results": [
    {
      "id": 5,
      "name": "Stripe",
      "sector": "Fintech",
      "hq_location": "San Francisco, CA",
      "size": "1001-5000",
      "stage": "public",
      "fit_score": 92,
      "priority": "A",
      "target_role": "VP Engineering",
      "melbourne_relevant": false
    }
  ]
}
```

---

### GET /api/search/contacts

Find contacts, optionally filtered by company (network check).

**Parameters:**
| Name | In | Type | Required | Description |
|------|-----|------|----------|-------------|
| company | query | string | No | Filter by company name (partial match) |
| q | query | string | No | Search name or title (partial match) |
| limit | query | integer | No | Max results (default: 20) |

**Response:**
```json
{
  "count": 1,
  "results": [
    {
      "id": 1,
      "name": "Jane Smith",
      "company": "Stripe",
      "title": "Engineering Manager",
      "relationship": "colleague",
      "email": "jane@stripe.com",
      "linkedin_url": "https://linkedin.com/in/janesmith",
      "relationship_strength": "strong",
      "last_contact": "2025-01-10"
    }
  ]
}
```

---

### POST /api/gap-analysis

Live gap analysis: extract keywords from a JD and match against bullets and skills in the DB.

**Request Body:**
```json
{ "jd_text": "We're looking for a VP Engineering to lead our platform team..." }
```

`jd_text` is required.

**Response:**
```json
{
  "jd_keywords": ["platform", "engineering", "leadership", "distributed"],
  "matched_bullets": [
    {
      "id": 42,
      "text": "Led platform migration...",
      "matched_keyword": "platform",
      "employer": "Acme Corp",
      "title": "VP Engineering"
    }
  ],
  "matched_skills": [
    {
      "id": 3,
      "name": "Distributed Systems",
      "category": "Engineering",
      "proficiency": "expert",
      "last_used_year": 2024,
      "matched_keyword": "distributed"
    }
  ],
  "gaps": ["agile", "budget"],
  "coverage_pct": 86.7
}
```

Note: This endpoint performs an in-memory analysis and does not persist results. To save a gap analysis, use `POST /api/gap-analyses`.

---

## Analytics

### GET /api/analytics/funnel

Application funnel by status with counts and percentages.

**Response:**
```json
[
  { "status": "Applied", "count": 45, "pct": 100.0 },
  { "status": "Interview", "count": 12, "pct": 26.7 },
  { "status": "Offer", "count": 2, "pct": 4.4 }
]
```

---

### GET /api/analytics/monthly

Monthly activity breakdown.

**Response:**
```json
[
  {
    "month": "2025-01",
    "applications": 12,
    "interviews": 4,
    "rejections": 3,
    "ghosted": 2,
    "offers": 0
  }
]
```

---

### GET /api/analytics/sources

Source effectiveness: application-to-response and application-to-interview rates by source.

**Response:**
```json
[
  {
    "source": "LinkedIn",
    "total_apps": 20,
    "got_response": 8,
    "response_rate_pct": 40.0,
    "got_interview": 4,
    "interview_rate_pct": 20.0
  }
]
```

---

### GET /api/analytics/summary

Overall campaign statistics.

**Response:**
```json
{
  "total_applications": 45,
  "applied": 20,
  "in_progress": 10,
  "offers": 2,
  "rejected": 8,
  "ghosted": 5,
  "total_interviews": 15,
  "total_companies": 30,
  "total_contacts": 42,
  "total_emails": 120,
  "unique_sources": 6
}
```

---

## Activity Log

### GET /api/activity

Recent activity feed with optional filters.

**Parameters:**
| Name | In | Type | Required | Description |
|------|-----|------|----------|-------------|
| action | query | string | No | Filter by action type |
| entity_type | query | string | No | Filter by entity type (e.g. `application`, `interview`) |
| entity_id | query | integer | No | Filter by specific entity ID |
| days | query | integer | No | Limit to last N days |
| limit | query | integer | No | Max rows (default: 50) |
| offset | query | integer | No | Pagination offset (default: 0) |

**Response:**
```json
[
  {
    "id": 1,
    "action": "status_change",
    "entity_type": "application",
    "entity_id": 1,
    "details": { "old_status": "Applied", "new_status": "Interview" },
    "created_at": "2025-01-20T10:00:00"
  }
]
```

---

### POST /api/activity

Log an activity event.

**Request Body:**
```json
{
  "action": "status_change",
  "entity_type": "application",
  "entity_id": 1,
  "details": { "old_status": "Applied", "new_status": "Interview" }
}
```

`action` is required.

**Response:** Created row (HTTP 201).

---

## Onboarding

### POST /api/onboard/upload

Upload one or more `.docx` or `.pdf` resume files. Runs the full onboarding pipeline: text extraction, AI/rule-based parsing, DB insertion with dedup, templatization, recipe creation, reconstruction, and diff scoring.

**Request Body:** `multipart/form-data` with field name `files` (supports multiple files).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| files | file[] | Yes | One or more `.docx` or `.pdf` files |

**Response:**
```json
{
  "results": [
    {
      "filename": "resume_v32.docx",
      "status": "success",
      "upload_id": 1,
      "template_id": 3,
      "recipe_id": 7,
      "match_score": 94.2,
      "parsing_method": "ai_enhanced",
      "parsing_confidence": 0.91,
      "steps": {
        "text_extraction": "ok (14832 chars)",
        "parsing": {
          "method": "ai_enhanced",
          "confidence": 0.91,
          "career_history_count": 5,
          "bullet_count": 48,
          "skill_count": 32
        },
        "db_insert": {
          "career_history_ids": [1, 2, 3, 4, 5],
          "bullet_ids": [10, 11, 12],
          "skill_ids": [1, 2, 3],
          "near_duplicates": [],
          "skipped_exact_dups": 35
        },
        "template_stored": { "template_id": 3 },
        "templatize": { "slots": 42, "template_docx": "/tmp/..." },
        "recipe": { "recipe_id": 7, "slot_count": 42 },
        "reconstruct": "ok",
        "compare": {
          "match_score": 94.2,
          "total_paragraphs": 85,
          "matching_paragraphs": 80,
          "diff_preview": "(identical)"
        }
      },
      "errors": []
    }
  ],
  "total": 1
}
```

Status values: `success`, `partial` (some steps failed but data was saved), `failed`.
