-- Migration 017: LinkedIn Profile & Brand Management
-- Rollback: DROP TABLE IF EXISTS linkedin_skills_audits, linkedin_voice_rules, linkedin_theme_pillars, linkedin_post_engagement, linkedin_posts, linkedin_profile_audits CASCADE;

BEGIN;

CREATE TABLE IF NOT EXISTS linkedin_profile_audits (
  id SERIAL PRIMARY KEY,
  audit_type VARCHAR(30) NOT NULL DEFAULT 'full',  -- full, headline, about, experience, skills, featured
  overall_score REAL,
  section_scores JSONB,  -- {"headline": 85, "about": 70, "experience": 90, "skills": 60, "featured": 40}
  recommendations JSONB,  -- [{"section": "headline", "priority": "high", "suggestion": "..."}]
  target_jd_ids JSONB,  -- [saved_job_id, ...] used for match scoring
  match_scores JSONB,  -- {"jd_42": 78.5, "jd_55": 65.2}
  keyword_gaps JSONB,  -- {"missing": ["kubernetes", "terraform"], "section_suggestions": {...}}
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS linkedin_posts (
  id SERIAL PRIMARY KEY,
  content TEXT NOT NULL,
  post_type VARCHAR(30) DEFAULT 'text',  -- text, article, poll, carousel, video, document
  theme_pillar_id INTEGER,
  status VARCHAR(20) DEFAULT 'draft',  -- draft, published, scheduled
  published_at TIMESTAMP,
  linkedin_url TEXT,
  hook_text TEXT,  -- first ~210 chars before "see more"
  hashtags JSONB,  -- ["#leadership", "#techcareers"]
  char_count INTEGER,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS linkedin_post_engagement (
  id SERIAL PRIMARY KEY,
  post_id INTEGER REFERENCES linkedin_posts(id) ON DELETE CASCADE,
  snapshot_day INTEGER NOT NULL DEFAULT 1,  -- 1, 3, 7 for decay tracking
  impressions INTEGER DEFAULT 0,
  reactions INTEGER DEFAULT 0,
  comments INTEGER DEFAULT 0,
  reposts INTEGER DEFAULT 0,
  engagement_rate REAL,  -- calculated: (reactions+comments+reposts)/impressions
  captured_at TIMESTAMP DEFAULT NOW(),
  UNIQUE(post_id, snapshot_day)
);

CREATE TABLE IF NOT EXISTS linkedin_theme_pillars (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT,
  target_role_types JSONB,  -- ["engineering_leader", "cto"]
  keywords JSONB,  -- ["AI/ML", "team building", "scale"]
  color VARCHAR(7),  -- hex color for UI
  sort_order INTEGER DEFAULT 0,
  active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS linkedin_voice_rules (
  id SERIAL PRIMARY KEY,
  category VARCHAR(30) NOT NULL,  -- tone, structure, vocabulary, hook, cta, banned_patterns
  rule_text TEXT NOT NULL,
  source VARCHAR(20) DEFAULT 'manual',  -- manual, ai_extracted, template
  persona_template VARCHAR(30),  -- executive, technical, creative, academic (null = custom)
  active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS linkedin_skills_audits (
  id SERIAL PRIMARY KEY,
  target_jd_ids JSONB,  -- [saved_job_id, ...]
  skills_keep JSONB,  -- [{"skill": "Python", "relevance": "high", "jd_frequency": 85}]
  skills_add JSONB,
  skills_remove JSONB,
  skills_reprioritize JSONB,
  top_50_recommended JSONB,  -- ranked list
  endorsement_gaps JSONB,  -- [{"skill": "Python", "endorsements": 3, "target": 10}]
  skill_role_mapping JSONB,  -- {"Python": ["Senior Engineer @ Acme", "Lead @ Foo"]}
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_linkedin_posts_status ON linkedin_posts(status);
CREATE INDEX IF NOT EXISTS idx_linkedin_posts_theme ON linkedin_posts(theme_pillar_id);
CREATE INDEX IF NOT EXISTS idx_linkedin_posts_published ON linkedin_posts(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_linkedin_voice_rules_category ON linkedin_voice_rules(category);
CREATE INDEX IF NOT EXISTS idx_linkedin_profile_audits_created ON linkedin_profile_audits(created_at DESC);

COMMIT;
