# MCP Tool Reference

SuperTroopers exposes 42 tools via Model Context Protocol (MCP). Connect via SSE at `http://localhost:8056/sse`.

## Connection

Add to your `.mcp.json`:
```json
{
  "mcpServers": {
    "supertroopers": {
      "type": "sse",
      "url": "http://localhost:8056/sse"
    }
  }
}
```

---

## Career & Knowledge Base

### search_bullets

Search resume bullets by text, tags, role type, or industry.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| query | str | No | Text to search for in bullet text (ILIKE). |
| tags | list[str] | No | List of tags to filter by (array overlap). |
| role_type | str | No | Filter by role suitability (e.g. CTO, VP Eng, Director). |
| industry | str | No | Filter by industry suitability (e.g. defense, manufacturing). |
| limit | int | No | Max results to return (default 20). |

**Returns:** List of matching bullet records with text, tags, role_type, industry, and metadata.

**Example:** "Search my bullets for leadership experience in defense."

---

### get_career_history

Get career history for an employer (or all if blank).

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| employer | str | No | Employer name to search (ILIKE match). Leave blank for all. |

**Returns:** List of positions with employer, title, dates, and associated bullets.

**Example:** "Show me my full career history" or "What did I do at Leidos?"

---

### get_skills

List skills, optionally filtered by category.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| category | str | No | Skill category filter (language, framework, platform, methodology, tool). |

**Returns:** List of skills with name, category, and proficiency level.

**Example:** "What are my skills?" or "List my programming languages."

---

### get_summary_variant

Get a professional summary variant for a target role type.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| role_type | str | Yes | Target role (e.g. CTO, VP Eng, Director, AI Architect, SW Architect, PM, Sr SWE). |

**Returns:** Summary text tailored to the specified role type.

**Example:** "Get me a summary for a VP Engineering role."

---

### get_candidate_profile

Get candidate profile data. Returns full profile or specific sections.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| section | str | No | Filter by section name (e.g. "Identity", "Career Narrative", "Target Roles", "Compensation", "References"). Leave blank for all. |
| format | str | No | "sections" for structured data, "text" for reconstructed markdown (default "sections"). |

**Returns:** Candidate profile data in structured or markdown format.

**Example:** "Show me my candidate profile" or "What are my target roles and compensation expectations?"

---

## Resume Generation

### get_resume_data

Get full resume data for reconstruction or querying. Returns header, spec, experience, education, certs.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| version | str | No | Resume version (default v32). |
| variant | str | No | Resume variant (default base). |
| section | str | No | Optional filter: "header", "education", "certifications", "experience", "spec", "keywords". Leave blank for all. |

**Returns:** Full resume data dict with requested sections.

**Example:** "Get my current resume data" or "Show me the experience section of my resume."

---

### generate_resume

Generate a .docx resume from a recipe or legacy spec.

When recipe_id is provided, uses recipe-based generation (pointer references). Otherwise falls back to legacy spec-based generation.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| version | str | No | Resume version for legacy path (default v32). |
| variant | str | No | Resume variant for legacy path (default base). |
| output_path | str | No | Where to save the .docx. Defaults to Output/resume_{version}_{variant}.docx. |
| recipe_id | int | No | Recipe ID from resume_recipes (0 = use legacy spec path). |

**Returns:** `{"output_path": str, "status": str}` with path to generated .docx file.

**Example:** "Generate my resume using recipe 5" or "Build a resume from my base spec."

---

### list_recipes

List available resume recipes.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| template_id | int | No | Filter by template ID (0 = all templates). |
| is_active | bool | No | Filter by active status (default True). |

**Returns:** List of recipe records with id, name, headline, template_id, description, and is_active.

**Example:** "What resume recipes do I have?" or "List my active recipes."

---

### get_recipe

Get a single resume recipe with full JSON.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| recipe_id | int | Yes | Recipe ID to fetch. |

**Returns:** Full recipe record including slot-to-source mapping JSON.

**Example:** "Show me the details of recipe 3."

---

### create_recipe

Create a new resume recipe.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| name | str | No | Recipe name (e.g. "V32 AI Architect - Optum"). |
| headline | str | No | Resume headline text. |
| template_id | int | No | ID of the template to use. |
| recipe_json | str | No | JSON string of slot-to-source mappings. |
| description | str | No | Optional description. |
| application_id | int | No | Optional linked application ID (0 = none). |

**Returns:** `{"recipe_id": int, "status": str}` for the newly created recipe.

**Example:** "Create a new recipe for my Optum application."

---

### update_recipe

Update an existing resume recipe.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| recipe_id | int | No | Recipe ID to update. |
| name | str | No | New name (empty = keep current). |
| headline | str | No | New headline (empty = keep current). |
| recipe_json | str | No | New recipe JSON (empty = keep current). |
| description | str | No | New description (empty = keep current). |
| is_active | bool | No | Active status (default True). |

