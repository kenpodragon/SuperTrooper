-- Migration 023: Add scheduled_for to linkedin_posts + post schedule index
-- Enables content calendar scheduling for LinkedIn posts

ALTER TABLE linkedin_posts
    ADD COLUMN IF NOT EXISTS scheduled_for TIMESTAMP WITHOUT TIME ZONE;

CREATE INDEX IF NOT EXISTS idx_linkedin_posts_scheduled
    ON linkedin_posts (scheduled_for)
    WHERE scheduled_for IS NOT NULL;

COMMENT ON COLUMN linkedin_posts.scheduled_for IS
    'When this post is scheduled to be published. NULL = unscheduled draft.';
