-- 036_section_based_templates.sql
-- Add headline to summary_variants for recipe HEADLINE refs
-- Add template_map_v1 backup column for migration safety

ALTER TABLE summary_variants ADD COLUMN IF NOT EXISTS headline TEXT;

ALTER TABLE resume_templates ADD COLUMN IF NOT EXISTS template_map_v1 JSONB;

-- Update recipe_version default for new recipes
COMMENT ON COLUMN resume_recipes.recipe_version IS '1=v1 numbered slots, 2=v2 section-based';