**Returns:** `{"status": str, "updated": int}` with count of updated rows.

**Example:** "Update recipe 5 with a new headline."

---

## Job Search & Analysis

### match_jd

Match a job description against resume bullets. Returns best matches and gaps.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| jd_text | str | Yes | Full job description text to analyze. |

**Returns:** Dict with strong_matches, partial_matches, gaps, bonus_value, fit_scores, overall_score, and recommendation.

**Example:** "Analyze this job description against my resume" or "How well do I match this JD?"

---

### save_job

Save a job to the evaluation queue.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| title | str | Yes | Job title (required). |
| company | str | No | Company name. |
| url | str | No | Job posting URL. |
| jd_text | str | No | Full job description text. |
| source | str | No | Where the job was found (indeed, linkedin, manual, etc.). |
| fit_score | float | No | Initial fit score (0-10). |
| notes | str | No | Any notes about the job. |

**Returns:** `{"saved_job_id": int, "status": str}` for the newly saved job.

**Example:** "Save this job posting to my evaluation queue."

---

### list_saved_jobs

List saved jobs in the evaluation queue.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| status | str | No | Filter by status (saved, evaluating, applying, applied, passed). Empty = all. |
| limit | int | No | Max results (default 20). |

**Returns:** List of saved job records with title, company, url, fit_score, status, and notes.

**Example:** "What jobs do I have saved to evaluate?" or "Show me jobs I'm currently considering."

---

### update_saved_job

Update a saved job's status, score, or notes.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| job_id | int | Yes | Saved job ID (required). |
| status | str | No | New status (saved, evaluating, applying, applied, passed). |
| fit_score | float | No | Updated fit score (0-10). |
| notes | str | No | Updated notes. |

**Returns:** `{"status": str, "updated": int}` with count of updated rows.

**Example:** "Mark saved job 12 as applying with a fit score of 8."

---

### save_gap_analysis

Save a gap analysis result to the database.

All JSON fields (strong_matches, partial_matches, gaps, bonus_value, fit_scores) should be passed as JSON strings.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| jd_text | str | No | The job description text analyzed. |
| application_id | int | No | Link to an application (0 = none). |
| saved_job_id | int | No | Link to a saved job (0 = none). |
| strong_matches | str | No | JSON string of strong match items. |
| partial_matches | str | No | JSON string of partial match items. |
| gaps | str | No | JSON string of gap items. |
| bonus_value | str | No | JSON string of bonus value items. |
| fit_scores | str | No | JSON string of fit score breakdown. |
| overall_score | float | No | Overall fit score (0-10). |
| recommendation | str | No | Apply/pass/consider recommendation. |
| notes | str | No | Additional notes. |

**Returns:** `{"gap_id": int, "status": str}` for the saved analysis.

**Example:** "Save the gap analysis results for my Optum application."

---

### get_gap_analysis

Retrieve a gap analysis by ID or by linked application/saved job.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| gap_id | int | No | Gap analysis ID (direct lookup). |
| application_id | int | No | Find gap analysis linked to this application. |
| saved_job_id | int | No | Find gap analysis linked to this saved job. |

**Returns:** Gap analysis record with matches, gaps, scores, and recommendation.

**Example:** "Show me the gap analysis for application 7" or "Retrieve gap analysis 3."

---

## Applications & Pipeline

### search_applications

Search job applications by status, company, or source.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| status | str | No | Filter by status (Applied, Interview, Rejected, etc.). |
| company | str | No | Filter by company name (ILIKE match). |
| source | str | No | Filter by source (Indeed, LinkedIn, etc.). |
| limit | int | No | Max results (default 50). |

**Returns:** List of application records with id, company, role, status, date_applied, and notes.

**Example:** "Show all my active applications" or "What applications do I have at Google?"

---

### add_application

Add a new job application to the tracker.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| company_name | str | Yes | Company name. |
| role | str | Yes | Job title / role applied for. |
| source | str | No | Application source (Indeed, LinkedIn, Dice, ZipRecruiter, Direct, Recruiter, Referral). |
| status | str | No | Initial status (default Applied). |
| notes | str | No | Any notes. |
| company_id | int | No | Optional company ID if known. |
| date_applied | str | No | Date applied (YYYY-MM-DD). Defaults to today. |
| jd_url | str | No | Job description URL. |
| jd_text | str | No | Job description text. |

**Returns:** `{"application_id": int, "status": str}` for the new application.

**Example:** "Log that I applied to Optum for VP Engineering today via LinkedIn."

---

### update_application

Update an application's status and/or notes.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| id | int | Yes | Application ID. |
| status | str | No | New status value. |
| notes | str | No | Updated notes (replaces existing). |

