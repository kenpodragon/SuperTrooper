-- 033: Create languages table for Phase 6 content editors.

CREATE TABLE IF NOT EXISTS languages (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    proficiency VARCHAR(50) NOT NULL DEFAULT 'conversational',
    -- proficiency: native, fluent, professional, conversational, basic
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

-- References table for professional references
CREATE TABLE IF NOT EXISTS "references" (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    title VARCHAR(200),
    company VARCHAR(200),
    relationship VARCHAR(100),  -- e.g., 'former manager', 'peer', 'direct report'
    email VARCHAR(200),
    phone VARCHAR(50),
    linkedin_url VARCHAR(500),
    notes TEXT,
    ok_to_contact BOOLEAN NOT NULL DEFAULT true,
    career_history_id INTEGER REFERENCES career_history(id),
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Ensure summary_variants has sort_order
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'summary_variants' AND column_name = 'sort_order') THEN
        ALTER TABLE summary_variants ADD COLUMN sort_order INTEGER NOT NULL DEFAULT 0;
    END IF;
END $$;
