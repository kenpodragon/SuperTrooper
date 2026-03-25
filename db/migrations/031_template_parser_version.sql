DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='resume_templates' AND column_name='parser_version') THEN
        ALTER TABLE resume_templates ADD COLUMN parser_version VARCHAR(10) DEFAULT '1.0';
    END IF;
END $$;
