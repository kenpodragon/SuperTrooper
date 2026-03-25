-- Migration 029: Bullet Browser schema additions
-- Adds display_order, ai_analysis, content_hash, is_default, updated_at to bullets
-- Adds metadata and date normalization columns to career_history

-- ============================================================
-- bullets table additions
-- ============================================================

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='bullets' AND column_name='display_order') THEN
    ALTER TABLE bullets ADD COLUMN display_order INTEGER DEFAULT 0;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='bullets' AND column_name='ai_analysis') THEN
    ALTER TABLE bullets ADD COLUMN ai_analysis JSONB;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='bullets' AND column_name='ai_analyzed_at') THEN
    ALTER TABLE bullets ADD COLUMN ai_analyzed_at TIMESTAMP;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='bullets' AND column_name='content_hash') THEN
    ALTER TABLE bullets ADD COLUMN content_hash TEXT;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='bullets' AND column_name='is_default') THEN
    ALTER TABLE bullets ADD COLUMN is_default BOOLEAN DEFAULT FALSE;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='bullets' AND column_name='updated_at') THEN
    ALTER TABLE bullets ADD COLUMN updated_at TIMESTAMP DEFAULT NOW();
  END IF;
END $$;

-- ============================================================
-- career_history table additions
-- ============================================================

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='career_history' AND column_name='metadata') THEN
    ALTER TABLE career_history ADD COLUMN metadata JSONB DEFAULT '{}';
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='career_history' AND column_name='start_date_raw') THEN
    ALTER TABLE career_history ADD COLUMN start_date_raw TEXT;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='career_history' AND column_name='end_date_raw') THEN
    ALTER TABLE career_history ADD COLUMN end_date_raw TEXT;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='career_history' AND column_name='start_date_iso') THEN
    ALTER TABLE career_history ADD COLUMN start_date_iso DATE;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='career_history' AND column_name='end_date_iso') THEN
    ALTER TABLE career_history ADD COLUMN end_date_iso DATE;
  END IF;
END $$;

-- ============================================================
-- Indexes
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_bullets_content_hash
  ON bullets(content_hash);

CREATE INDEX IF NOT EXISTS idx_bullets_display_order
  ON bullets(career_history_id, display_order);

CREATE UNIQUE INDEX IF NOT EXISTS idx_bullets_one_default_synopsis
  ON bullets(career_history_id)
  WHERE type = 'synopsis' AND is_default = TRUE;

-- ============================================================
-- Trigger: auto-update content_hash and updated_at on UPDATE
-- ============================================================

CREATE OR REPLACE FUNCTION bullets_update_trigger_fn()
RETURNS TRIGGER AS $$
BEGIN
  NEW.content_hash := md5(NEW.text);
  NEW.updated_at   := NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS bullets_update_trigger ON bullets;

CREATE TRIGGER bullets_update_trigger
  BEFORE UPDATE ON bullets
  FOR EACH ROW
  EXECUTE FUNCTION bullets_update_trigger_fn();

-- ============================================================
-- Backfill existing data
-- ============================================================

-- Set content_hash for all existing bullets
UPDATE bullets
SET content_hash = md5(text)
WHERE content_hash IS NULL;

-- Set updated_at = created_at where null (fallback to NOW())
UPDATE bullets
SET updated_at = COALESCE(created_at, NOW())
WHERE updated_at IS NULL;

-- Copy existing date columns to raw/iso fields in career_history
-- Assumes existing columns: start_date, end_date (DATE type)
UPDATE career_history
SET
  start_date_raw = start_date::TEXT,
  start_date_iso = start_date::DATE
WHERE start_date IS NOT NULL
  AND start_date_raw IS NULL;

UPDATE career_history
SET
  end_date_raw = end_date::TEXT,
  end_date_iso = end_date::DATE
WHERE end_date IS NOT NULL
  AND end_date_raw IS NULL;
