-- Migration 030: Resume Builder — recipe v2 + theme support

-- recipe_version: 1 = legacy flat slots, 2 = array-based sections
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns
    WHERE table_name='resume_recipes' AND column_name='recipe_version') THEN
    ALTER TABLE resume_recipes ADD COLUMN recipe_version INTEGER DEFAULT 1;
  END IF;
END $$;

-- theme overrides per recipe (fonts, colors, margins, etc.)
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns
    WHERE table_name='resume_recipes' AND column_name='theme') THEN
    ALTER TABLE resume_recipes ADD COLUMN theme JSONB;
  END IF;
END $$;

-- backup of v1 recipe JSON for rollback safety
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns
    WHERE table_name='resume_recipes' AND column_name='recipe_v1_backup') THEN
    ALTER TABLE resume_recipes ADD COLUMN recipe_v1_backup JSONB;
  END IF;
END $$;

-- template preview thumbnail cache
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns
    WHERE table_name='resume_templates' AND column_name='preview_blob') THEN
    ALTER TABLE resume_templates ADD COLUMN preview_blob BYTEA;
  END IF;
END $$;