**Returns:** `{"status": str, "updated": int}` with count of updated rows.

**Example:** "Update application 14 to Interview status."

---

### log_follow_up

Log a follow-up attempt for an application.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| application_id | int | Yes | Application ID (required). |
| method | str | No | Contact method (email, linkedin, phone). |
| date_sent | str | No | Date sent (YYYY-MM-DD). Defaults to today. |
| notes | str | No | Notes about the follow-up. |

**Returns:** `{"follow_up_id": int, "status": str}` for the logged follow-up.

**Example:** "Log that I sent a follow-up email to Optum today."

---

### get_stale_applications

Find applications with no activity for N days.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| days | int | No | Number of days without activity to consider stale (default 14). |

**Returns:** List of stale application records with last activity date and days since activity.

**Example:** "Which applications haven't had any activity in 2 weeks?"

---

## Interviews

### save_interview_prep

Save interview prep materials. JSON fields should be passed as JSON strings.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| interview_id | int | Yes | Interview ID (required). |
| company_dossier | str | No | JSON string of company research snapshot. |
| prepared_questions | str | No | JSON string of prepared Q&A items. |
| talking_points | str | No | JSON string of talking points. |
| star_stories_selected | str | No | JSON string of selected STAR stories. |
| questions_to_ask | str | No | JSON string of questions to ask the interviewer. |
| notes | str | No | Additional notes. |

**Returns:** `{"status": str, "prep_id": int}` for the saved prep record.

**Example:** "Save my interview prep for interview 5 at Optum."

---

### save_interview_debrief

Save a structured interview debrief. JSON fields as JSON strings.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| interview_id | int | Yes | Interview ID (required). |
| went_well | str | No | JSON string of things that went well. |
| went_poorly | str | No | JSON string of things that went poorly. |
| questions_asked | str | No | JSON string of questions asked and answers given. |
| next_steps | str | No | Free-text next steps. |
| overall_feeling | str | No | great, good, neutral, concerned, or poor. |
| lessons_learned | str | No | Free-text lessons learned. |
| notes | str | No | Additional notes. |

**Returns:** `{"status": str, "debrief_id": int}` for the saved debrief record.

**Example:** "Save my debrief for the Optum interview... it went well overall."

---

## Networking

### search_contacts

Search contacts by company or name.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| company | str | No | Company name filter (ILIKE). |
| name | str | No | Contact name filter (ILIKE). |

**Returns:** List of contact records with name, company, title, and relationship notes.

**Example:** "Who do I know at Lockheed Martin?" or "Find my contact Sarah at Booz Allen."

---

### network_check

Find contacts and related emails for a company. Useful for warm intro research.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| company | str | Yes | Company name to check network for. |

**Returns:** Dict with contacts list and related email threads for the company.

**Example:** "Do I have any connections at Palantir I could reach out to?"

---

### search_companies

Search target companies by name, priority, or sector.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| query | str | No | Company name search (ILIKE). |
| priority | str | No | Priority tier (A, B, C). |
| sector | str | No | Sector filter (ILIKE). |
| limit | int | No | Max results (default 50). |

**Returns:** List of company records with name, priority, sector, and notes.

**Example:** "Show me my A-list target companies" or "What defense companies am I tracking?"

---

### get_company_dossier

Get full company info including applications, contacts, and related emails.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| name | str | Yes | Company name (ILIKE match). |

**Returns:** Full company dossier with profile, open applications, known contacts, and related email threads.

**Example:** "Give me a full dossier on Leidos" or "What do I know about Optum?"

---

## Content & Voice

### get_voice_rules

Get voice guide rules for content generation. Use to check writing quality.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| category | str | No | Filter by rule type: banned_word, banned_construction, caution_word, structural_tell, resume_rule, cover_letter_rule, final_check, linkedin_pattern, stephen_ism, context_pattern, quick_reference. Leave blank for all. |
| part | int | No | Filter by Voice Guide part number (1-8). 0 = all parts. |
| format | str | No | "rules" for structured data, "text" for reconstructed guide (default "rules"). |

**Returns:** Voice rules in structured or text format, scoped to requested category/part.

**Example:** "Get the banned words list" or "Show me the final check rules before I submit this resume."

---

### check_voice

Check text against voice guide banned words and constructions. Returns violations.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| text | str | Yes | The text to check against voice rules. |

**Returns:** Dict with `violations` list (each with rule, matched_text, suggestion) and `pass` boolean.

**Example:** "Check this cover letter paragraph for voice violations."

---

### get_salary_data

Get salary benchmarks and COLA market data for target roles.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| role | str | No | Search by role title (e.g. "CTO", "VP", "Director"). Leave blank for all. |
| tier | int | No | Filter by tier (1=Executive, 2=Director, 3=Senior IC, 4=PM, 5=Academia). 0 = all. |

