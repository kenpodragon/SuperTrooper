-- 032: Add content_hash to resume_templates for duplicate detection on re-upload.
-- SHA-256 of template_blob. Unique constraint per template_type so the same file
-- uploaded as 'full' and 'uploaded_original' are separate entries.

ALTER TABLE resume_templates
    ADD COLUMN IF NOT EXISTS content_hash TEXT;

-- Back-fill existing rows
UPDATE resume_templates
   SET content_hash = encode(sha256(template_blob), 'hex')
 WHERE content_hash IS NULL
   AND template_blob IS NOT NULL;

-- Deduplicate: keep lowest id per (content_hash, template_type), re-point FKs
DO $$
DECLARE
    dup RECORD;
BEGIN
    FOR dup IN
        SELECT content_hash, template_type,
               min(id) AS keep_id,
               array_remove(array_agg(id ORDER BY id), min(id)) AS remove_ids
          FROM resume_templates
         WHERE content_hash IS NOT NULL
         GROUP BY content_hash, template_type
        HAVING count(*) > 1
    LOOP
        UPDATE resume_recipes   SET template_id = dup.keep_id WHERE template_id = ANY(dup.remove_ids);
        UPDATE onboard_uploads  SET template_id = dup.keep_id WHERE template_id = ANY(dup.remove_ids);
        DELETE FROM resume_templates WHERE id = ANY(dup.remove_ids);
    END LOOP;
END $$;

-- Unique per type so we don't block storing the same file as both
-- 'uploaded_original' and 'full'.
CREATE UNIQUE INDEX IF NOT EXISTS uq_template_hash_type
    ON resume_templates (content_hash, template_type);
