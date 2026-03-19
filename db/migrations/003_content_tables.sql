-- Migration 003: Content tables for document-to-DB migration
-- Stores structured content from Notes/*.md files with full reconstruction support
-- Tables: content_sections, voice_rules, salary_benchmarks, cola_markets

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. content_sections — generic document section store
--    Handles: CANDIDATE_PROFILE, REJECTION_ANALYSIS, APPLICATION_HISTORY, EMAIL_SCAN_DEEP
--    Supports: full document reconstruction (source_document + sort_order)
--              section-level querying (section/subsection)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS content_sections (
    id SERIAL PRIMARY KEY,
    source_document VARCHAR(100) NOT NULL,   -- candidate_profile, rejection_analysis, application_history, email_scan_deep
    section VARCHAR(200) NOT NULL,           -- e.g. "Identity", "Career Narrative", "Target Roles"
    subsection VARCHAR(200),                 -- e.g. "Primary", "Secondary", "Compensation"
    sort_order INTEGER NOT NULL DEFAULT 0,   -- for reconstruction ordering
    content TEXT NOT NULL,                   -- the actual markdown content
    content_format VARCHAR(20) DEFAULT 'markdown',  -- markdown, table, list, text
    tags TEXT[],                             -- optional tags for filtering
    metadata JSONB,                          -- flexible metadata (key-value pairs)
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_content_sections_source ON content_sections(source_document);
CREATE INDEX IF NOT EXISTS idx_content_sections_section ON content_sections(source_document, section);
CREATE INDEX IF NOT EXISTS idx_content_sections_tags ON content_sections USING GIN(tags);

-- ---------------------------------------------------------------------------
-- 2. voice_rules — structured rules from VOICE_GUIDE.md
--    Each rule is individually queryable with category/type filtering
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS voice_rules (
    id SERIAL PRIMARY KEY,
    part INTEGER NOT NULL,                   -- 1-8 maps to Voice Guide parts
    part_title VARCHAR(200) NOT NULL,        -- "Banned Vocabulary", "Banned Constructions", etc.
    category VARCHAR(50) NOT NULL,           -- banned_word, banned_construction, caution_word, structural_tell, resume_rule, cover_letter_rule, final_check, linkedin_pattern, stephen_ism, context_pattern
    subcategory VARCHAR(100),                -- e.g. "buzzword_verb", "buzzword_adjective", "false_authority", "engagement_bait"
    rule_text TEXT NOT NULL,                 -- the actual rule/pattern
    explanation TEXT,                        -- why it's banned/required
    examples_bad TEXT[],                     -- bad examples
    examples_good TEXT[],                    -- good replacements
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_voice_rules_part ON voice_rules(part);
CREATE INDEX IF NOT EXISTS idx_voice_rules_category ON voice_rules(category);

-- ---------------------------------------------------------------------------
-- 3. salary_benchmarks — role-by-role salary data
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS salary_benchmarks (
    id SERIAL PRIMARY KEY,
    role_title VARCHAR(200) NOT NULL,
    tier INTEGER NOT NULL,                   -- 1=Executive, 2=Director, 3=Sr IC, 4=PM, 5=Academia
    tier_name VARCHAR(100) NOT NULL,         -- "Executive / C-Suite", "Director-Level", etc.
    national_median_range VARCHAR(100),      -- "$285,000 - $327,000"
    melbourne_range VARCHAR(100),            -- "$180,000 - $260,000"
    remote_range VARCHAR(100),              -- "$220,000 - $350,000"
    hcol_range VARCHAR(100),               -- "$350,000 - $500,000+"
    target_realistic TEXT,                  -- assessment of whether $200-250K is realistic
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- 4. cola_markets — cost of living reference data
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS cola_markets (
    id SERIAL PRIMARY KEY,
    market_name VARCHAR(100) NOT NULL,
    col_index_approx VARCHAR(20),           -- "96-98", "180", etc.
    cola_factor NUMERIC(4,2),               -- 1.00, 1.55, 1.86, etc.
    melbourne_200k_equiv INTEGER,           -- what $200K Melbourne = in that market
    melbourne_250k_equiv INTEGER,
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- Record migration
-- ---------------------------------------------------------------------------

INSERT INTO schema_migrations (version, name) VALUES (3, '003_content_tables');

COMMIT;