**Returns:** List of salary records with role, tier, base_low, base_high, total_comp, and market notes.

**Example:** "What's the market rate for a VP Engineering role?" or "Show me executive-tier salary benchmarks."

---

### get_rejection_analysis

Get rejection and ghosting analysis data.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| section | str | No | Filter by section (e.g. "Companies with Confirmed Interview Activity", "Pattern Analysis"). Leave blank for all. |
| format | str | No | "sections" for structured data, "text" for reconstructed markdown (default "sections"). |

**Returns:** Rejection analysis data including patterns, company-level outcomes, and recommendations.

**Example:** "Show me my rejection patterns" or "What patterns show up in my ghosting history?"

---

### search_emails

Search emails by text, category, and date range.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| query | str | No | Text search in subject, snippet, body (ILIKE). |
| category | str | No | Email category (application, rejection, interview, recruiter, reference, other). |
| after | str | No | Date filter - emails after this date (YYYY-MM-DD). |
| before | str | No | Date filter - emails before this date (YYYY-MM-DD). |
| limit | int | No | Max results (default 20). |

**Returns:** List of email records with subject, snippet, category, date, and thread_id.

**Example:** "Find all recruiter emails from this month" or "Search for emails about Optum."

---

### get_analytics

Get pipeline statistics: funnel, source effectiveness, monthly activity, and summary counts.

*No parameters.*

**Returns:** Dict with funnel metrics (applied/interview/offer rates), source breakdown, monthly activity counts, and summary totals.

**Example:** "Show me my application pipeline stats" or "How is my job search performing?"

---

## Document Utilities

### mcp_read_docx

Extract text from a .docx file.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| file_path | str | Yes | Path to the .docx file. |

**Returns:** `{"text": str, "paragraphs": int}` with full extracted text and paragraph count.

**Example:** "Read the text from my resume docx."

---

### mcp_read_pdf

Extract text from a .pdf file.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| file_path | str | Yes | Path to the .pdf file. |
| pages | str | No | Optional page range (e.g., "1-5"). Default reads all. |

**Returns:** `{"text": str}` with full extracted text.

**Example:** "Extract text from this PDF job description."

---

### mcp_edit_docx

Find and replace text in a .docx file.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| file_path | str | Yes | Path to the .docx file. |
| find_text | str | Yes | Text to find. |
| replace_text | str | Yes | Replacement text. |
| output_path | str | No | Optional output path. Defaults to overwriting original. |
| replace_all | bool | No | Replace all occurrences (default False). |

**Returns:** `{"replacements": int}` with count of replacements made.

**Example:** "Update the phone number in my resume docx."

---

### mcp_docx_to_pdf

Convert a .docx file to .pdf.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| file_path | str | Yes | Path to the .docx file. |
| output_path | str | No | Optional output path. Defaults to same name with .pdf extension. |

**Returns:** `{"pdf_path": str}` with path to the generated PDF.

**Example:** "Convert my tailored resume docx to PDF."

---

### mcp_templatize_resume

Convert a .docx resume into a placeholder template.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| file_path | str | Yes | Path to the .docx resume. |
| output_dir | str | No | Directory for output files (default /tmp). |
| layout | str | No | Template layout name (default "auto"). |

**Returns:** `{"template_path": str, "map_path": str, "slots": int}` with template file, slot map file, and slot count.

**Example:** "Templatize my base resume to create a reusable template."

---

### mcp_compare_docs

Compare two .docx documents and return a match score and diff.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| file_a | str | Yes | Path to first .docx document. |
| file_b | str | Yes | Path to second .docx document. |

**Returns:** `{"match_percentage": float, "diff_count": int, "diff_text": str}` with similarity score and line-level diff.

**Example:** "Compare my base resume with the tailored version for Optum."

---

## Onboarding

### onboard_resume

Run the full onboarding pipeline on a resume file.

Parses resume into career data, creates template and recipe, and verifies reconstruction.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| file_path | str | Yes | Path to .docx or .pdf resume file. |

**Returns:** Full pipeline report with inserted row counts, template/recipe IDs, and match score.

**Example:** "Onboard my new resume file to set up the system."

---

## Profile

### update_header

Update resume header / candidate contact info.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| full_name | str | No | Full name. |
| credentials | str | No | Credentials string (e.g. "PhD, CSM, PMP, MBA"). |
| email | str | No | Email address. |
| phone | str | No | Phone number. |
| location | str | No | Location. |
| linkedin_url | str | No | LinkedIn profile URL. |

**Returns:** `{"status": str, "updated": int}` confirming the update.

**Example:** "Update my resume header with my new phone number."
