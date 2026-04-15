-- 035_template_is_default.sql
-- Add is_default flag to resume_templates for seed/built-in template protection.
ALTER TABLE resume_templates ADD COLUMN IF NOT EXISTS is_default BOOLEAN DEFAULT FALSE;
