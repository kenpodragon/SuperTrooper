-- Migration 005: Template placeholder system
-- Adds template_map JSONB to resume_templates for placeholder-based generation.
-- The template_map stores the structural definition of each slot:
--   - placeholder name (e.g., JOB_1_BULLET_1)
--   - slot type (e.g., job_bullet, highlight, education)
--   - formatting rules (bold_label, size_pt, style)
--   - original_text for base reconstruction
--
-- This enables the future template editor (drag-and-drop layouts with named
-- formatting slots) by making templates self-describing.

-- Add template_map column
ALTER TABLE resume_templates ADD COLUMN IF NOT EXISTS template_map jsonb;

-- Add template_type to distinguish full vs placeholder templates
ALTER TABLE resume_templates ADD COLUMN IF NOT EXISTS template_type varchar(20) DEFAULT 'full';
-- Values: 'full' (complete resume), 'placeholder' (slots with {{MARKERS}})
