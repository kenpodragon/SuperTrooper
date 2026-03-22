-- 022_skills_development.sql
-- Skills development & certification planning tables
-- Phase 5D (S16)

BEGIN;

-- Learning plans table
CREATE TABLE IF NOT EXISTS learning_plans (
    id SERIAL PRIMARY KEY,
    skill_name VARCHAR(200) NOT NULL,
    gap_category VARCHAR(30) DEFAULT 'deep_gap',  -- not_showcased, adjacent, deep_gap
    priority INTEGER DEFAULT 3,  -- 1=highest
    resources JSONB,  -- [{name, url, type, cost, time_hours}]
    milestones JSONB,  -- [{milestone, target_date, completed}]
    status VARCHAR(20) DEFAULT 'planned',  -- planned, in_progress, completed, deferred
    jd_unlock_count INTEGER DEFAULT 0,  -- how many more JDs this skill would match
    estimated_hours INTEGER,
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_learning_plans_status ON learning_plans(status);

-- Extend skills with development tracking
ALTER TABLE skills ADD COLUMN IF NOT EXISTS demand_frequency INTEGER DEFAULT 0;
ALTER TABLE skills ADD COLUMN IF NOT EXISTS is_trending BOOLEAN DEFAULT FALSE;
ALTER TABLE skills ADD COLUMN IF NOT EXISTS acquired_date DATE;
ALTER TABLE skills ADD COLUMN IF NOT EXISTS learning_plan_id INTEGER REFERENCES learning_plans(id);

COMMIT;
