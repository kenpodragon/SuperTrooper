-- ============================================================================
-- Migration 002: Seed enum-like reference values
-- Created: 2026-03-18
-- Depends on: 001_initial_schema
--
-- These are not database ENUMs (which are rigid). Instead, these are INSERT
-- statements that pre-populate common values so that the application layer
-- has consistent reference data. The VARCHAR columns remain flexible for
-- new values added later.
-- ============================================================================

BEGIN;

-- ============================================================================
-- Application Statuses (applications.status)
-- ============================================================================
-- Reference list only... these live as VARCHAR values in the applications table.
-- Ordered by pipeline stage:
--
--   Saved -> Applied -> Phone Screen -> Interview -> Technical -> Final ->
--   Offer -> Accepted
--   (Terminal: Rejected, Ghosted, Withdrawn, Rescinded)
--
-- No separate table needed. This comment serves as the canonical list.

-- ============================================================================
-- Application Sources (applications.source)
-- ============================================================================
-- Indeed, LinkedIn, Dice, ZipRecruiter, Direct, Recruiter, Referral

-- ============================================================================
-- Bullet Types (bullets.type)
-- ============================================================================
-- core, alternate, deep_cut, interview_only

-- ============================================================================
-- Pre-populate skills with common categories
-- ============================================================================
-- Skill categories: language, framework, platform, methodology, tool

INSERT INTO skills (name, category, proficiency) VALUES
    -- Languages
    ('Python',          'language',     'expert'),
    ('JavaScript',      'language',     'expert'),
    ('TypeScript',      'language',     'proficient'),
    ('SQL',             'language',     'expert'),
    ('Java',            'language',     'proficient'),
    ('C#',              'language',     'proficient'),
    ('C++',             'language',     'familiar'),
    ('Bash',            'language',     'proficient'),
    ('R',               'language',     'familiar'),

    -- Frameworks & Libraries
    ('React',           'framework',    'proficient'),
    ('Flask',           'framework',    'proficient'),
    ('Django',          'framework',    'familiar'),
    ('Node.js',         'framework',    'proficient'),
    ('FastAPI',         'framework',    'familiar'),
    ('.NET',            'framework',    'proficient'),
    ('Spring Boot',     'framework',    'familiar'),

    -- Platforms & Infrastructure
    ('AWS',             'platform',     'expert'),
    ('Azure',           'platform',     'proficient'),
    ('GCP',             'platform',     'familiar'),
    ('Docker',          'platform',     'proficient'),
    ('Kubernetes',      'platform',     'proficient'),
    ('PostgreSQL',      'platform',     'expert'),
    ('Redis',           'platform',     'proficient'),
    ('Kafka',           'platform',     'familiar'),
    ('Terraform',       'platform',     'proficient'),

    -- Methodologies
    ('Agile/Scrum',     'methodology',  'expert'),
    ('SAFe',            'methodology',  'proficient'),
    ('DevOps/CI-CD',    'methodology',  'expert'),
    ('TDD',             'methodology',  'proficient'),
    ('TOGAF',           'methodology',  'familiar'),
    ('Six Sigma',       'methodology',  'familiar'),
    ('OKRs',            'methodology',  'expert'),

    -- Tools
    ('Git',             'tool',         'expert'),
    ('Jira',            'tool',         'expert'),
    ('Confluence',      'tool',         'proficient'),
    ('Jenkins',         'tool',         'proficient'),
    ('GitHub Actions',  'tool',         'proficient'),
    ('Tableau',         'tool',         'familiar'),
    ('Power BI',        'tool',         'familiar'),
    ('Datadog',         'tool',         'proficient'),
    ('Splunk',          'tool',         'familiar')
ON CONFLICT DO NOTHING;

-- ============================================================================
-- Pre-populate summary_variants with role types (empty text, to be filled)
-- ============================================================================
INSERT INTO summary_variants (role_type, text) VALUES
    ('CTO',             ''),
    ('VP Engineering',  ''),
    ('Director',        ''),
    ('AI Architect',    ''),
    ('SW Architect',    ''),
    ('PM',              ''),
    ('Sr SWE',          '')
ON CONFLICT DO NOTHING;

-- ============================================================================
-- Record migration
-- ============================================================================
INSERT INTO schema_migrations (version, name)
VALUES ('002', 'seed_enums');

COMMIT;
